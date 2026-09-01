# BankSym

A general, multi-tenant **test bank framework**. Spin up simulated banks — each with its own
branding, country, locale, enabled protocols, and synthetic customers — to develop and test
integrations against (PSD2 / Berlin Group first, more protocols pluggable).

## Architecture

One stable **core banking** capability is the single domain of record. Everything else is a
pluggable capability behind a strong interface. Dependencies point **inward only**: plugins depend
on `CoreBankingService`; core never imports a plugin. State is persisted via SQLAlchemy (SQLite by
default), so banks, customers, accounts and transactions survive restarts.

```
banksym/
  core/            # the only stateful domain of record
    kernel/        # money, ids, errors, capability registry base
    domain/        # Customer, Account, Balance, Ledger, TransactionHistory
    service/       # CoreBankingService — the single public interface plugins use
  tenancy/         # Bank (tenant): branding, country, locale, enabled capabilities
  capabilities/    # pluggable capabilities (each: interface + registry + impls)
    protocols/     # ProtocolAdapter (Berlin Group XS2A: AIS + PIS; Open Finance)
    auth/          # AuthProvider / ScaProvider (simple password, auto-approve SCA)
    txgen/         # TransactionGenerator (rule-based, persona-driven) + persona catalog
    localization/  # LocalizationProvider (country packs: DE/ES/FR/GB/NL)
    settlement/    # SettlementEngine (RTGS, netting, inter-bank)
  persistence/     # SQLAlchemy models + repositories backing the core & tenancy stores
  simulation.py    # Server-side live transaction simulator (rolling feed)
  settings.py      # Runtime settings (database URL, etc.)
  api/             # FastAPI app + admin/instantiation API
ui/                # Self-contained HTML: architecture map (/) + bank builder (/builder)
```

## APIs

Two protocol adapters ship today, both serving the same core bank:

| Adapter | Prefix | Shape |
|---|---|---|
| `berlin_group` | `/xs2a/{bank_id}/v1` | PSD2 NextGenPSD2: IBANs, consent resources, SCA |
| `open_finance` | `/openfinance/{bank_id}/v1` | US account aggregation: opaque ids and masks, credit cards first-class, enriched transactions |

They are separate adapters rather than one parameterised surface because an
integration written against one genuinely will not work against the other. Open
Finance exposes:

```
GET /openfinance/{bank_id}/v1/institution
GET /openfinance/{bank_id}/v1/customers
GET /openfinance/{bank_id}/v1/customers/{customer_id}/accounts
GET /openfinance/{bank_id}/v1/accounts/{account_id}
GET /openfinance/{bank_id}/v1/accounts/{account_id}/transactions?fromDate=&toDate=
```

All endpoints require `Authorization: Bearer <token>`. Any token is accepted — this
is a test bank, and rejecting tokens would only obstruct the integrations it exists
to support — but the header is required so client code carries credentials the way
it would against a real aggregator.

### Importing a fixture history

`POST /banks/{bank_id}/transactions/import` bulk-loads a dated, categorised history
across many accounts. Entries can be back-dated and carry
`merchant_name` / `category` / `channel` / `location`, so an imported history is
indistinguishable from a generated one when read back through a protocol adapter.
Overdrafts are permitted during import, since a replayed history arrives out of
reach of its own funding entries and a credit card is legitimately negative.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
uvicorn banksym.api.app:app --reload
```

Open http://127.0.0.1:8000/docs for the API.

## Run scripts

Cross-platform helper scripts create the virtual environment, install dependencies, and
start/stop the server (guarding against double-starts via a PID file).

**Windows (PowerShell):**

```powershell
.\run.ps1 start     # create venv, install deps, start server (if not already running)
.\run.ps1 status
.\run.ps1 restart
.\run.ps1 stop
```

**macOS / Linux:**

```bash
chmod +x run.sh     # first time only
./run.sh start
./run.sh status
./run.sh restart
./run.sh stop
```

Override host/port with the `BANKSYM_HOST` and `BANKSYM_PORT` environment variables. Server logs
are written to `banksym.log`.
