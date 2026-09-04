from __future__ import annotations

from decimal import Decimal

from recon.application.reconciliation.dto.data import SettlementReconciliationData
from recon.application.reconciliation.dto.response import ReconcileSettlementResponse
from recon.domain.graph.entity import EntityReference
from recon.domain.reconciliation.evidence import EvidenceRef    
from recon.domain.reconciliation.finding import ReconciliationFinding


class ReconcileSettlementService:

    def reconcile(
        self,
        data: SettlementReconciliationData,
    ) -> ReconcileSettlementResponse:

        if data.settlement.status != "processed":
            return self._pre_settlement_response(data)

        findings = (
            self._validate_razorpay_state(data)
            + self._validate_orders(data)
            + self._validate_payments(data)
            + self._validate_merchant_sources(data)
            + self._validate_temporal(data)
            + self._validate_completeness(data)
            + self._validate_settlement(data)
        )

        evidence = self._extract_evidence(findings)

        razorpay_net = self._calculate_razorpay_net(data)
        merchant_expected = self._calculate_merchant_expected(data.ledger_entries)
        bank_observed = self._calculate_bank_observed(data.bank_transactions)

        merchant_vs_razorpay_difference = merchant_expected - razorpay_net
        razorpay_vs_bank_difference = razorpay_net - bank_observed

        if findings:
            status = "exception"
            reason_code = self._get_reason_code(findings)
        elif (
            merchant_vs_razorpay_difference == Decimal("0")
            and razorpay_vs_bank_difference == Decimal("0")
        ):
            status = "reconciled"
            reason_code = "ALL_SOURCES_AGREE"
        else:
            status = "exception"
            reason_code = "FINANCIAL_DIFFERENCE"

        return ReconcileSettlementResponse(
            settlement_id=data.settlement.settlement_id,
            merchant_expected=merchant_expected,
            razorpay_net=razorpay_net,
            bank_observed=bank_observed,
            merchant_vs_razorpay_difference=merchant_vs_razorpay_difference,
            razorpay_vs_bank_difference=razorpay_vs_bank_difference,
            status=status,
            reason_code=reason_code,
            findings=findings,
            evidence=evidence,
        )

    @staticmethod
    def _pre_settlement_response(
        data: SettlementReconciliationData,
    ) -> ReconcileSettlementResponse:
        merchant_expected = ReconcileSettlementService._calculate_merchant_expected(
            data.ledger_entries
        )

        return ReconcileSettlementResponse(
            settlement_id=data.settlement.settlement_id,
            merchant_expected=merchant_expected,
            razorpay_net=Decimal("0"),
            bank_observed=Decimal("0"),
            merchant_vs_razorpay_difference=Decimal("0"),
            razorpay_vs_bank_difference=Decimal("0"),
            status="pending",
            reason_code="AWAITING_SETTLEMENT",
            findings=[],
            evidence=[],
        )

    @staticmethod
    def _finding(
        code: str,
        severity: str,
        entity: EntityReference,
        message: str,
        evidence: list[EvidenceRef],
    ) -> ReconciliationFinding:
        return ReconciliationFinding(
            finding_id=f"{code}:{entity.entity_type}:{entity.entity_id}",
            code=code,
            severity=severity,
            affected_entity=entity,
            message=message,
            evidence=evidence,
        )

    @staticmethod
    def _entity(
        source: str,
        entity_type: str,
        entity_id: str,
    ) -> EntityReference:
        return EntityReference(
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    @staticmethod
    def _evidence(
        source: str,
        entity_type: str,
        entity_id: str,
        reason: str,
        object_key: str | None = None,
    ) -> EvidenceRef:
        return EvidenceRef(
            evidence_id=f"ev:{source}:{entity_type}:{entity_id}:{reason}",
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            object_key=object_key,
        )

    @staticmethod
    def _object_key(
        data: SettlementReconciliationData,
        entity_type: str,
        entity_id: str,
    ) -> str | None:
        import_id = data.entity_imports.get((entity_type, entity_id))

        if import_id is None:
            return None

        return data.object_keys.get(import_id)

    @staticmethod
    def _validate_razorpay_state(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        payments = {x.payment_id: x for x in data.payments}
        refunds = {x.refund_id: x for x in data.refunds}
        transfers = {x.transfer_id: x for x in data.transfers}
        adjustments = {x.adjustment_id: x for x in data.adjustments}
        orders = {x.order_id: x for x in data.orders}

        for entry in data.settlement_entries:

            if entry.order_id and entry.order_id not in orders:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=f"Order not found: {entry.order_id}",
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "ORDER_NOT_FOUND",
                            ),
                        ],
                    )
                )

            if entry.payment_id:
                payment = payments.get(entry.payment_id)

                if payment is None:
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="PAYMENT_NOT_FOUND",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                            ),
                            message=f"Payment not found: {entry.payment_id}",
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement_entry",
                                    entry.entry_id,
                                    "PAYMENT_NOT_FOUND",
                                ),
                            ],
                        )
                    )

                elif payment.status not in {"captured", "refunded"}:
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="PAYMENT_NOT_CAPTURED",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                            ),
                            message=(
                                f"Payment {entry.payment_id} "
                                f"is not settled: {payment.status}"
                            ),
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "payment",
                                    payment.payment_id,
                                    "PAYMENT_NOT_CAPTURED",
                                ),
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement_entry",
                                    entry.entry_id,
                                    "PAYMENT_NOT_CAPTURED",
                                ),
                            ],
                        )
                    )

            if entry.refund_id:
                refund = refunds.get(entry.refund_id)

                if refund is None:
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="REFUND_NOT_FOUND",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                            ),
                            message=f"Refund not found: {entry.refund_id}",
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement_entry",
                                    entry.entry_id,
                                    "REFUND_NOT_FOUND",
                                ),
                            ],
                        )
                    )

                elif refund.status != "processed":
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="REFUND_NOT_PROCESSED",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "refund",
                                refund.refund_id,
                            ),
                            message=(
                                f"Refund {entry.refund_id} "
                                f"is not processed: {refund.status}"
                            ),
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "refund",
                                    refund.refund_id,
                                    "REFUND_NOT_PROCESSED",
                                ),
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement_entry",
                                    entry.entry_id,
                                    "REFUND_NOT_PROCESSED",
                                ),
                            ],
                        )
                    )

            if entry.transfer_id and entry.transfer_id not in transfers:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="TRANSFER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=f"Transfer not found: {entry.transfer_id}",
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "TRANSFER_NOT_FOUND",
                            ),
                        ],
                    )
                )

            if entry.adjustment_id and entry.adjustment_id not in adjustments:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="ADJUSTMENT_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=f"Adjustment not found: {entry.adjustment_id}",
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "ADJUSTMENT_NOT_FOUND",
                            ),
                        ],
                    )
                )

        return findings

    @staticmethod
    def _validate_orders(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        razorpay_orders = {
            x.order_id: x
            for x in data.orders
        }

        seen_orders: dict[str, int] = {}

        for merchant_order in data.merchant_orders:
            seen_orders[merchant_order.order_id] = (
                seen_orders.get(merchant_order.order_id, 0) + 1
            )

            razorpay_order = razorpay_orders.get(
                merchant_order.razorpay_order_id
            )

            if razorpay_order is None:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="RAZORPAY_ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "merchant_order",
                            merchant_order.order_id,
                        ),
                        message=(
                            f"Razorpay order not found: "
                            f"{merchant_order.razorpay_order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "merchant_order",
                                merchant_order.order_id,
                                "RAZORPAY_ORDER_NOT_FOUND",
                                ReconcileSettlementService._object_key(data, "merchant_order", merchant_order.order_id),
                            ),
                        ],
                    )
                )
                continue

            if merchant_order.amount != razorpay_order.amount:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="ORDER_AMOUNT_MISMATCH",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "merchant_order",
                            merchant_order.order_id,
                        ),
                        message=(
                            f"Amount mismatch for "
                            f"{merchant_order.order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "merchant_order",
                                merchant_order.order_id,
                                "ORDER_AMOUNT_MISMATCH",
                                ReconcileSettlementService._object_key(data, "merchant_order", merchant_order.order_id),
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                razorpay_order.order_id,
                                "ORDER_AMOUNT_MISMATCH",
                            ),
                        ],
                    )
                )

            if merchant_order.currency != razorpay_order.currency:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="ORDER_CURRENCY_MISMATCH",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "merchant_order",
                            merchant_order.order_id,
                        ),
                        message=(
                            f"Currency mismatch for "
                            f"{merchant_order.order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "merchant_order",
                                merchant_order.order_id,
                                "ORDER_CURRENCY_MISMATCH",
                                ReconcileSettlementService._object_key(data, "merchant_order", merchant_order.order_id),
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                razorpay_order.order_id,
                                "ORDER_CURRENCY_MISMATCH",
                            ),
                        ],
                    )
                )

        for merchant_order_id, count in seen_orders.items():
            if count <= 1:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="DUPLICATE_MERCHANT_ORDER",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "merchant",
                        "merchant_order",
                        merchant_order_id,
                    ),
                    message=(
                        f"Merchant order appears {count} times: "
                        f"{merchant_order_id}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            "merchant_order",
                            merchant_order_id,
                            "DUPLICATE_MERCHANT_ORDER",
                            ReconcileSettlementService._object_key(data, "merchant_order", merchant_order_id),
                        ),
                    ],
                )
            )

        return findings

    @staticmethod
    def _validate_payments(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        orders = {
            x.order_id: x
            for x in data.orders
        }

        for payment in data.payments:

            if payment.order_id is None:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_ORDER_MISSING",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=f"Payment has no order: {payment.payment_id}",
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "PAYMENT_ORDER_MISSING",
                            ),
                        ],
                    )
                )
                continue

            order = orders.get(payment.order_id)

            if order is None:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=(
                            f"Payment {payment.payment_id} "
                            f"references missing order {payment.order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "PAYMENT_ORDER_NOT_FOUND",
                            ),
                        ],
                    )
                )
                continue

            if payment.amount != order.amount:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_AMOUNT_MISMATCH",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=(
                            f"Payment amount mismatch: "
                            f"{payment.payment_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "PAYMENT_AMOUNT_MISMATCH",
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                order.order_id,
                                "PAYMENT_AMOUNT_MISMATCH",
                            ),
                        ],
                    )
                )

            if payment.currency != order.currency:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_CURRENCY_MISMATCH",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=(
                            f"Payment currency mismatch: "
                            f"{payment.payment_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "PAYMENT_CURRENCY_MISMATCH",
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                order.order_id,
                                "PAYMENT_CURRENCY_MISMATCH",
                            ),
                        ],
                    )
                )

        return findings

    @staticmethod
    def _validate_merchant_sources(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        merchant_orders = {
            x.order_id: x
            for x in data.merchant_orders
        }

        for ledger in data.ledger_entries:
            if ledger.merchant_order_id not in merchant_orders:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="LEDGER_ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "ledger_entry",
                            ledger.entry_id,
                        ),
                        message=(
                            f"Ledger entry {ledger.entry_id} "
                            f"references unknown merchant order"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "ledger_entry",
                                ledger.entry_id,
                                "LEDGER_ORDER_NOT_FOUND",
                                ReconcileSettlementService._object_key(data, "ledger_entry", ledger.entry_id),
                            ),
                        ],
                    )
                )

        for transaction in data.pos_transactions:
            if transaction.merchant_order_id not in merchant_orders:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="POS_ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "pos_transaction",
                            transaction.transaction_id,
                        ),
                        message=(
                            f"POS transaction "
                            f"{transaction.transaction_id} "
                            f"references unknown merchant order"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "pos_transaction",
                                transaction.transaction_id,
                                "POS_ORDER_NOT_FOUND",
                                ReconcileSettlementService._object_key(data, "pos_transaction", transaction.transaction_id),
                            ),
                        ],
                    )
                )

        for transaction in data.gateway_transactions:
            if transaction.merchant_order_id not in merchant_orders:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="GATEWAY_ORDER_NOT_FOUND",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "gateway_transaction",
                            transaction.transaction_id,
                        ),
                        message=(
                            f"Gateway transaction "
                            f"{transaction.transaction_id} "
                            f"references unknown merchant order"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "gateway_transaction",
                                transaction.transaction_id,
                                "GATEWAY_ORDER_NOT_FOUND",
                                ReconcileSettlementService._object_key(data, "gateway_transaction", transaction.transaction_id),
                            ),
                        ],
                    )
                )

        if data.settlement.utr and not data.bank_transactions:
            findings.append(
                ReconcileSettlementService._finding(
                    code="BANK_TRANSACTION_MISSING",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "settlement",
                        data.settlement.settlement_id,
                    ),
                    message=(
                        f"No bank transaction found for settlement UTR: "
                        f"{data.settlement.utr}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "settlement",
                            data.settlement.settlement_id,
                            "BANK_TRANSACTION_MISSING",
                        ),
                    ],
                )
            )

        return findings

    @staticmethod
    def _validate_temporal(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        orders = {
            x.order_id: x
            for x in data.orders
        }

        payments = {
            x.payment_id: x
            for x in data.payments
        }

        for payment in data.payments:

            if payment.order_id is None:
                continue

            order = orders.get(payment.order_id)

            if order is None:
                continue

            if payment.created_at < order.created_at:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_BEFORE_ORDER",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=(
                            f"Payment {payment.payment_id} was created "
                            f"before order {order.order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                order.order_id,
                                "PAYMENT_BEFORE_ORDER",
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "PAYMENT_BEFORE_ORDER",
                            ),
                        ],
                    )
                )

            if (
                payment.captured_at is not None
                and payment.captured_at < payment.created_at
            ):
                findings.append(
                    ReconcileSettlementService._finding(
                        code="CAPTURE_BEFORE_PAYMENT",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                        ),
                        message=(
                            f"Payment {payment.payment_id} was captured "
                            f"before it was created"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "CAPTURE_BEFORE_PAYMENT",
                            ),
                        ],
                    )
                )

        for entry in data.settlement_entries:

            if entry.payment_id is None:
                continue

            payment = payments.get(entry.payment_id)

            if payment is None:
                continue

            if entry.created_at < payment.created_at:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="SETTLEMENT_ENTRY_BEFORE_PAYMENT",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=(
                            f"Settlement entry {entry.entry_id} "
                            f"was created before payment "
                            f"{payment.payment_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "SETTLEMENT_ENTRY_BEFORE_PAYMENT",
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "SETTLEMENT_ENTRY_BEFORE_PAYMENT",
                            ),
                        ],
                    )
                )

            if (
                entry.settled_at is not None
                and entry.settled_at < entry.created_at
            ):
                findings.append(
                    ReconcileSettlementService._finding(
                        code="SETTLED_BEFORE_ENTRY",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=(
                            f"Settlement entry {entry.entry_id} "
                            f"was settled before it was created"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "SETTLED_BEFORE_ENTRY",
                            ),
                        ],
                    )
                )

            if (
                payment.captured_at is not None
                and entry.created_at < payment.captured_at
            ):
                findings.append(
                    ReconcileSettlementService._finding(
                        code="SETTLEMENT_BEFORE_CAPTURE",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry.entry_id,
                        ),
                        message=(
                            f"Settlement entry {entry.entry_id} "
                            f"was created before payment "
                            f"{payment.payment_id} was captured"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "SETTLEMENT_BEFORE_CAPTURE",
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "SETTLEMENT_BEFORE_CAPTURE",
                            ),
                        ],
                    )
                )

        if data.settlement.processed_at is not None:
            for entry in data.settlement_entries:
                if (
                    entry.settled_at is not None
                    and entry.settled_at > data.settlement.processed_at
                ):
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="ENTRY_AFTER_SETTLEMENT",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                            ),
                            message=(
                                f"Settlement entry {entry.entry_id} "
                                f"was settled after settlement "
                                f"{data.settlement.settlement_id}"
                            ),
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement",
                                    data.settlement.settlement_id,
                                    "ENTRY_AFTER_SETTLEMENT",
                                ),
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "settlement_entry",
                                    entry.entry_id,
                                    "ENTRY_AFTER_SETTLEMENT",
                                ),
                            ],
                        )
                    )

        return findings

    @staticmethod
    def _validate_completeness(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        orders = {
            x.order_id: x
            for x in data.orders
        }

        payments_by_order: dict[str, int] = {}

        for payment in data.payments:
            if payment.order_id is None:
                continue

            payments_by_order[payment.order_id] = (
                payments_by_order.get(payment.order_id, 0) + 1
            )

        for merchant_order in data.merchant_orders:
            razorpay_order = orders.get(
                merchant_order.razorpay_order_id
            )

            if razorpay_order is None:
                continue

            if payments_by_order.get(razorpay_order.order_id, 0) == 0:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="PAYMENT_MISSING",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "razorpay_order",
                            razorpay_order.order_id,
                        ),
                        message=(
                            f"No payment found for "
                            f"Razorpay order {razorpay_order.order_id}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "merchant_order",
                                merchant_order.order_id,
                                "PAYMENT_MISSING",
                                ReconcileSettlementService._object_key(data, "merchant_order", merchant_order.order_id),
                            ),
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "razorpay_order",
                                razorpay_order.order_id,
                                "PAYMENT_MISSING",
                            ),
                        ],
                    )
                )

        entry_counts: dict[str, int] = {}

        for entry in data.settlement_entries:
            entry_counts[entry.entry_id] = (
                entry_counts.get(entry.entry_id, 0) + 1
            )

        for entry_id, count in entry_counts.items():
            if count <= 1:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="DUPLICATE_SETTLEMENT_ENTRY",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "settlement_entry",
                        entry_id,
                    ),
                    message=(
                        f"Duplicate settlement entry: "
                        f"{entry_id}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "settlement_entry",
                            entry_id,
                            "DUPLICATE_SETTLEMENT_ENTRY",
                        ),
                    ],
                )
            )

        referenced_payment_ids = {
            entry.payment_id
            for entry in data.settlement_entries
            if entry.payment_id
        }

        for payment in data.payments:
            if payment.payment_id in referenced_payment_ids:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="UNSETTLED_PAYMENT",
                    severity="warning",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "payment",
                        payment.payment_id,
                    ),
                    message=(
                        f"Payment not represented in settlement entries: "
                        f"{payment.payment_id}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                            "UNSETTLED_PAYMENT",
                        ),
                    ],
                )
            )

        return findings

    @staticmethod
    def _validate_settlement(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        findings: list[ReconciliationFinding] = []

        if not data.settlement.utr:
            findings.append(
                ReconcileSettlementService._finding(
                    code="SETTLEMENT_UTR_MISSING",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "settlement",
                        data.settlement.settlement_id,
                    ),
                    message=(
                        f"Settlement UTR missing: "
                        f"{data.settlement.settlement_id}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "settlement",
                            data.settlement.settlement_id,
                            "SETTLEMENT_UTR_MISSING",
                        ),
                    ],
                )
            )

        return findings

    @staticmethod
    def _extract_evidence(
        findings: list[ReconciliationFinding],
    ) -> list[EvidenceRef]:
        evidence: list[EvidenceRef] = []
        seen: set[tuple[str, str, str, str, str | None]] = set()

        for finding in findings:
            for item in finding.evidence:
                key = (
                    item.source,
                    item.entity_type,
                    item.entity_id,
                    item.reason,
                    item.object_key,
                )

                if key in seen:
                    continue

                seen.add(key)
                evidence.append(item)

        return evidence

    @staticmethod
    def _calculate_razorpay_net(
        data: SettlementReconciliationData,
    ) -> Decimal:
        entries = {
            x.entry_id: x
            for x in data.settlement_entries
        }

        return sum(
            (x.credit - x.debit for x in entries.values()),
            Decimal("0"),
        )

    @staticmethod
    def _calculate_merchant_expected(
        ledgers,
    ) -> Decimal:
        entries = {
            x.entry_id: x
            for x in ledgers
        }

        return sum(
            (x.credit - x.debit for x in entries.values()),
            Decimal("0"),
        )

    @staticmethod
    def _calculate_bank_observed(
        transactions,
    ) -> Decimal:
        transactions = {
            x.transaction_id: x
            for x in transactions
        }

        return sum(
            (x.credit - x.debit for x in transactions.values()),
            Decimal("0"),
        )

    @staticmethod
    def _get_reason_code(
        findings: list[ReconciliationFinding],
    ) -> str:
        priority = (
            "PAYMENT_NOT_CAPTURED",
            "REFUND_NOT_PROCESSED",
            "PAYMENT_BEFORE_ORDER",
            "CAPTURE_BEFORE_PAYMENT",
            "SETTLEMENT_BEFORE_CAPTURE",
            "ORDER_AMOUNT_MISMATCH",
            "PAYMENT_AMOUNT_MISMATCH",
            "ORDER_CURRENCY_MISMATCH",
            "PAYMENT_CURRENCY_MISMATCH",
            "BANK_TRANSACTION_MISSING",
            "RAZORPAY_ORDER_NOT_FOUND",
            "PAYMENT_NOT_FOUND",
            "FINANCIAL_DIFFERENCE",
        )

        codes = {
            finding.code
            for finding in findings
        }

        for code in priority:
            if code in codes:
                return code

        return findings[0].code if findings else "UNKNOWN"