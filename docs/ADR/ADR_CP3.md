# ADR 0001 – Introduce Returns & Refunds Module

## Status
Accepted

## Context
The existing retail management system (Checkpoint 2) supports product catalog, sales, payments, inventory, flash sales, and partner integrations. However, it does not support returns (RMA) or refunds, which are core to a realistic retail system and required for Checkpoint 3.

## Decision
We introduce a dedicated Returns & Refunds module with the following key elements (implemented in `src/models.py`, `src/services/returns_service.py`, `src/services/refund_service.py`, and the Flask blueprints/templates):
- New domain entities: `ReturnRequest`, `ReturnItem`, `ReturnShipment`, `Inspection`, and `Refund`.
- New services: `ReturnsService` and `RefundService`.
- Extension of `PaymentService` to support refunds using the original payment reference.
- Controlled status lifecycles for return requests and refunds.

## Consequences
- **Positive:**
  - Clear separation of concerns between purchase flow and return flow.
  - Easier to reason about return policies and lifecycle transitions.
  - Foundation for observability metrics around returns and refunds.
- **Negative:**
  - Additional complexity in the domain model and database schema.
  - More test cases required to cover new flows and edge cases.



# ADR 0002 – Docker and docker-compose Deployment

## Status
Accepted

## Context
Checkpoint 3 requires the system to be deployable using containers. Currently, the application is started directly on the host using a virtual environment and a local PostgreSQL instance.

## Decision
We containerized the system with:
- `Dockerfile` (Python 3.12 slim + Gunicorn) building the Flask app.
- `docker-compose.yml` orchestrating `web` and `db` services, wiring `.env`, health checks, and auto-running `db/init.sql`, the returns migration, and demo seed scripts.
- `docker/entrypoint.sh` + `docker/wait_for_db.py` ensuring the web container waits for Postgres before launching Gunicorn.

## Consequences
- **Positive:**
  - Reproducible, environment-independent setup for the project reviewers.
  - Better alignment with real-world deployment patterns.
  - Easier to add future services (e.g., worker, cache) to the compose file.
- **Negative:**
  - Additional complexity for configuration management (environment variables, container networking).
  - Requires Docker tooling to be installed for local development.




# ADR 0003 – Centralized Logging and Metrics

## Status
Accepted

## Context
The system currently logs basic information to the console, but Checkpoint 3 requires explicit observability: structured logs, metrics, and a way for administrators to inspect system health and behavior.

## Decision
We implemented an observability module (`src/observability/`) that:
- Configures JSON logging with request IDs via Flask middleware.
- Tracks counters/histograms/events and exposes them through `/admin/metrics`.
- Adds `/health` and `/admin/dashboard` (Tailwind UI) so admins can inspect DB status, request latency, returns/refund KPIs, and recent business events.

## Consequences
- **Positive:**
  - Easier debugging through correlated logs.
  - Direct support for quality scenario verification using runtime metrics.
  - Clear separation between application logic and observability concerns.
- **Negative:**
  - Slight performance overhead due to metrics tracking.
  - More moving parts to maintain (logging configuration, metrics module, dashboard UI).
