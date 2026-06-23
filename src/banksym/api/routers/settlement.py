"""Per-bank settlement administration: trigger the deferred settlement cycle."""

from __future__ import annotations

from fastapi import APIRouter

from banksym.api.deps import BankIdDep, ContainerDep
from banksym.api.schemas import SettlementCycleResponse, SettlementCycleResult

router = APIRouter(prefix="/banks/{bank_id}/settlement", tags=["settlement"])


@router.post(
    "/run-cycle", response_model=SettlementCycleResponse, summary="Run the settlement cycle"
)
def run_cycle(bank_id: BankIdDep, container: ContainerDep) -> SettlementCycleResponse:
    """Run the bank's deferred settlement cycle and reconcile pending payments.

    For immediate engines (e.g. RTGS) this is a no-op returning an empty list; for deferred engines
    (e.g. netting) it sweeps net positions and promotes accepted payments to settled.
    """
    results = container.run_settlement_cycle(bank_id)
    return SettlementCycleResponse(
        settled=[
            SettlementCycleResult(
                instruction_id=r.instruction_id,
                status=r.status.value,
                journal_id=r.journal_id,
                detail=r.detail,
            )
            for r in results
        ]
    )
