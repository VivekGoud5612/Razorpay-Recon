from __future__ import annotations

from recon.domain.razorpay.settlement_entry import RazorpaySettlementEntry

def partition_of_entry_ids(entries: list[RazorpaySettlementEntry]) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    order_ids: set[str] = set()
    payment_ids: set[str] = set()
    refund_ids: set[str] = set()
    transfer_ids: set[str] = set()
    adjustment_ids: set[str] = set()

    for entry in entries:
        if entry.order_id:
            order_ids.add(entry.order_id)

        if entry.payment_id:
            payment_ids.add(entry.payment_id)

        if entry.refund_id:
            refund_ids.add(entry.refund_id)

        if entry.transfer_id:
            transfer_ids.add(entry.transfer_id)

        if entry.adjustment_id:
            adjustment_ids.add(entry.adjustment_id)

    return (
        list(order_ids),
        list(payment_ids),
        list(refund_ids),
        list(transfer_ids),
        list(adjustment_ids),
    )



