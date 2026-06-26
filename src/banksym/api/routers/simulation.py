"""Server-side live transaction simulation control.

The simulator runs inside the API process (not in any browser tab), so it keeps generating
transactions across selected accounts even after the Live page is closed. Clients start/stop it and
poll a rolling feed of the most recent transactions.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from banksym.api.deps import ContainerDep
from banksym.api.schemas import (
    SimulationEventResponse,
    SimulationFeedResponse,
    SimulationParticipantResponse,
    SimulationParticipantsResponse,
    SimulationStartRequest,
    SimulationStatusResponse,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get(
    "/participants",
    response_model=SimulationParticipantsResponse,
    summary="List currently participating accounts",
)
def participants(container: ContainerDep) -> SimulationParticipantsResponse:
    """Return metadata for the currently configured simulation targets only."""
    targets = container.simulation.targets()
    if not targets:
        # Keep the Live page immediately usable even before the first explicit /simulation/start.
        targets = _default_participant_targets(container)

    rows: list[SimulationParticipantResponse] = []
    for bank_id, account_id in targets:
        try:
            bank = container.bank_service.get_bank(bank_id)
            account = container.banking.get_account(bank_id, account_id)
        except Exception:
            # Ignore stale targets that point at removed banks/accounts.
            continue

        customer_id = account.customer_id
        customer_name = ""
        if customer_id:
            try:
                customer_name = container.banking.get_customer(
                    bank_id, customer_id
                ).full_name
            except Exception:
                customer_name = customer_id

        rows.append(
            SimulationParticipantResponse(
                bank_id=bank_id,
                bank_name=bank.branding.display_name,
                bank_color=bank.branding.primary_color,
                country=bank.country,
                customer_id=customer_id,
                customer_name=customer_name,
                account_id=account.id,
                account_name=account.name or account.type.value,
                iban=account.iban,
                currency=account.currency,
                type=account.type.value,
            )
        )
    return SimulationParticipantsResponse(participants=rows)


def _default_participant_targets(
    container: ContainerDep, *, per_bank_limit: int = 12, total_limit: int = 200
) -> list[tuple[str, str]]:
    """Return a capped default target set when no explicit simulator targets exist."""
    targets: list[tuple[str, str]] = []
    for bank in container.bank_service.list_banks():
        if len(targets) >= total_limit:
            break
        accounts = container.banking.list_accounts(bank.id, limit=per_bank_limit)
        for account in accounts:
            if len(targets) >= total_limit:
                break
            if account.customer_id and not account.is_internal:
                targets.append((bank.id, account.id))
    return targets


@router.get("", response_model=SimulationStatusResponse, summary="Get simulation status")
def get_status(container: ContainerDep) -> SimulationStatusResponse:
    """Return whether the live simulator is running, its cadence and counters."""
    return SimulationStatusResponse(**container.simulation.status())


@router.post(
    "/start",
    response_model=SimulationStatusResponse,
    summary="Start or reconfigure the live simulation",
)
async def start(
    body: SimulationStartRequest, container: ContainerDep
) -> SimulationStatusResponse:
    """Start the server-side simulator (or update its cadence/participating accounts).

    ``avg_seconds`` is the average gap between transactions; ``targets`` lists the bank/account
    pairs that should receive simulated activity. The simulator runs independently of any browser.
    """
    targets = [(t.bank_id, t.account_id) for t in body.targets]
    await container.simulation.start(body.avg_seconds, targets)
    return SimulationStatusResponse(**container.simulation.status())


@router.post(
    "/stop", response_model=SimulationStatusResponse, summary="Stop the live simulation"
)
async def stop(container: ContainerDep) -> SimulationStatusResponse:
    """Stop the server-side simulator. The rolling feed of past transactions is retained."""
    await container.simulation.stop()
    return SimulationStatusResponse(**container.simulation.status())


@router.get(
    "/feed",
    response_model=SimulationFeedResponse,
    summary="Poll recent live transactions",
)
def feed(
    container: ContainerDep,
    after: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200),
) -> SimulationFeedResponse:
    """Return live transactions with ``seq > after`` (oldest first), capped to the last 200."""
    data = container.simulation.feed(after=after, limit=limit)
    return SimulationFeedResponse(
        running=data["running"],
        generated=data["generated"],
        last_seq=data["last_seq"],
        events=[SimulationEventResponse(**e) for e in data["events"]],
    )
