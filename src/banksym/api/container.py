"""Composition root — wires repositories, services, and registered capabilities together.

Importing this module also imports capability implementations so they self-register in their
registries. This is the one place allowed to know about every layer.
"""

from __future__ import annotations

from dataclasses import dataclass

# Importing implementations triggers their @registry.register side effects.
import banksym.capabilities.auth.simple  # noqa: F401
import banksym.capabilities.localization.packs  # noqa: F401
import banksym.capabilities.protocols.berlingroup.adapter  # noqa: F401
import banksym.capabilities.settlement.interbank  # noqa: F401
import banksym.capabilities.settlement.netting  # noqa: F401
import banksym.capabilities.settlement.rtgs  # noqa: F401
import banksym.capabilities.txgen.rulebased  # noqa: F401
from banksym.capabilities.auth.base import (
    AuthProvider,
    InMemorySessionStore,
    ScaProvider,
    auth_registry,
    sca_registry,
)
from banksym.capabilities.protocols.base import (
    InMemoryConsentStore,
    InMemoryPaymentStore,
    ProtocolAdapter,
    protocol_registry,
)
from banksym.capabilities.protocols.base.consent import (
    Authorisation,
    Consent,
    ConsentStatus,
    ScaStatus,
)
from banksym.capabilities.protocols.base.payment import PaymentStatus
from banksym.capabilities.settlement.base import (
    SettlementEngine,
    SettlementResult,
    settlement_registry,
)
from banksym.capabilities.txgen.base import txgen_registry
from banksym.core.domain.account import AccountType
from banksym.core.domain.transaction import TransactionRecord
from banksym.core.kernel.ids import new_id
from banksym.core.kernel.money import Money
from banksym.core.service import CoreBankingService
from banksym.persistence import (
    SqlBankRepository,
    SqlCoreBankingRepository,
    SqlCredentialStore,
    init_db,
    make_engine,
    make_session_factory,
)
from banksym.settings import get_settings
from banksym.simulation import SimulationEngine
from banksym.tenancy import BankService

DEFAULT_SETTLEMENT = "rtgs"
DEFAULT_AUTH = "simple"
DEFAULT_SCA = "auto"
DEFAULT_PASSWORD = "foobar!"


@dataclass(slots=True)
class OAuthCode:
    """A one-time OAuth2 authorization code bound to a bank, consent, and PSU session."""

    bank_id: str
    consent_id: str
    session_token: str
    redirect_uri: str


