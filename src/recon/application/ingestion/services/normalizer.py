from __future__ import annotations

import re 
from dataclasses import dataclass 
from decimal import Decimal, InvalidOperation
from typing import Any 
from datetime import date, datetime

from recon.application.ingestion.dto.normalization import (
    NormalizationResult, FieldMapping, DetectedEntity,
)


class MerchantSourceNormalizer:
    """
    Converts source-specific parsed rows into our canonical
    field representation.

    V1:
    - one entity type per file
    - deterministic field detection
    - deterministic value normalization
    """

    FIELD_ALIASES: dict[str, set[str]] = {
        "merchant_order_id": {
            "merchant_order_id",
            "order_id",
            "orderid",
            "order_no",
            "order_number",
            "sales_order",
            "sales_order_id",
            "order_ref",
            "order_reference",
        },
        "razorpay_order_id": {
            "razorpay_order_id",
            "razorpay_order",
            "rzp_order",
            "rp_order",
            "razorpay_ref",
            "razorpay_reference",
        },
        "amount": {
            "amount",
            "total",
            "total_amount",
            "order_amount",
            "gross_amount",
            "transaction_amount",
        },
        "currency": {
            "currency",
            "currency_code",
            "curr",
        },
        "customer_ref": {
            "customer_ref",
            "customer_id",
            "customer",
            "client_id",
            "buyer_id",
        },
        "invoice_id": {
            "invoice_id",
            "invoice",
            "invoice_no",
            "invoice_number",
        },
        "status": {
            "status",
            "payment_status",
            "order_status",
            "state",
        },
        "created_at": {
            "created_at",
            "created_date",
            "order_date",
            "date",
            "timestamp",
        },
        "ledger_entry_id": {
            "entry_id",
            "ledger_id",
            "ledger_entry_id",
            "line_id",
        },
        "account_code": {
            "account_code",
            "account",
            "account_id",
            "gl_account",
            "gl_code",
        },
        "entry_type": {
            "entry_type",
            "transaction_type",
            "posting_type",
            "type",
        },
        "debit": {
            "debit",
            "dr",
            "debit_amount",
        },
        "credit": {
            "credit",
            "cr",
            "credit_amount",
        },
        "reference": {
            "reference",
            "ref",
            "reference_id",
            "transaction_reference",
        },

        "transaction_id": {
            "transaction_id",
            "txn_id",
            "transaction_no",
            "transaction_number",
        },
        "utr": {
            "utr",
            "utr_no",
            "utr_number",
            "bank_reference",
        },
        "transaction_date": {
            "transaction_date",
            "txn_date",
            "date",
        },
        "value_date": {
            "value_date",
            "value_dt",
        },
        "description": {
            "description",
            "narration",
            "remarks",
            "details",
        },
        "balance": {
            "balance",
            "closing_balance",
            "running_balance",
        },

        "pos_transaction_id": {
            "pos_transaction_id",
            "pos_txn_id",
            "terminal_transaction_id",
            "receipt_id",
        },
        "terminal_id": {
            "terminal_id",
            "terminal",
            "pos_id",
            "machine_id",
        },

        "gateway_transaction_id": {
            "gateway_transaction_id",
            "gateway_txn_id",
        },
        "gateway_order_id": {
            "gateway_order_id",
            "gateway_order",
            "gateway_ref",
            "payment_reference",
        },
        "posted_at": {
            "posted_at",
            "posted_date",
            "posting_date",
            "entry_date",
        },
    }

    ENTITY_SIGNATURES: dict[str, set[str]] = {
        "merchant_order": {
            "merchant_order_id",
            "razorpay_order_id",
            "amount",
            "currency",
        },
        "ledger_entry": {
            "ledger_entry_id",
            "account_code",
            "debit",
            "credit",
        },
        "bank_transaction": {
            "transaction_id",
            "utr",
            "transaction_date",
            "debit",
            "credit",
        },
        "pos_transaction": {
            "pos_transaction_id",
            "merchant_order_id",
            "amount",
            "transaction_date",
            "terminal_id",
        },
        "gateway_transaction": {
            "gateway_transaction_id",
            "merchant_order_id",
            "amount",
            "currency",
            "status",
        },
    }

    CURRENCY_SYMBOLS = {
        "₹": "INR",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    def normalize(self, rows: list[dict[str,Any]]) -> "NormalizationResult":

        if not rows:
            return NormalizationResult(
                entity_type="unknown",
                entity_confidence=0.0,
                field_mappings=[],
                records=[],
                warnings=["Input file contains no records."],
                errors=[],
            )
        
        normalized_headers = {
            MerchantSourceNormalizer.normalize_column_name(column) 
            for column in rows[0].keys()
        }

        entity = self._detect_entity(normalized_headers)
        mappings = self._detect_field_mappings(rows[0].keys())
        records = [
            self._normalize_record(row, mappings) for row in rows
        ]

        return NormalizationResult(
            entity_type=entity.entity_type,
            entity_confidence=entity.confidence,
            field_mappings=mappings,
            records=records,
            warnings=[],
            errors=[],
        )


    def _detect_entity(self, columns: set[str]) -> DetectedEntity:
        scores: dict[str, tuple[int, list[str]]] = {}

        for entity_type, signature in self.ENTITY_SIGNATURES.items():
            matched = columns & signature

            if matched:
                scores[entity_type] = (
                    len(matched),
                    [
                        f"Matched column: {column}" for column in sorted(matched)
                    ],
                )

        if not scores:
            return DetectedEntity(
                entity_type="unknown",
                confidence=0.0,
                reasons=["No known entity signature matched."],
            )

        entity_type, (score, reasons) = max(
            scores.items(),
            key=lambda item: item[1][0],
        )

        confidence = min(score / len(self.ENTITY_SIGNATURES[entity_type]), 1.0)

        return DetectedEntity(
            entity_type=entity_type,
            confidence=confidence,
            reasons=reasons,
        )

    def _detect_field_mappings(self, columns: Any) -> list[FieldMapping]:
        mappings: list[FieldMapping] = []

        for source_column in columns:
            normalized = MerchantSourceNormalizer.normalize_column_name(source_column)

            candidates = [
                canonical_field for canonical_field, aliases in self.FIELD_ALIASES.items()
                if normalized in aliases
            ]

            if len(candidates) == 1:
                mappings.append(
                    FieldMapping(
                        source_column=source_column,
                        canonical_field=candidates[0],
                        confidence=1.0,
                        reason="exact alias match",
                    )
                )

            elif len(candidates) > 1:
                mappings.append(
                    FieldMapping(
                        source_column=source_column,
                        canonical_field="ambiguous",
                        confidence=0.0,
                        reason="multiple canonical fields matched",
                    )
                )

        return mappings

    def _normalize_record(
        self,
        row: dict[str, Any],
        mappings: list[FieldMapping],
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}

        for mapping in mappings:
            if mapping.canonical_field == "ambiguous":
                continue

            raw_value = row.get(mapping.source_column)
            normalized[mapping.canonical_field] = (
                self._normalize_value(mapping.canonical_field, raw_value)
            )

        return normalized

    @staticmethod
    def _normalize_value(
        field: str,
        value: Any,
    ) -> Any:

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

        if field in {
            "amount",
            "debit",
            "credit",
            "fee",
            "tax",
            "balance",
        }:
            amount, _ = MerchantSourceNormalizer.normalize_amount(value)
            return amount

        if field in {
            "currency",
            "status",
        }:
            return str(value).upper()

        if field in {
            "transaction_date",
            "value_date",
        }:
            if isinstance(value, date):
                return value

            text = str(value)
            try:
                return date.fromisoformat(text)
            except ValueError:
                # Some bank exports put a full ISO datetime (with time/offset)
                # in what is otherwise a date-only column.
                return datetime.fromisoformat(text).date()

        if field in {
            "created_at",
            "posted_at",
        }:
            if isinstance(value, datetime):
                return value

            return datetime.fromisoformat(str(value))

        return value

    @staticmethod
    def normalize_amount(
        value: Any,
    ) -> tuple[Decimal | None, str | None]:
        if value is None:
            return None, None

        value = str(value).strip()

        detected_currency = None

        for symbol, currency in MerchantSourceNormalizer.CURRENCY_SYMBOLS.items():
            if symbol in value:
                detected_currency = currency
                value = value.replace(symbol, "")

        value = value.replace(",", "").strip()

        try:
            return Decimal(value), detected_currency
        except InvalidOperation:
            return None, detected_currency


    @staticmethod
    def normalize_column_name(name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[^a-z0-9]+", "_", name)
        return name.strip("_")