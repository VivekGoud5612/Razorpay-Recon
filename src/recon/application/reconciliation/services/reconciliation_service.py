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
            + self._validate_ledger_amounts(data)
            + self._validate_ledger_payment_references(data)
            + self._validate_multi_source_amounts(data)
            + self._validate_source_amounts_against_payment(data)
            + self._validate_temporal(data)
            + self._validate_settlement_timing(data)
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

        # DUPLICATE_ORDER: distinct from DUPLICATE_MERCHANT_ORDER above --
        # here the *merchant_order_id* values are all different, but two or
        # more of them reference the exact same razorpay_order_id, i.e. the
        # merchant uploaded the same underlying order twice under different
        # labels. This never touches uq_merchant_order_source (the DB
        # constraint is keyed on merchant_order_id, not razorpay_order_id),
        # so it is representable and detectable without any constraint
        # change.
        razorpay_ref_to_merchant_ids: dict[str, list[str]] = {}
        for merchant_order in data.merchant_orders:
            if merchant_order.razorpay_order_id in razorpay_orders:
                razorpay_ref_to_merchant_ids.setdefault(
                    merchant_order.razorpay_order_id, []
                ).append(merchant_order.order_id)

        for razorpay_order_id, merchant_ids in razorpay_ref_to_merchant_ids.items():
            if len(merchant_ids) <= 1:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="DUPLICATE_ORDER",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "razorpay_order",
                        razorpay_order_id,
                    ),
                    message=(
                        f"Razorpay order {razorpay_order_id} is claimed by "
                        f"{len(merchant_ids)} different merchant orders: "
                        f"{sorted(merchant_ids)}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            "merchant_order",
                            merchant_id,
                            "DUPLICATE_ORDER",
                            ReconcileSettlementService._object_key(data, "merchant_order", merchant_id),
                        )
                        for merchant_id in sorted(merchant_ids)
                    ]
                    + [
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "razorpay_order",
                            razorpay_order_id,
                            "DUPLICATE_ORDER",
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
    def _validate_ledger_amounts(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        """MERCHANT_LEDGER_AMOUNT_MISMATCH: the merchant's own ledger books a
        different amount than the actual Razorpay payment for that order --
        a bookkeeping drift on the merchant's side, not a Razorpay-side
        problem (merchant_orders/razorpay_orders/payments can all agree with
        each other while the ledger alone disagrees). This does not treat
        the ledger as settlement authority: it only reports the mismatch as
        a finding, exactly like every other *_AMOUNT_MISMATCH check here --
        it has no effect on which of merchant/razorpay/bank is authoritative
        for the settlement-level status.

        Aggregated per merchant_order_id over its `entry_type == "credit"`
        rows only (not a blind sum of credit-debit across every row). A
        proper double-entry ledger books revenue as one credit row (e.g.
        account_code=SALES) *and* an offsetting debit row (e.g.
        RECEIVABLE) for the same order -- summing credit-debit per row
        would flag every single order's own balancing debit row as a
        "mismatch" against the payment amount, and completely miss a real
        anomaly like an extra, unexplained credit row (which nets out
        against nothing). Revenue actually booked for an order is the sum
        of what it was *credited*, full stop; the offsetting debit is a
        balance-sheet fact, not a second, independent revenue claim.
        """
        findings: list[ReconciliationFinding] = []

        merchant_orders = {x.order_id: x for x in data.merchant_orders}
        razorpay_orders = {x.order_id: x for x in data.orders}
        payments_by_order = {
            x.order_id: x for x in data.payments if x.order_id is not None
        }

        credits_by_order: dict[str, list] = {}
        for ledger in data.ledger_entries:
            if ledger.entry_type != "credit":
                continue
            if ledger.merchant_order_id not in merchant_orders:
                continue  # LEDGER_ORDER_NOT_FOUND already covers this row
            credits_by_order.setdefault(ledger.merchant_order_id, []).append(ledger)

        for merchant_order_id, credit_entries in credits_by_order.items():
            merchant_order = merchant_orders[merchant_order_id]
            razorpay_order = razorpay_orders.get(merchant_order.razorpay_order_id)

            if razorpay_order is None:
                continue  # RAZORPAY_ORDER_NOT_FOUND already covers this row

            payment = payments_by_order.get(razorpay_order.order_id)

            if payment is None:
                continue

            booked_revenue = sum((e.credit for e in credit_entries), Decimal("0"))

            if booked_revenue != payment.amount:
                findings.append(
                    ReconcileSettlementService._finding(
                        code="MERCHANT_LEDGER_AMOUNT_MISMATCH",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "merchant",
                            "merchant_order",
                            merchant_order.order_id,
                        ),
                        message=(
                            f"Ledger books {booked_revenue} in revenue "
                            f"credits for {merchant_order.order_id} but the "
                            f"actual Razorpay payment {payment.payment_id} "
                            f"is {payment.amount}"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "merchant",
                                "ledger_entry",
                                ledger.entry_id,
                                "MERCHANT_LEDGER_AMOUNT_MISMATCH",
                                ReconcileSettlementService._object_key(data, "ledger_entry", ledger.entry_id),
                            )
                            for ledger in credit_entries
                        ]
                        + [
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "payment",
                                payment.payment_id,
                                "MERCHANT_LEDGER_AMOUNT_MISMATCH",
                            ),
                        ],
                    )
                )

        return findings

    @staticmethod
    def _validate_ledger_payment_references(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        """Ledger entries carry the razorpay_payment_id they claim in
        `reference`. When the same reference is cited by ledger entries
        under more than one merchant_order_id, exactly one of two things is
        true, and which one is determined structurally (never by string
        similarity/fuzzy matching):

        - DUPLICATE_PAYMENT: none of the citing merchant orders has a
          *different* payment of its own via its own
          merchant_order -> razorpay_order -> payment chain (e.g. the
          "duplicate" entry belongs to no real distinct order at all) --
          the same real payment was simply posted to the ledger twice.
        - WRONG_PAYMENT_REFERENCE: a citing merchant order's own natural
          chain resolves to a *different*, real payment than the one it
          cited in the ledger -- that merchant order referenced someone
          else's payment by mistake, and its own true payment is
          identifiable and reported as the correct one.
        """
        findings: list[ReconciliationFinding] = []

        merchant_orders = {x.order_id: x for x in data.merchant_orders}
        razorpay_orders = {x.order_id: x for x in data.orders}
        payments_by_id = {x.payment_id: x for x in data.payments}
        payments_by_order = {
            x.order_id: x for x in data.payments if x.order_id is not None
        }

        def natural_payment_id(merchant_order_id: str) -> str | None:
            merchant_order = merchant_orders.get(merchant_order_id)
            if merchant_order is None:
                return None
            razorpay_order = razorpay_orders.get(merchant_order.razorpay_order_id)
            if razorpay_order is None:
                return None
            payment = payments_by_order.get(razorpay_order.order_id)
            return payment.payment_id if payment else None

        references: dict[str, list[LedgerEntry]] = {}
        for ledger in data.ledger_entries:
            if not ledger.reference or ledger.reference not in payments_by_id:
                continue
            references.setdefault(ledger.reference, []).append(ledger)

        for reference, entries in references.items():
            citing_order_ids = {
                e.merchant_order_id for e in entries if e.merchant_order_id
            }

            if len(citing_order_ids) <= 1:
                continue

            wrong_reference_orders = {
                order_id: natural_payment_id(order_id)
                for order_id in citing_order_ids
                if natural_payment_id(order_id) not in (None, reference)
            }

            if wrong_reference_orders:
                for order_id, correct_payment_id in wrong_reference_orders.items():
                    wrong_entry = next(
                        e for e in entries if e.merchant_order_id == order_id
                    )
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="WRONG_PAYMENT_REFERENCE",
                            severity="error",
                            entity=ReconcileSettlementService._entity(
                                "merchant",
                                "merchant_order",
                                order_id,
                            ),
                            message=(
                                f"Ledger entry {wrong_entry.entry_id} for "
                                f"{order_id} references payment {reference}, "
                                f"but {order_id}'s own Razorpay order links "
                                f"to a different real payment: "
                                f"{correct_payment_id}"
                            ),
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "merchant",
                                    "ledger_entry",
                                    wrong_entry.entry_id,
                                    "WRONG_PAYMENT_REFERENCE",
                                    ReconcileSettlementService._object_key(data, "ledger_entry", wrong_entry.entry_id),
                                ),
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "payment",
                                    correct_payment_id,
                                    "WRONG_PAYMENT_REFERENCE",
                                ),
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "payment",
                                    reference,
                                    "WRONG_PAYMENT_REFERENCE",
                                ),
                            ],
                        )
                    )
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="DUPLICATE_PAYMENT",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "razorpay",
                        "payment",
                        reference,
                    ),
                    message=(
                        f"Payment {reference} is cited by ledger entries "
                        f"under {len(citing_order_ids)} different merchant "
                        f"orders: {sorted(citing_order_ids)}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            "ledger_entry",
                            entry.entry_id,
                            "DUPLICATE_PAYMENT",
                            ReconcileSettlementService._object_key(data, "ledger_entry", entry.entry_id),
                        )
                        for entry in sorted(entries, key=lambda e: e.entry_id)
                    ]
                    + [
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "payment",
                            reference,
                            "DUPLICATE_PAYMENT",
                        ),
                    ],
                )
            )

        return findings

    @staticmethod
    def _validate_multi_source_amounts(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        """MULTI_SOURCE_DISAGREEMENT: the merchant's own ledger, POS, and
        other-gateway records for the *same* merchant_order_id state
        different amounts for it. Unlike the other amount-mismatch checks,
        there is no single authoritative merchant-side source here to
        compare against Razorpay -- three merchant-side sources disagree
        with each other, which is exactly the kind of fault the
        investigation layer should abstain on rather than guess which one
        is right.

        The ledger side is aggregated per order over `entry_type ==
        "credit"` rows only, same rationale as _validate_ledger_amounts: a
        double-entry ledger's balancing debit row is not a second,
        independent amount claim, and comparing it directly against
        POS/gateway (which have no debit/credit distinction at all) would
        manufacture a disagreement out of ordinary double-entry bookkeeping
        on every single order.
        """
        findings: list[ReconciliationFinding] = []
        merchant_orders = {x.order_id: x for x in data.merchant_orders}

        amounts_by_order: dict[str, dict[str, tuple[str, object]]] = {}

        ledger_credits_by_order: dict[str, list] = {}
        for ledger in data.ledger_entries:
            if ledger.entry_type != "credit":
                continue
            if ledger.merchant_order_id not in merchant_orders:
                continue
            ledger_credits_by_order.setdefault(ledger.merchant_order_id, []).append(ledger)

        for merchant_order_id, credit_entries in ledger_credits_by_order.items():
            booked_revenue = sum((e.credit for e in credit_entries), Decimal("0"))
            representative_id = "+".join(sorted(e.entry_id for e in credit_entries))
            amounts_by_order.setdefault(merchant_order_id, {})["ledger_entry"] = (
                representative_id,
                booked_revenue,
            )

        for pos in data.pos_transactions:
            if pos.merchant_order_id not in merchant_orders:
                continue
            amounts_by_order.setdefault(pos.merchant_order_id, {})["pos_transaction"] = (
                pos.transaction_id,
                pos.amount,
            )

        for gw in data.gateway_transactions:
            if gw.merchant_order_id not in merchant_orders:
                continue
            amounts_by_order.setdefault(gw.merchant_order_id, {})["gateway_transaction"] = (
                gw.transaction_id,
                gw.amount,
            )

        for merchant_order_id, sources in amounts_by_order.items():
            if len(sources) < 2:
                continue

            distinct_amounts = {amount for _, amount in sources.values()}

            if len(distinct_amounts) <= 1:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="MULTI_SOURCE_DISAGREEMENT",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "merchant",
                        "merchant_order",
                        merchant_order_id,
                    ),
                    message=(
                        f"Merchant-side sources disagree on the amount for "
                        f"{merchant_order_id}: "
                        + ", ".join(
                            f"{entity_type}={amount}"
                            for entity_type, (_, amount) in sorted(sources.items())
                        )
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            entity_type,
                            entity_id,
                            "MULTI_SOURCE_DISAGREEMENT",
                            ReconcileSettlementService._object_key(data, entity_type, entity_id),
                        )
                        for entity_type, (entity_id, _) in sorted(sources.items())
                    ],
                )
            )

        return findings

    @staticmethod
    def _validate_source_amounts_against_payment(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        """POS_AMOUNT_MISMATCH / GATEWAY_AMOUNT_MISMATCH: a merchant-side
        POS or other-gateway record for an order states an amount that
        disagrees with the *actual* Razorpay payment for that order --
        distinct from MULTI_SOURCE_DISAGREEMENT (which fires when
        merchant-side sources disagree *with each other* and there is no
        authoritative side to check against). Here there is one: the real
        payment. Reported as its own itemized finding rather than folded
        into MULTI_SOURCE_DISAGREEMENT so it's clear which single merchant
        source is wrong, not just that "sources disagree."
        """
        findings: list[ReconciliationFinding] = []

        merchant_orders = {x.order_id: x for x in data.merchant_orders}
        razorpay_orders = {x.order_id: x for x in data.orders}
        payments_by_order = {
            x.order_id: x for x in data.payments if x.order_id is not None
        }

        def actual_payment(merchant_order_id: str):
            merchant_order = merchant_orders.get(merchant_order_id)
            if merchant_order is None:
                return None
            razorpay_order = razorpay_orders.get(merchant_order.razorpay_order_id)
            if razorpay_order is None:
                return None
            return payments_by_order.get(razorpay_order.order_id)

        for pos in data.pos_transactions:
            payment = actual_payment(pos.merchant_order_id)

            if payment is None or pos.amount == payment.amount:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="POS_AMOUNT_MISMATCH",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "merchant",
                        "merchant_order",
                        pos.merchant_order_id,
                    ),
                    message=(
                        f"POS transaction {pos.transaction_id} states "
                        f"{pos.amount} for {pos.merchant_order_id} but the "
                        f"actual Razorpay payment {payment.payment_id} is "
                        f"{payment.amount}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            "pos_transaction",
                            pos.transaction_id,
                            "POS_AMOUNT_MISMATCH",
                            ReconcileSettlementService._object_key(data, "pos_transaction", pos.transaction_id),
                        ),
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                            "POS_AMOUNT_MISMATCH",
                        ),
                    ],
                )
            )

        for gw in data.gateway_transactions:
            payment = actual_payment(gw.merchant_order_id)

            if payment is None or gw.amount == payment.amount:
                continue

            findings.append(
                ReconcileSettlementService._finding(
                    code="GATEWAY_AMOUNT_MISMATCH",
                    severity="error",
                    entity=ReconcileSettlementService._entity(
                        "merchant",
                        "merchant_order",
                        gw.merchant_order_id,
                    ),
                    message=(
                        f"Gateway transaction {gw.transaction_id} states "
                        f"{gw.amount} for {gw.merchant_order_id} but the "
                        f"actual Razorpay payment {payment.payment_id} is "
                        f"{payment.amount}"
                    ),
                    evidence=[
                        ReconcileSettlementService._evidence(
                            "merchant",
                            "gateway_transaction",
                            gw.transaction_id,
                            "GATEWAY_AMOUNT_MISMATCH",
                            ReconcileSettlementService._object_key(data, "gateway_transaction", gw.transaction_id),
                        ),
                        ReconcileSettlementService._evidence(
                            "razorpay",
                            "payment",
                            payment.payment_id,
                            "GATEWAY_AMOUNT_MISMATCH",
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

    # A settlement crediting more than this many days after the payment it
    # settles is treated as an anomaly worth a deterministic finding. Real
    # settlement timing is T+2/T+3; this threshold is deliberately well
    # above that (not a tight boundary check) so normal timing variance
    # never trips it -- it exists to catch genuinely anomalous delays
    # (weeks), not to police the exact settlement SLA.
    SETTLEMENT_TIMING_THRESHOLD_DAYS = 7

    @staticmethod
    def _validate_settlement_timing(
        data: SettlementReconciliationData,
    ) -> list[ReconciliationFinding]:
        """SETTLEMENT_TIMING_ANOMALY: a bank credit dated far outside the
        expected settlement window from the payments it settles. Anchored
        on the bank_transaction's own `utr` against the settlement's own
        `settlement_entries[].settlement_utr` -- the exact same UTR linkage
        RELATION_RULES already uses for the settlement<->bank_transaction
        graph edge, not a fuzzy/approximate match.

        One finding per (settlement, bank_transaction) pair, anchored on the
        *earliest* captured payment settled by it -- this is a fact about
        the settlement's timing as a whole (every payment in the same
        settlement shares the same bank credit date by construction), not a
        separate fault per payment; reporting one per payment would just be
        the same anomaly repeated N times.
        """
        findings: list[ReconciliationFinding] = []

        payments_by_id = {x.payment_id: x for x in data.payments}
        bank_by_utr: dict[str, list] = {}
        for bank_transaction in data.bank_transactions:
            if bank_transaction.utr:
                bank_by_utr.setdefault(bank_transaction.utr, []).append(bank_transaction)

        entries_by_utr: dict[str, list] = {}
        for entry in data.settlement_entries:
            if entry.payment_id is None or not entry.settlement_utr:
                continue
            payment = payments_by_id.get(entry.payment_id)
            if payment is None or payment.captured_at is None:
                continue
            entries_by_utr.setdefault(entry.settlement_utr, []).append(payment)

        for utr, payments in entries_by_utr.items():
            earliest_payment = min(payments, key=lambda p: p.captured_at)

            for bank_transaction in bank_by_utr.get(utr, []):
                days_elapsed = (bank_transaction.transaction_date - earliest_payment.captured_at.date()).days

                if days_elapsed > ReconcileSettlementService.SETTLEMENT_TIMING_THRESHOLD_DAYS:
                    findings.append(
                        ReconcileSettlementService._finding(
                            code="SETTLEMENT_TIMING_ANOMALY",
                            severity="warning",
                            entity=ReconcileSettlementService._entity(
                                "razorpay",
                                "settlement",
                                data.settlement.settlement_id,
                            ),
                            message=(
                                f"Bank credit {bank_transaction.transaction_id} "
                                f"(UTR {utr}) landed {days_elapsed} days "
                                f"after the earliest payment in this "
                                f"settlement, {earliest_payment.payment_id}, "
                                f"was captured ({earliest_payment.captured_at.date()})"
                            ),
                            evidence=[
                                ReconcileSettlementService._evidence(
                                    "razorpay",
                                    "payment",
                                    earliest_payment.payment_id,
                                    "SETTLEMENT_TIMING_ANOMALY",
                                ),
                                ReconcileSettlementService._evidence(
                                    "bank",
                                    "bank_transaction",
                                    bank_transaction.transaction_id,
                                    "SETTLEMENT_TIMING_ANOMALY",
                                    ReconcileSettlementService._object_key(data, "bank_transaction", bank_transaction.transaction_id),
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

        # BANK_SETTLEMENT_AMOUNT_DIFFERENCE: itemized *per UTR* -- exactly
        # the authoritative comparison this system's financial-authority
        # rule names (Razorpay settlement net vs bank observed), but scoped
        # down to the specific settlement_entry/bank_transaction pair that
        # actually disagrees, not a single blunt settlement-wide finding.
        # A settlement with 60 clean entries and one short-settled UTR must
        # name that one UTR, not report "the settlement" as if the whole
        # thing were wrong (previously this only ever surfaced as the top-
        # level FINANCIAL_DIFFERENCE reason code with zero explaining
        # evidence at all). Only fires for a UTR that actually has bank
        # data; a totally absent bank transaction for the settlement is
        # BANK_TRANSACTION_MISSING's job, not this one's.
        if data.bank_transactions:
            entries_by_utr: dict[str, list] = {}
            for entry in data.settlement_entries:
                if entry.settlement_utr:
                    entries_by_utr.setdefault(entry.settlement_utr, []).append(entry)

            bank_by_utr: dict[str, list] = {}
            for bank_transaction in data.bank_transactions:
                if bank_transaction.utr:
                    bank_by_utr.setdefault(bank_transaction.utr, []).append(bank_transaction)

            for utr, entries in entries_by_utr.items():
                bank_rows = bank_by_utr.get(utr)

                if not bank_rows:
                    continue  # no bank data for this UTR at all -- not this check's job

                expected_net = sum((e.credit - e.debit for e in entries), Decimal("0"))
                observed = sum((b.credit - b.debit for b in bank_rows), Decimal("0"))

                if expected_net == observed:
                    continue

                # entity_id must be unique per UTR (not just the settlement)
                # -- ReconciliationFinding.finding_id is derived from
                # code+entity_type+entity_id, so keying every UTR's finding
                # on the same settlement entity would collide and silently
                # overwrite one another the moment more than one UTR is
                # actually anomalous.
                entry_key = "+".join(sorted(e.entry_id for e in entries))

                findings.append(
                    ReconcileSettlementService._finding(
                        code="BANK_SETTLEMENT_AMOUNT_DIFFERENCE",
                        severity="error",
                        entity=ReconcileSettlementService._entity(
                            "razorpay",
                            "settlement_entry",
                            entry_key,
                        ),
                        message=(
                            f"Bank observed {observed} for UTR {utr} "
                            f"differs from Razorpay's computed net "
                            f"{expected_net} for the settlement_entry/ies "
                            f"it settles"
                        ),
                        evidence=[
                            ReconcileSettlementService._evidence(
                                "razorpay",
                                "settlement_entry",
                                entry.entry_id,
                                "BANK_SETTLEMENT_AMOUNT_DIFFERENCE",
                            )
                            for entry in entries
                        ]
                        + [
                            ReconcileSettlementService._evidence(
                                "bank",
                                "bank_transaction",
                                bank_transaction.transaction_id,
                                "BANK_SETTLEMENT_AMOUNT_DIFFERENCE",
                                ReconcileSettlementService._object_key(data, "bank_transaction", bank_transaction.transaction_id),
                            )
                            for bank_transaction in bank_rows
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
        # Some merchant ledgers post one row per order (entry_type is always
        # "credit"); others use genuine double-entry bookkeeping -- a credit
        # revenue row plus a balancing debit row per order. Summing
        # credit - debit across *all* rows is correct for the former but
        # nets every double-entry order down to ~0 (the two rows cancel),
        # collapsing the settlement-wide total to a near-zero residual of
        # only the imbalanced orders. Only credit-type rows represent booked
        # revenue in either style; debit rows are never independently summed.
        entries = {
            x.entry_id: x
            for x in ledgers
        }

        return sum(
            (x.credit for x in entries.values() if x.entry_type == "credit"),
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
            "DUPLICATE_ORDER",
            "DUPLICATE_PAYMENT",
            "WRONG_PAYMENT_REFERENCE",
            "ORDER_AMOUNT_MISMATCH",
            "PAYMENT_AMOUNT_MISMATCH",
            "ORDER_CURRENCY_MISMATCH",
            "PAYMENT_CURRENCY_MISMATCH",
            "BANK_TRANSACTION_MISSING",
            "BANK_SETTLEMENT_AMOUNT_DIFFERENCE",
            "RAZORPAY_ORDER_NOT_FOUND",
            "PAYMENT_NOT_FOUND",
            "MERCHANT_LEDGER_AMOUNT_MISMATCH",
            "POS_AMOUNT_MISMATCH",
            "GATEWAY_AMOUNT_MISMATCH",
            "MULTI_SOURCE_DISAGREEMENT",
            "SETTLEMENT_TIMING_ANOMALY",
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