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
    """Return metadata for all real customer-linked accounts across all banks.

    The Live page uses this as the source of truth for selectable participants, so it should
    reflect newly created manual and batch accounts immediately rather than only existing
    simulator targets.
    """
    rows: list[SimulationParticipantResponse] = []
    for bank in container.bank_service.list_banks():
        try:
            accounts = container.banking.list_accounts(bank.id)
        except Exception:
            continue

        for account in accounts:
            if account.is_internal or not account.customer_id:
                continue

            customer_id = account.customer_id
            customer_name = ""
            customer_source = "manual"
            try:
                customer = container.banking.get_customer(bank.id, customer_id)
                customer_name = customer.full_name
                customer_source = customer.source or "manual"
            except Exception:
                customer_name = customer_id

            rows.append(
                SimulationParticipantResponse(
                    bank_id=bank.id,
                    bank_name=bank.branding.display_name,
                    bank_color=bank.branding.primary_color,
                    country=bank.country,
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_source=customer_source,
                    account_id=account.id,
                    account_name=account.name or account.type.value,
                    iban=account.iban,
                    currency=account.currency,
                    type=account.type.value,
                )
            )

    return SimulationParticipantsResponse(participants=rows)


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
