-- Seed script to create a reusable Returns & Refunds walkthrough.
-- It removes any previous demo data identified by RMA-CP3-DEMO-001 and recreates it.

BEGIN;

DELETE FROM "Refund"
WHERE "returnRequestID" IN (
    SELECT "returnRequestID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "ReturnShipment"
WHERE "returnRequestID" IN (
    SELECT "returnRequestID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "Inspection"
WHERE "returnRequestID" IN (
    SELECT "returnRequestID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "ReturnItem"
WHERE "returnRequestID" IN (
    SELECT "returnRequestID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "SaleItem"
WHERE "saleID" IN (
    SELECT "saleID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "Payment"
WHERE "saleID" IN (
    SELECT "saleID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "Sale"
WHERE "saleID" IN (
    SELECT "saleID" FROM "ReturnRequest" WHERE "rma_number" = 'RMA-CP3-DEMO-001'
);

DELETE FROM "ReturnRequest"
WHERE "rma_number" = 'RMA-CP3-DEMO-001';

WITH demo_sale AS (
    INSERT INTO "Sale" ("userID", "sale_date", "totalAmount", "status")
    VALUES (1, NOW() - INTERVAL '5 days', 1110.00, 'completed')
    RETURNING "saleID"
),
demo_item AS (
    INSERT INTO "SaleItem" ("saleID", "productID", "quantity", "original_unit_price", "discount_applied", "final_unit_price", "shipping_fee_applied", "import_duty_applied", "subtotal")
    SELECT "saleID", 1, 1, 1200.00, 120.00, 1080.00, 20.00, 10.00, 1110.00
    FROM demo_sale
    RETURNING "saleItemID", "saleID"
),
demo_payment AS (
    INSERT INTO "Payment" ("saleID", "payment_date", "amount", "status", "payment_type", "card_number", "card_type", "card_exp_date", "type")
    SELECT "saleID", NOW() - INTERVAL '5 days', 1110.00, 'completed', 'card', '4242424242424242', 'VISA', '12/2030', 'card'
    FROM demo_sale
    RETURNING "paymentID", "saleID"
),
demo_return AS (
    INSERT INTO "ReturnRequest" ("saleID", "customerID", "status", "reason", "details", "photos_url", "rma_number", "decision_notes", "policy_window_days", "created_at", "updated_at")
    SELECT "saleID", 1, 'AUTHORIZED', 'DAMAGED', 'Screen flickers intermittently', 'https://example.com/photos/rma-demo', 'RMA-CP3-DEMO-001', NULL, 30, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
    FROM demo_sale
    RETURNING "returnRequestID", "saleID"
),
demo_return_item AS (
    INSERT INTO "ReturnItem" ("returnRequestID", "saleItemID", "quantity", "condition_report", "restocking_fee")
    SELECT demo_return."returnRequestID", demo_item."saleItemID", 1, 'Visual inspection pending', 0.00
    FROM demo_return
    JOIN demo_item ON demo_item."saleID" = demo_return."saleID"
),
demo_shipment AS (
    INSERT INTO "ReturnShipment" ("returnRequestID", "carrier", "tracking_number", "shipped_at", "received_at", "notes")
    SELECT "returnRequestID", 'DHL', 'RMA123456789', NOW() - INTERVAL '1 day', NULL, 'Customer provided drop-off receipt'
    FROM demo_return
),
demo_inspection AS (
    INSERT INTO "Inspection" ("returnRequestID", "inspected_by", "inspected_at", "result", "notes")
    SELECT "returnRequestID", NULL, NULL, 'PENDING', 'Awaiting warehouse processing'
    FROM demo_return
)
INSERT INTO "Refund" ("returnRequestID", "paymentID", "amount", "method", "status", "failure_reason", "created_at", "processed_at", "external_reference")
SELECT demo_return."returnRequestID", demo_payment."paymentID", 1110.00, 'CARD', 'PENDING', NULL, NOW() - INTERVAL '1 day', NULL, 'REF-CP3-DEMO'
FROM demo_return
JOIN demo_payment ON demo_payment."saleID" = demo_return."saleID";

COMMIT;

