from __future__ import annotations

from recon.domain.graph.constraint import ConstraintRule


CONSTRAINT_RULES = (
    ConstraintRule(
        constraint_code="ORDER_AMOUNT_MATCH",
        description="Merchant order amount must match Razorpay order amount.",
    ),
    ConstraintRule(
        constraint_code="ORDER_CURRENCY_MATCH",
        description="Merchant order currency must match Razorpay order currency.",
    ),
    ConstraintRule(
        constraint_code="PAYMENT_AMOUNT_MATCH",
        description="Payment amount must match the associated order.",
    ),
    ConstraintRule(
        constraint_code="PAYMENT_CAPTURED",
        description="Payment must be captured before settlement.",
    ),
    ConstraintRule(
        constraint_code="REFUND_PROCESSED",
        description="Refund must be processed before being treated as completed.",
    ),
    ConstraintRule(
        constraint_code="SETTLEMENT_PROCESSED",
        description="Settlement must be processed before settlement reconciliation.",
    ),
    ConstraintRule(
        constraint_code="TEMPORAL_ORDER",
        description="Related financial events must occur in a valid chronological order.",
    ),
    ConstraintRule(
        constraint_code="LEDGER_BALANCE",
        description="Merchant ledger values must agree with the expected transaction.",
    ),
    ConstraintRule(
        constraint_code="BANK_BALANCE",
        description="Observed bank credit must agree with the settlement.",
    ),
    ConstraintRule(
        constraint_code="ENTITY_COMPLETENESS",
        description="Expected related entities must exist exactly once.",
    ),
)