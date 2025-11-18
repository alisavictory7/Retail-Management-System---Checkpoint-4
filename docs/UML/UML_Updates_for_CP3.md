## 3. Logical View – Returns & Refunds Additions

**New domain classes:**
- `ReturnRequest`
- `ReturnItem`
- `ReturnShipment`
- `Inspection`
- `Refund`

**New service classes:**
- `ReturnsService`
- `RefundService`

**Updated classes/services:**
- `PaymentService` – add refund operation, reuse circuit breaker and retry tactics.
- `InventoryService` – add method to handle stock adjustments triggered by approved returns.

**Key relationships:**
- `Sale` 1..* → `SaleItem`
- `Sale` 0..* → `ReturnRequest`
- `ReturnRequest` 1..* → `ReturnItem`
- `ReturnRequest` 0..1 → `ReturnShipment`
- `ReturnRequest` 0..1 → `Inspection`
- `ReturnRequest` 0..1 → `Refund`



## 4. Process View – RMA Processing Sequence

1. `Customer` → `Flask Router` → `ReturnsController.request_return(order_id, items, reason)`
2. `ReturnsController` → `ReturnsService.create_return_request(...)`
3. `ReturnsService` → `SaleRepository` to validate order existence and ownership.
4. `ReturnsService` → `ReturnRequestRepository` to persist the new RMA.
5. Admin approves RMA via `AdminReturnsController.authorize_return(return_id)`.
6. `AdminReturnsController` → `ReturnsService.authorize_return(return_id)`.
7. Once inspection is done, admin triggers refund via `AdminReturnsController.approve_return(return_id)`.
8. `ReturnsService` → `RefundService.process_refund(return_id)`.
9. `RefundService` → `PaymentService.refund(payment_id, amount)` (with circuit breaker + retries).
10. `PaymentService` returns success/failure.
11. `RefundService` updates `Refund` status and calls `InventoryService.apply_return_stock(return_id)`.
12. `InventoryService` updates stock levels and logs `StockMovement`.
13. `ReturnsService` updates `ReturnRequest` status to `REFUNDED` on successful refund.



## 5. Deployment View – Checkpoint 3

**Runtime nodes:**
- `web-app` container
  - Flask application
  - Business services: `ReturnsService`, `RefundService`, `PaymentService`, `InventoryService`, etc.
- `db` container
  - PostgreSQL database hosting all tables, including new RMA and refund tables.
- (Optional) `worker` container
  - Background processing for long-running tasks (e.g., async refunds or email notifications).
- (Optional) `monitoring` component (logical)
  - In practice, observability is implemented inside `web-app` as:
    - `/admin/dashboard` UI
    - `/admin/metrics` endpoint

**Deployment decisions (planned):**
- All containers orchestrated via `docker-compose` in a local network.
- App exposes HTTP port 5000 on the host.
- Logs emitted to stdout in structured format for easy collection via `docker compose logs`.



## 6. Observability Architecture (Implemented)

**Logging:**
- Implemented in `src/observability/logging_config.py` and wired in `src/main.py`.
- JSON output with fields: `timestamp`, `level`, `logger`, `request_id`, `path`, `method`, `user_id`.
- Key business events captured via `record_event(...)` (returns created, refund completed/failed, throttling notices).

**Metrics:**
- `src/observability/metrics.py` tracks counters such as `http_requests_total`, `returns_created_total`, `refunds_completed_total`, and latency histograms for every endpoint.
- `/admin/metrics` returns a JSON snapshot consumed by the dashboard or external tooling.

**Monitoring & Dashboard:**
- `/admin/dashboard` (Tailwind template) visualizes DB health, return/refund KPIs, refund success rate, and the HTTP latency table.
- `/health` exposes readiness/liveness status for Docker health checks.
- Scenarios can be replayed and evidenced entirely with the dashboard + metrics JSON.
