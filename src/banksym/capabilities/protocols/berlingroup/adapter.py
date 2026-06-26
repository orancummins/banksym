"""Berlin Group XS2A adapter — maps AIS consent + account-information flows onto core services.

Endpoints are mounted under ``/xs2a/{bank_id}/v1`` so the multi-tenant test bank can host many
banks while keeping the Berlin Group path structure after the tenant segment. SCA is auto-approved
to keep the test loop fast (a real ASPSP would redirect the PSU); the authorisation sub-resource is
still modelled so TPP integrations exercise the full consent lifecycle.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Path

from banksym.capabilities.protocols.base.adapter import APIAdapter, api_registry
from banksym.capabilities.protocols.base.consent import (
    Authorisation,
    Consent,
    ConsentStatus,
    ScaStatus,
)
from banksym.capabilities.protocols.base.payment import Payment, PaymentStatus
from banksym.capabilities.protocols.berlingroup import schemas as s
from banksym.capabilities.settlement.base import SettlementInstruction, SettlementStatus
from banksym.core.domain.account import Account, AccountType
from banksym.core.kernel.money import Money
from banksym.tenancy.service import BankNotFoundError

_CASH_ACCOUNT_TYPE = {
    AccountType.CURRENT: "CACC",
    AccountType.SAVINGS: "SVGS",
    AccountType.CREDIT_CARD: "CARD",
    AccountType.LOAN: "LOAN",
}


def _synth_iban(account: Account, country: str) -> str:
    """Deterministic pseudo-IBAN for accounts created without one (test data only)."""
    if account.iban:
        return account.iban
    tail = account.id.replace("acc_", "")[:16].upper().ljust(16, "0")
    return f"{country[:2].upper()}00BSYM{tail}"


@api_registry.register
class BerlinGroupAdapter(APIAdapter):
    capability_name = "berlin_group"
    protocol_title = "Berlin Group NextGenPSD2 (XS2A)"

    def build_router(self) -> APIRouter:  # noqa: C901 - cohesive protocol surface
        router = APIRouter(prefix="/xs2a/{bank_id}/v1", tags=["xs2a (Berlin Group)"])
        banking = self.banking
        consents = self.consents
        banks = self.banks

        def require_bank(bank_id: str) -> None:
            try:
                banks.get_bank(bank_id)
            except BankNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Bank not found") from exc

        def base(bank_id: str) -> str:
            return f"/xs2a/{bank_id}/v1"

        def load_consent(bank_id: str, consent_id: str) -> Consent:
            consent = consents.get(bank_id, consent_id)
            if consent is None:
                raise HTTPException(status_code=403, detail="Consent unknown")
            return consent

        def require_valid_consent(bank_id: str, consent_id: str | None) -> Consent:
            if not consent_id:
                raise HTTPException(status_code=401, detail="Consent-ID header required")
            consent = load_consent(bank_id, consent_id)
            if consent.status != ConsentStatus.VALID:
                raise HTTPException(
                    status_code=401,
                    detail=f"Consent status is {consent.status.value}, expected valid",
                )
            return consent

        def verify_psu(bank_id: str, authorization: str | None, consent: Consent) -> None:
            """Require a valid PSU login session before SCA can finalise a consent.

            The session is issued by the bank's auth provider when the PSU logs in with their real
            online-banking credentials, so SCA is bound to genuine authentication rather than being
            blindly auto-approved.
            """
            if not authorization:
                raise HTTPException(
                    status_code=401,
                    detail="PSU authentication required: 'Authorization: Bearer <session>'",
                )
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise HTTPException(status_code=401, detail="Expected 'Bearer <token>'")
            session = self.auth_resolver(bank_id).get_session(token)
            if session is None or session.bank_id != bank_id:
                raise HTTPException(status_code=401, detail="Invalid or expired PSU session")
            if consent.psu_id and session.username != consent.psu_id:
                raise HTTPException(
                    status_code=403, detail="Authenticated PSU does not match the consent PSU"
                )
            # Scope the consent to the authenticated customer so account access can't span PSUs.
            consent.customer_id = session.customer_id

        def visible_accounts(bank_id: str, consent: Consent) -> list[Account]:
            accounts = [
                a
                for a in banking.list_accounts(bank_id)
                if not a.is_internal and a.customer_id is not None
            ]
            # Once the PSU has authenticated, the consent is scoped to that customer so a TPP
            # never sees other customers' accounts (even with an "all accounts" consent).
            if consent.customer_id is not None:
                accounts = [a for a in accounts if a.customer_id == consent.customer_id]
            # Narrow to exactly the accounts the PSU ticked on the bank's authorisation page.
            if consent.allowed_account_ids is not None:
                allowed_ids = set(consent.allowed_account_ids)
                accounts = [a for a in accounts if a.id in allowed_ids]
            if consent.all_accounts:
                return accounts
            allowed = consent.allowed_ibans()
            country = banks.get_bank(bank_id).country
            return [a for a in accounts if _synth_iban(a, country) in allowed]

        def to_details(bank_id: str, account: Account) -> s.AccountDetails:
            country = banks.get_bank(bank_id).country
            resource = account.id
            return s.AccountDetails(
                resourceId=resource,
                iban=_synth_iban(account, country),
                currency=account.currency,
                name=account.name,
                cashAccountType=_CASH_ACCOUNT_TYPE.get(account.type, "CACC"),
                _links={
                    "balances": s.HrefObject(href=f"{base(bank_id)}/accounts/{resource}/balances"),
                    "transactions": s.HrefObject(
                        href=f"{base(bank_id)}/accounts/{resource}/transactions"
                    ),
                },
            )

        # -- Consents ---------------------------------------------------------------
        @router.post(
            "/consents",
            response_model=s.ConsentResponse,
            status_code=201,
            summary="Create an AIS consent",
        )
        def create_consent(
            body: s.ConsentRequest,
            bank_id: str = Path(...),
            psu_id: str | None = Header(default=None, alias="PSU-ID"),
        ) -> s.ConsentResponse:
            """Create an account-information consent and return a link to start authorisation (SCA).

            The optional ``PSU-ID`` header binds the consent to a specific account holder so that
            only that PSU can later authorise it.
            """
            require_bank(bank_id)
            consent = Consent(
                bank_id=bank_id,
                access=body.access.model_dump(exclude_none=True, by_alias=True),
                recurring=body.recurringIndicator,
                frequency_per_day=body.frequencyPerDay,
                valid_until=body.validUntil,
                combined_service=body.combinedServiceIndicator,
                psu_id=psu_id,
            )
            consents.add(consent)
            href = f"{base(bank_id)}/consents/{consent.id}"
            return s.ConsentResponse(
                consentStatus=consent.status.value,
                consentId=consent.id,
                _links={"startAuthorisation": s.HrefObject(href=f"{href}/authorisations")},
            )

        @router.get(
            "/consents/{consent_id}",
            response_model=s.ConsentInformationResponse,
            summary="Get consent details",
        )
        def get_consent(consent_id: str, bank_id: str = Path(...)) -> s.ConsentInformationResponse:
            """Return the access scope, validity and current status of a consent."""
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            return s.ConsentInformationResponse(
                access=s.AccessObject(**consent.access),
                recurringIndicator=consent.recurring,
                validUntil=consent.valid_until,
                frequencyPerDay=consent.frequency_per_day,
                consentStatus=consent.status.value,
            )

        @router.get(
            "/consents/{consent_id}/status",
            response_model=s.ConsentStatusResponse,
            summary="Get consent status",
        )
        def consent_status(consent_id: str, bank_id: str = Path(...)) -> s.ConsentStatusResponse:
            """Return only the lifecycle status of a consent (e.g. ``received``, ``valid``)."""
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            return s.ConsentStatusResponse(consentStatus=consent.status.value)

        @router.delete(
            "/consents/{consent_id}", status_code=204, summary="Revoke a consent"
        )
        def delete_consent(consent_id: str, bank_id: str = Path(...)) -> None:
            """Revoke a consent on behalf of the TPP, marking it terminated."""
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            consent.status = ConsentStatus.TERMINATED_BY_TPP
            consents.save(consent)

        # -- Authorisation (SCA) ----------------------------------------------------
        @router.post(
            "/consents/{consent_id}/authorisations",
            response_model=s.StartScaResponse,
            status_code=201,
            summary="Start consent authorisation (SCA)",
        )
        def start_authorisation(
            consent_id: str, bank_id: str = Path(...)
        ) -> s.StartScaResponse:
            """Begin a Strong Customer Authentication flow for a consent."""
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            auth = Authorisation()
            consent.authorisations[auth.id] = auth
            consents.save(consent)
            href = f"{base(bank_id)}/consents/{consent_id}/authorisations/{auth.id}"
            return s.StartScaResponse(
                scaStatus=auth.sca_status.value,
                authorisationId=auth.id,
                _links={"scaStatus": s.HrefObject(href=href)},
            )

        @router.put(
            "/consents/{consent_id}/authorisations/{authorisation_id}",
            response_model=s.ScaStatusResponse,
            summary="Complete consent authorisation (SCA)",
        )
        def update_authorisation(
            consent_id: str,
            authorisation_id: str,
            body: s.UpdateAuthorisationRequest,
            bank_id: str = Path(...),
            authorization: str | None = Header(default=None, alias="Authorization"),
        ) -> s.ScaStatusResponse:
            """Complete SCA by presenting a valid PSU session, which activates the consent.

            The ``Authorization: Bearer <token>`` header must carry the session of the PSU that
            owns the consent; on success the authorisation is finalised and the consent becomes
            ``valid``.
            """
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            auth = consent.authorisations.get(authorisation_id)
            if auth is None:
                raise HTTPException(status_code=404, detail="Authorisation unknown")
            # SCA is bound to a real PSU login session; only then is the consent activated.
            verify_psu(bank_id, authorization, consent)
            auth.sca_status = ScaStatus.FINALISED
            consent.status = ConsentStatus.VALID
            consents.save(consent)
            return s.ScaStatusResponse(scaStatus=auth.sca_status.value)

        @router.get(
            "/consents/{consent_id}/authorisations/{authorisation_id}",
            response_model=s.ScaStatusResponse,
            summary="Get consent authorisation status",
        )
        def get_authorisation(
            consent_id: str, authorisation_id: str, bank_id: str = Path(...)
        ) -> s.ScaStatusResponse:
            """Return the SCA status of a consent authorisation."""
            require_bank(bank_id)
            consent = load_consent(bank_id, consent_id)
            auth = consent.authorisations.get(authorisation_id)
            if auth is None:
                raise HTTPException(status_code=404, detail="Authorisation unknown")
            return s.ScaStatusResponse(scaStatus=auth.sca_status.value)

        # -- Account information (AIS) ----------------------------------------------
        @router.get("/accounts", response_model=s.AccountList, summary="List accessible accounts")
        def get_accounts(
            bank_id: str = Path(...),
            consent_id: str | None = Header(default=None, alias="Consent-ID"),
        ) -> s.AccountList:
            """List the accounts the supplied ``Consent-ID`` grants access to."""
            require_bank(bank_id)
            consent = require_valid_consent(bank_id, consent_id)
            return s.AccountList(
                accounts=[to_details(bank_id, a) for a in visible_accounts(bank_id, consent)]
            )

        @router.get(
            "/accounts/{account_id}",
            response_model=s.AccountDetailsResponse,
            summary="Get account details",
        )
        def get_account(
            account_id: str,
            bank_id: str = Path(...),
            consent_id: str | None = Header(default=None, alias="Consent-ID"),
        ) -> s.AccountDetailsResponse:
            """Return details for a single account within the consent's scope (404 otherwise)."""
            require_bank(bank_id)
            consent = require_valid_consent(bank_id, consent_id)
            account = _resolve_account(bank_id, account_id, consent)
            return s.AccountDetailsResponse(account=to_details(bank_id, account))

        @router.get(
            "/accounts/{account_id}/balances",
            response_model=s.BalancesResponse,
            summary="Get account balances",
        )
        def get_balances(
            account_id: str,
            bank_id: str = Path(...),
            consent_id: str | None = Header(default=None, alias="Consent-ID"),
        ) -> s.BalancesResponse:
            """Return the closing booked balance for an account within the consent's scope."""
            require_bank(bank_id)
            consent = require_valid_consent(bank_id, consent_id)
            account = _resolve_account(bank_id, account_id, consent)
            balance = banking.balance(bank_id, account_id)
            country = banks.get_bank(bank_id).country
            return s.BalancesResponse(
                account=s.AccountReference(iban=_synth_iban(account, country)),
                balances=[
                    s.BalanceObject(
                        balanceType="closingBooked",
                        balanceAmount=s.AmountObject(
                            currency=balance.currency, amount=str(balance.to_decimal())
                        ),
                    )
                ],
            )

        @router.get(
            "/accounts/{account_id}/transactions",
            response_model=s.TransactionsResponse,
            summary="Get account transactions",
        )
        def get_transactions(
            account_id: str,
            bank_id: str = Path(...),
            consent_id: str | None = Header(default=None, alias="Consent-ID"),
        ) -> s.TransactionsResponse:
            """Return booked transactions for an account within the consent's scope."""
            require_bank(bank_id)
            consent = require_valid_consent(bank_id, consent_id)
            account = _resolve_account(bank_id, account_id, consent)
            country = banks.get_bank(bank_id).country
            history = banking.transaction_history(bank_id, account_id)
            booked = [
                s.TransactionEntry(
                    transactionId=r.journal_id,
                    bookingDate=r.booked_at.date(),
                    valueDate=r.booked_at.date(),
                    transactionAmount=s.AmountObject(
                        currency=r.amount.currency, amount=str(r.amount.to_decimal())
                    ),
                    remittanceInformationUnstructured=r.description or None,
                )
                for r in history
            ]
            return s.TransactionsResponse(
                account=s.AccountReference(iban=_synth_iban(account, country)),
                transactions=s.TransactionsBody(booked=booked),
            )

        # -- Payment initiation (PIS) -----------------------------------------------
        def account_by_iban(bank_id: str, iban: str | None) -> Account | None:
            if not iban:
                return None
            country = banks.get_bank(bank_id).country
            for account in banking.list_accounts(bank_id):
                if account.is_internal or account.customer_id is None:
                    continue
                if _synth_iban(account, country) == iban:
                    return account
            return None

        def finalise_payment(payment: Payment) -> None:
            """Run settlement for an authorised payment and record the outcome."""
            engine = self.settlement_resolver(payment.bank_id)
            result = engine.settle(
                SettlementInstruction(
                    bank_id=payment.bank_id,
                    debtor_account_id=payment.debtor_account_id,
                    amount=payment.amount,
                    creditor_name=payment.creditor_name,
                    creditor_iban=payment.creditor_iban,
                    reference=payment.remittance or payment.end_to_end_id,
                )
            )
            if result.status == SettlementStatus.SETTLED:
                payment.status = PaymentStatus.ACCEPTED_SETTLEMENT_COMPLETED
                payment.settlement_journal_id = result.journal_id
            elif result.status == SettlementStatus.PENDING:
                # Deferred settlement (e.g. netting): accepted, awaiting the cycle.
                payment.status = PaymentStatus.ACCEPTED_TECHNICAL_VALIDATION
                payment.settlement_journal_id = result.journal_id
            else:
                payment.status = PaymentStatus.REJECTED
            self.payments.save(payment)

        @router.post(
            "/payments/{payment_product}",
            response_model=s.PaymentInitiationResponse,
            status_code=201,
            summary="Initiate a payment",
        )
        def initiate_payment(
            payment_product: str,
            body: s.PaymentInitiation,
            bank_id: str = Path(...),
        ) -> s.PaymentInitiationResponse:
            """Initiate a single payment from a debtor account and return a link to authorise it.

            Validates the debtor IBAN, currency match and a positive amount before creating the
            payment in a ``received`` state awaiting SCA.
            """
            require_bank(bank_id)
            debtor = account_by_iban(bank_id, body.debtorAccount.iban)
            if debtor is None:
                raise HTTPException(status_code=400, detail="Unknown debtor account")
            if debtor.currency != body.instructedAmount.currency:
                raise HTTPException(
                    status_code=400, detail="Instructed amount currency mismatch"
                )
            amount = Money.from_decimal(
                body.instructedAmount.amount, body.instructedAmount.currency
            )
            if not amount.is_positive:
                raise HTTPException(status_code=400, detail="Amount must be positive")
            payment = Payment(
                bank_id=bank_id,
                payment_product=payment_product,
                debtor_account_id=debtor.id,
                amount=amount,
                creditor_iban=body.creditorAccount.iban,
                creditor_name=body.creditorName,
                remittance=body.remittanceInformationUnstructured,
                end_to_end_id=body.endToEndIdentification,
            )
            self.payments.add(payment)
            href = f"{base(bank_id)}/payments/{payment_product}/{payment.id}"
            return s.PaymentInitiationResponse(
                transactionStatus=payment.status.value,
                paymentId=payment.id,
                _links={"startAuthorisation": s.HrefObject(href=f"{href}/authorisations")},
            )

        def load_payment(bank_id: str, payment_id: str) -> Payment:
            payment = self.payments.get(bank_id, payment_id)
            if payment is None:
                raise HTTPException(status_code=404, detail="Payment unknown")
            return payment

        @router.get(
            "/payments/{payment_product}/{payment_id}",
            response_model=s.PaymentInformationResponse,
            summary="Get payment details",
        )
        def get_payment(
            payment_product: str, payment_id: str, bank_id: str = Path(...)
        ) -> s.PaymentInformationResponse:
            """Return the debtor, creditor, amount and status of an initiated payment."""
            require_bank(bank_id)
            payment = load_payment(bank_id, payment_id)
            return s.PaymentInformationResponse(
                transactionStatus=payment.status.value,
                instructedAmount=s.AmountObject(
                    currency=payment.amount.currency, amount=str(payment.amount.to_decimal())
                ),
                debtorAccount=s.AccountReference(
                    iban=_synth_iban(
                        banking.get_account(bank_id, payment.debtor_account_id),
                        banks.get_bank(bank_id).country,
                    )
                ),
                creditorAccount=s.AccountReference(iban=payment.creditor_iban),
                creditorName=payment.creditor_name,
                remittanceInformationUnstructured=payment.remittance,
            )

        @router.get(
            "/payments/{payment_product}/{payment_id}/status",
            response_model=s.PaymentStatusResponse,
            summary="Get payment status",
        )
        def payment_status(
            payment_product: str, payment_id: str, bank_id: str = Path(...)
        ) -> s.PaymentStatusResponse:
            """Return only the transaction status of an initiated payment."""
            require_bank(bank_id)
            payment = load_payment(bank_id, payment_id)
            return s.PaymentStatusResponse(transactionStatus=payment.status.value)

        @router.post(
            "/payments/{payment_product}/{payment_id}/authorisations",
            response_model=s.StartScaResponse,
            status_code=201,
            summary="Start payment authorisation (SCA)",
        )
        def start_payment_authorisation(
            payment_product: str, payment_id: str, bank_id: str = Path(...)
        ) -> s.StartScaResponse:
            """Begin a Strong Customer Authentication flow for an initiated payment."""
            require_bank(bank_id)
            payment = load_payment(bank_id, payment_id)
            auth = Authorisation()
            payment.authorisations[auth.id] = auth
            self.payments.save(payment)
            href = (
                f"{base(bank_id)}/payments/{payment_product}/{payment_id}"
                f"/authorisations/{auth.id}"
            )
            return s.StartScaResponse(
                scaStatus=auth.sca_status.value,
                authorisationId=auth.id,
                _links={"scaStatus": s.HrefObject(href=href)},
            )

        @router.put(
            "/payments/{payment_product}/{payment_id}/authorisations/{authorisation_id}",
            response_model=s.ScaStatusResponse,
            summary="Complete payment authorisation (SCA)",
        )
        def update_payment_authorisation(
            payment_product: str,
            payment_id: str,
            authorisation_id: str,
            body: s.UpdateAuthorisationRequest,
            bank_id: str = Path(...),
        ) -> s.ScaStatusResponse:
            """Complete SCA for a payment, which triggers settlement via the bank's engine."""
            require_bank(bank_id)
            payment = load_payment(bank_id, payment_id)
            auth = payment.authorisations.get(authorisation_id)
            if auth is None:
                raise HTTPException(status_code=404, detail="Authorisation unknown")
            # Test bank: auto-approve SCA, then settle the payment.
            auth.sca_status = ScaStatus.FINALISED
            self.payments.save(payment)
            finalise_payment(payment)
            return s.ScaStatusResponse(scaStatus=auth.sca_status.value)

        def _resolve_account(bank_id: str, account_id: str, consent: Consent) -> Account:
            """Resolve an account that the consent actually grants access to.

            Returns 404 for accounts outside the consent scope (e.g. another customer's account),
            so a TPP cannot read arbitrary accounts by guessing IDs.
            """
            allowed = {a.id for a in visible_accounts(bank_id, consent)}
            if account_id not in allowed:
                raise HTTPException(status_code=404, detail="Account not found")
            return banking.get_account(bank_id, account_id)

        return router