class Container:
    """Holds long-lived application services."""

    def __init__(self) -> None:
        # A real database backs all persistent state (banks, customers, accounts,
        # transactions, and online-banking credentials), so it survives restarts.
        engine = make_engine(get_settings().database_url)
        init_db(engine)
        session_factory = make_session_factory(engine)
        self.bank_repository = SqlBankRepository(session_factory)
        self.banking_repository = SqlCoreBankingRepository(session_factory)
        self.credential_store = SqlCredentialStore(session_factory)
        # Consents, payments, and sessions are short-lived flow state kept in memory.
        self.consent_store = InMemoryConsentStore()
        self.payment_store = InMemoryPaymentStore()
        self.session_store = InMemorySessionStore()
        self.bank_service = BankService(self.bank_repository)
        self.banking = CoreBankingService(self.banking_repository)
        # One-time OAuth2 authorization codes minted during the redirect SCA flow.
        self.oauth_codes: dict[str, OAuthCode] = {}
        # Server-side live transaction simulator (runs independently of any browser tab).
        self.simulation = SimulationEngine(self)

    def delete_bank(self, bank_id: str) -> None:
        """Delete a bank tenant and purge all of its data across every store."""
        self.bank_service.delete_bank(bank_id)
        self.banking_repository.remove_bank(bank_id)
        self.consent_store.purge(bank_id)
        self.payment_store.purge(bank_id)
        self.credential_store.purge(bank_id)

    def register_customer_credential(
        self,
        bank_id: str,
        customer_id: str,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> str:
        """Create online-banking credentials for a customer and return the username.

        Defaults the username to the customer's email (falling back to the customer id) and the
        password to :data:`DEFAULT_PASSWORD`, so every customer can log in to Open Banking.
        """
        customer = self.banking.get_customer(bank_id, customer_id)
        login = (username or customer.email or customer.id).strip()
        provider = self.resolve_auth_provider(bank_id)
        provider.register(bank_id, login, password or DEFAULT_PASSWORD, customer_id)
        return login

    def post_external_transaction(
        self,
        bank_id: str,
        account_id: str,
        *,
        amount: object,
        currency: str | None = None,
        side: str = "credit",
        description: str | None = None,
        reference: str | None = None,
    ) -> TransactionRecord:
        """Book a single transaction against an account, facing the bank's "External world".

        ``side="credit"`` moves money into the account; ``"debit"`` moves it out. The amount is
        booked in the account's own currency (an optional ``currency`` must match it). Returns the
        resulting account-facing transaction record. Raises :class:`ValueError` on a currency
        mismatch and propagates core :class:`BankSymError` (e.g. insufficient funds on a debit).
        """
        account = self.banking.get_account(bank_id, account_id)
        ccy = (currency or account.currency).upper()
        if ccy != account.currency:
            raise ValueError(
                f"Currency {ccy} does not match account currency {account.currency}"
            )
        money = Money.from_decimal(amount, ccy)  # type: ignore[arg-type]
        counterparty = self.banking.ensure_internal_account(
            bank_id, ccy, AccountType.INTERNAL, "External world"
        )
        desc = description or ("Credit" if side == "credit" else "Debit")
        if side == "credit":
            self.banking.transfer(
                bank_id,
                counterparty.id,
                account_id,
                money,
                description=desc,
                reference=reference,
                allow_overdraft=True,
            )
        else:
            self.banking.transfer(
                bank_id,
                account_id,
                counterparty.id,
                money,
                description=desc,
                reference=reference,
            )
        return self.banking.transaction_history(bank_id, account_id)[-1]

    def approve_consent(
        self,
        bank_id: str,
        consent_id: str,
        *,
        customer_id: str | None = None,
        account_ids: list[str] | None = None,
    ) -> Consent:
        """Activate a consent after the PSU has authenticated at the bank (redirect SCA).

        Creates a finalised SCA authorisation sub-resource, binds the consent to the authenticated
        customer (so account access is scoped to that PSU), and moves it to ``valid``. When
        ``account_ids`` is given, access is further narrowed to exactly those accounts (the ones
        the PSU ticked on the authorisation page). Raises :class:`KeyError` if the consent is
        unknown for the bank.
        """
        consent = self.consent_store.get(bank_id, consent_id)
        if consent is None:
            raise KeyError(consent_id)
        auth = Authorisation(sca_status=ScaStatus.FINALISED)
        consent.authorisations[auth.id] = auth
        consent.status = ConsentStatus.VALID
        if customer_id is not None:
            consent.customer_id = customer_id
        if account_ids is not None:
            consent.allowed_account_ids = list(account_ids)
        self.consent_store.save(consent)
        return consent

    def issue_oauth_code(
        self, bank_id: str, consent_id: str, session_token: str, redirect_uri: str
    ) -> str:
        """Mint a one-time authorization code bound to the PSU session and consent."""
        code = new_id("code_")
        self.oauth_codes[code] = OAuthCode(bank_id, consent_id, session_token, redirect_uri)
        return code

    def exchange_oauth_code(
        self, bank_id: str, code: str, redirect_uri: str
    ) -> OAuthCode | None:
        """Redeem an authorization code (single use). Returns ``None`` if it is invalid."""
        record = self.oauth_codes.get(code)
        if record is None or record.bank_id != bank_id or record.redirect_uri != redirect_uri:
            return None
        del self.oauth_codes[code]
        return record

    def make_txgen(self, name: str) -> object:
        """Instantiate a transaction generator implementation bound to the core service."""
        impl = txgen_registry.get(name)
        return impl(self.banking)

    def make_settlement_engine(self, name: str) -> SettlementEngine:
        """Instantiate a settlement engine bound to the core service."""
        impl = settlement_registry.get(name)
        return impl(self.banking)

    def resolve_settlement_engine(self, bank_id: str) -> SettlementEngine:
        """Resolve the settlement engine a bank is configured to use (default: RTGS)."""
        bank = self.bank_service.get_bank(bank_id)
        name = bank.capabilities.get("settlement") or DEFAULT_SETTLEMENT
        if name not in settlement_registry:
            name = DEFAULT_SETTLEMENT
        return self.make_settlement_engine(name)

    def make_auth_provider(self, name: str) -> AuthProvider:
        """Instantiate an auth provider bound to the shared credential/session stores."""
        impl = auth_registry.get(name)
        return impl(self.credential_store, self.session_store)

    def resolve_auth_provider(self, bank_id: str) -> AuthProvider:
        bank = self.bank_service.get_bank(bank_id)
        name = bank.capabilities.get("auth") or DEFAULT_AUTH
        if name not in auth_registry:
            name = DEFAULT_AUTH
        return self.make_auth_provider(name)

    def make_sca_provider(self, name: str) -> ScaProvider:
        impl = sca_registry.get(name)
        return impl()

    def resolve_sca_provider(self, bank_id: str) -> ScaProvider:
        bank = self.bank_service.get_bank(bank_id)
        name = bank.capabilities.get("sca") or DEFAULT_SCA
        if name not in sca_registry:
            name = DEFAULT_SCA
        return self.make_sca_provider(name)

    def run_settlement_cycle(self, bank_id: str) -> list[SettlementResult]:
        """Run the bank's deferred settlement cycle and reconcile payment statuses.

        Settles any queued positions via the engine's ``run_cycle`` then promotes payments that
        were accepted-but-pending (ACTC) to completed (ACSC).
        """
        engine = self.resolve_settlement_engine(bank_id)
        results = engine.run_cycle(bank_id)
        if results:
            for payment in self.payment_store.list(bank_id):
                if payment.status == PaymentStatus.ACCEPTED_TECHNICAL_VALIDATION:
                    payment.status = PaymentStatus.ACCEPTED_SETTLEMENT_COMPLETED
                    self.payment_store.save(payment)
        return results

    def make_protocol_adapter(self, name: str) -> ProtocolAdapter:
        """Instantiate a protocol adapter bound to the shared services."""
        impl = protocol_registry.get(name)
        return impl(
            self.banking,
            self.consent_store,
            self.payment_store,
            self.bank_service,
            self.resolve_settlement_engine,
            self.resolve_auth_provider,
        )

    def protocol_adapters(self) -> list[ProtocolAdapter]:
        """Instantiate every registered protocol adapter."""
        return [self.make_protocol_adapter(name) for name in protocol_registry.names()]


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset global state (used by tests)."""
    global _container
    _container = None
