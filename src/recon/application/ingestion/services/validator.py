from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any

from recon.application.ingestion.dto.normalization import NormalizationResult


class MerchantRecordValidator:

    REQUIRED_FIELDS = {
        "merchant_order": {
            "merchant_order_id",
            "razorpay_order_id",
            "amount",
            "currency",
            "created_at",
        },
        "ledger_entry": {
            "ledger_entry_id",
            "account_code",
            "entry_type",
            "currency",
            "posted_at",
        },
        "bank_transaction": {
            "transaction_id",
            "transaction_date",
            "description",
        },
        "pos_transaction": {
            "pos_transaction_id",
            "merchant_order_id",
            "amount",
            "currency",
            "transaction_date",
        },
        "gateway_transaction": {
            "gateway_transaction_id",
            "merchant_order_id",
            "amount",
            "currency",
            "status",
            "created_at",
        },
    }

    def validate(
        self,
        result: NormalizationResult,
    ) -> list[str]:
        errors: list[str] = []

        required_fields = self.REQUIRED_FIELDS.get(
            result.entity_type
        )

        if required_fields is None:
            return [f"Unsupported entity type: {result.entity_type}"]

        mapped_fields = {
            mapping.canonical_field
            for mapping in result.field_mappings
            if mapping.canonical_field != "ambiguous"
        }

        for field in sorted(required_fields - mapped_fields):
            errors.append(
                f"Missing required field: {field}"
            )

        for index, record in enumerate(result.records):
            errors.extend(
                self._validate_record(
                    result.entity_type,
                    record,
                    index,
                )
            )

        return errors

    @staticmethod
    def _validate_record(
        entity_type: str,
        record: dict[str, Any],
        index: int,
    ) -> list[str]:
        errors: list[str] = []

        if entity_type == "merchant_order":
            if not record.get("merchant_order_id"):
                errors.append(
                    f"Row {index}: merchant_order_id is missing"
                )

            if not record.get("razorpay_order_id"):
                errors.append(
                    f"Row {index}: razorpay_order_id is missing"
                )

            amount = record.get("amount")
            if not isinstance(amount, Decimal):
                errors.append(
                    f"Row {index}: amount is invalid"
                )
            elif amount < 0:
                errors.append(
                    f"Row {index}: amount cannot be negative"
                )

            if not record.get("currency"):
                errors.append(
                    f"Row {index}: currency is missing"
                )

            if not isinstance(record.get("created_at"), datetime):
                errors.append(
                    f"Row {index}: created_at is invalid"
                )

        elif entity_type == "ledger_entry":
            if not record.get("ledger_entry_id"):
                errors.append(
                    f"Row {index}: ledger_entry_id is missing"
                )

            if not record.get("account_code"):
                errors.append(
                    f"Row {index}: account_code is missing"
                )

            if not record.get("entry_type"):
                errors.append(
                    f"Row {index}: entry_type is missing"
                )

            if not record.get("currency"):
                errors.append(
                    f"Row {index}: currency is missing"
                )

            if not isinstance(record.get("posted_at"), datetime):
                errors.append(
                    f"Row {index}: posted_at is invalid"
                )

            debit = record.get("debit", Decimal("0"))
            credit = record.get("credit", Decimal("0"))

            if not isinstance(debit, Decimal):
                errors.append(
                    f"Row {index}: debit is invalid"
                )
            elif debit < 0:
                errors.append(
                    f"Row {index}: debit cannot be negative"
                )

            if not isinstance(credit, Decimal):
                errors.append(
                    f"Row {index}: credit is invalid"
                )
            elif credit < 0:
                errors.append(
                    f"Row {index}: credit cannot be negative"
                )

        elif entity_type == "bank_transaction":
            if not record.get("transaction_id"):
                errors.append(
                    f"Row {index}: transaction_id is missing"
                )

            if not isinstance(
                record.get("transaction_date"),
                date,
            ):
                errors.append(
                    f"Row {index}: transaction_date is invalid"
                )

            if not record.get("description"):
                errors.append(
                    f"Row {index}: description is missing"
                )

            debit = record.get("debit", Decimal("0"))
            credit = record.get("credit", Decimal("0"))

            if not isinstance(debit, Decimal):
                errors.append(
                    f"Row {index}: debit is invalid"
                )
            elif debit < 0:
                errors.append(
                    f"Row {index}: debit cannot be negative"
                )

            if not isinstance(credit, Decimal):
                errors.append(
                    f"Row {index}: credit is invalid"
                )
            elif credit < 0:
                errors.append(
                    f"Row {index}: credit cannot be negative"
                )

        elif entity_type == "pos_transaction":
            if not record.get("pos_transaction_id"):
                errors.append(
                    f"Row {index}: pos_transaction_id is missing"
                )

            if not record.get("merchant_order_id"):
                errors.append(
                    f"Row {index}: merchant_order_id is missing"
                )

            amount = record.get("amount")
            if not isinstance(amount, Decimal):
                errors.append(
                    f"Row {index}: amount is invalid"
                )
            elif amount < 0:
                errors.append(
                    f"Row {index}: amount cannot be negative"
                )

            if not record.get("currency"):
                errors.append(
                    f"Row {index}: currency is missing"
                )

            if not isinstance(
                record.get("transaction_date"),
                date,
            ):
                errors.append(
                    f"Row {index}: transaction_date is invalid"
                )

        elif entity_type == "gateway_transaction":
            if not record.get("gateway_transaction_id"):
                errors.append(
                    f"Row {index}: gateway_transaction_id is missing"
                )

            if not record.get("merchant_order_id"):
                errors.append(
                    f"Row {index}: merchant_order_id is missing"
                )

            if not isinstance(record.get("amount"), Decimal):
                errors.append(
                    f"Row {index}: amount is invalid"
                )
            elif record["amount"] < 0:
                errors.append(
                    f"Row {index}: amount cannot be negative"
                )

            if not record.get("currency"):
                errors.append(
                    f"Row {index}: currency is missing"
                )

            if not record.get("status"):
                errors.append(
                    f"Row {index}: status is missing"
                )

            if not isinstance(record.get("created_at"), datetime):
                errors.append(
                    f"Row {index}: created_at is invalid"
                )

        return errors