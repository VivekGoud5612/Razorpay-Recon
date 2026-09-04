-- merchant_orders.razorpay_order_id had a hard FK to razorpay_orders(order_id),
-- which made it impossible to ever ingest a merchant order referencing a
-- Razorpay order that doesn't exist -- i.e. it made the RAZORPAY_ORDER_NOT_FOUND
-- finding in ReconcileSettlementService structurally unreachable, since the
-- offending row could never be persisted in the first place. A merchant's
-- own submitted data should never be constrained to only reference records
-- Razorpay already recognizes -- detecting the mismatch is reconciliation's
-- job, not the ingestion boundary's. Column stays NOT NULL; only the FK is
-- dropped.

ALTER TABLE merchant_orders
    DROP CONSTRAINT merchant_orders_razorpay_order_id_fkey;
