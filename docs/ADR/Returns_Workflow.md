### Use Case: Process Return and Refund (RMA)

**Primary actor:** Customer  
**Supporting actors:** Store Admin, Payment Provider (mock), Inventory System

**Main success scenario:**
1. Customer opens "Order History" and selects a completed order.
2. Customer clicks "Request Return", selects one or more items and a reason.
3. System creates a `ReturnRequest` with status `PENDING_AUTHORIZATION`.
4. Store Admin reviews the RMA in an admin UI and either:
   - Approves it → status becomes `AUTHORIZED`, RMA number shown to customer.
   - Rejects it → status becomes `REJECTED`, process ends.
5. If approved, the customer ships the items back with the RMA number.
6. Admin records shipment details → `ReturnShipment` created (`IN_TRANSIT`).
7. When items arrive, admin marks as received → `ReturnRequest` status `RECEIVED`.
8. Warehouse/quality inspector performs inspection:
   - Records `Inspection` with result (`APPROVED`/`REJECTED`).
   - Status moves to `APPROVED` or `REJECTED`.
9. If approved, system calculates eligible refund amount and creates a `Refund` with status `PENDING`.
10. System calls the `PaymentService` refund operation using the original `Payment` reference.
11. On success, `Refund` moves to `COMPLETED`, `ReturnRequest` moves to `REFUNDED`, and inventory is updated (stock incremented).
12. Customer sees refund confirmation in UI and the updated refund status on the order page.

**Extensions (error / alternative flows):**
- 3a. Customer tries to request a return after the allowed window → system immediately sets status `REJECTED` with reason "Out of return window".
- 4a. Admin partially approves (e.g., some items only) → `Inspection.result = PARTIALLY_APPROVED` and refund amount is adjusted.
- 10a. Payment refund fails (mock simulates failure) → `Refund.status = FAILED`, error is logged and admin is notified to retry or process manually.


### Services and Responsibilities (Returns & Refunds)

- `ReturnsService`
  - Create and validate return requests.
  - Enforce policy rules (return window, max quantity, etc.).
  - Manage status transitions for:
    - `PENDING_AUTHORIZATION` → `AUTHORIZED` / `REJECTED`
    - `AUTHORIZED` → `IN_TRANSIT` → `RECEIVED` → `UNDER_INSPECTION` → `APPROVED`/`REJECTED`
  - Coordinate with `InventoryService` when items are approved and refunded.

- `RefundService`
  - Given an approved `ReturnRequest`, calculate refund amount.
  - Call `PaymentService` to trigger the refund against the original `Payment`.
  - Update `Refund` entity and final status of the `ReturnRequest`.

- `PaymentService` (existing, extended)
  - Expose `refund(payment_id, amount)` alongside existing `charge(...)`.
  - Reuse circuit breaker, retries, and other quality tactics.

- `InventoryService` (existing)
  - When a return is approved and refunded, adjust inventory:
    - Increase on-hand stock for returned items.
    - Optionally log a `StockMovement` entry with type `RETURNED`.
