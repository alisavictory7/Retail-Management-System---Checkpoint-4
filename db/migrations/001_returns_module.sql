-- Migration 001: Introduce Returns & Refunds tables
-- Run after applying CP2 schema (db/init.sql) to upgrade to CP3 requirements.

BEGIN;

CREATE TABLE IF NOT EXISTS "ReturnRequest" (
    "returnRequestID" SERIAL PRIMARY KEY,
    "saleID" INTEGER NOT NULL REFERENCES "Sale"("saleID"),
    "customerID" INTEGER NOT NULL REFERENCES "User"("userID"),
    "status" VARCHAR(40) NOT NULL DEFAULT 'PENDING_AUTHORIZATION',
    "reason" VARCHAR(40) NOT NULL,
    "details" TEXT,
    "photos_url" VARCHAR(512),
    "rma_number" VARCHAR(50) UNIQUE,
    "decision_notes" TEXT,
    "policy_window_days" INTEGER DEFAULT 30,
    "created_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT "chk_return_status" CHECK ("status" IN (
        'PENDING_CUSTOMER_INFO','PENDING_AUTHORIZATION','AUTHORIZED','IN_TRANSIT',
        'RECEIVED','UNDER_INSPECTION','APPROVED','REJECTED','REFUNDED','CANCELLED'
    )),
    CONSTRAINT "chk_return_reason" CHECK ("reason" IN ('DAMAGED','WRONG_ITEM','NOT_AS_DESCRIBED','OTHER'))
);

CREATE TABLE IF NOT EXISTS "ReturnItem" (
    "returnItemID" SERIAL PRIMARY KEY,
    "returnRequestID" INTEGER NOT NULL REFERENCES "ReturnRequest"("returnRequestID") ON DELETE CASCADE,
    "saleItemID" INTEGER NOT NULL REFERENCES "SaleItem"("saleItemID"),
    "quantity" INTEGER NOT NULL,
    "condition_report" TEXT,
    "restocking_fee" DECIMAL(10, 2) DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS "ReturnShipment" (
    "shipmentID" SERIAL PRIMARY KEY,
    "returnRequestID" INTEGER NOT NULL REFERENCES "ReturnRequest"("returnRequestID") ON DELETE CASCADE,
    "carrier" VARCHAR(120),
    "tracking_number" VARCHAR(120),
    "shipped_at" TIMESTAMP WITH TIME ZONE,
    "received_at" TIMESTAMP WITH TIME ZONE,
    "notes" TEXT
);

CREATE TABLE IF NOT EXISTS "Inspection" (
    "inspectionID" SERIAL PRIMARY KEY,
    "returnRequestID" INTEGER NOT NULL REFERENCES "ReturnRequest"("returnRequestID") ON DELETE CASCADE,
    "inspected_by" VARCHAR(120),
    "inspected_at" TIMESTAMP WITH TIME ZONE,
    "result" VARCHAR(40) NOT NULL DEFAULT 'PENDING',
    "notes" TEXT,
    CONSTRAINT "chk_inspection_result" CHECK ("result" IN ('PENDING','APPROVED','PARTIALLY_APPROVED','REJECTED'))
);

CREATE TABLE IF NOT EXISTS "Refund" (
    "refundID" SERIAL PRIMARY KEY,
    "returnRequestID" INTEGER NOT NULL REFERENCES "ReturnRequest"("returnRequestID") ON DELETE CASCADE,
    "paymentID" INTEGER NOT NULL REFERENCES "Payment"("paymentID"),
    "amount" DECIMAL(10, 2) NOT NULL,
    "method" VARCHAR(40) NOT NULL,
    "status" VARCHAR(40) NOT NULL DEFAULT 'PENDING',
    "failure_reason" VARCHAR(255),
    "created_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "processed_at" TIMESTAMP WITH TIME ZONE,
    "external_reference" VARCHAR(120),
    CONSTRAINT "chk_refund_method" CHECK ("method" IN ('CARD','CASH','STORE_CREDIT','ORIGINAL_METHOD')),
    CONSTRAINT "chk_refund_status" CHECK ("status" IN ('PENDING','PROCESSING','COMPLETED','FAILED'))
);

CREATE INDEX IF NOT EXISTS "idx_returnrequest_status" ON "ReturnRequest"("status", "created_at");
CREATE INDEX IF NOT EXISTS "idx_returnrequest_customer" ON "ReturnRequest"("customerID", "status");
CREATE INDEX IF NOT EXISTS "idx_returnitem_request" ON "ReturnItem"("returnRequestID");
CREATE INDEX IF NOT EXISTS "idx_refund_status" ON "Refund"("status");

COMMIT;

