from __future__ import annotations

from typing import Protocol

from recon.domain.razorpay.order import RazorpayOrder
from recon.domain.razorpay.payment import RazorpayPayment


class RazorpayRepository(Protocol):

    async def save_order(
        self,
        order: RazorpayOrder,
    ) -> RazorpayOrder:
        ...

    async def save_payment(
        self,
        payment: RazorpayPayment,
    ) -> RazorpayPayment:
        ...

    async def save_settlement(self, settlement: RazorpaySettlement) -> RazorpaySettlement:
        ...

    async def save_settlement_entry(self, entry: RazorpaySettlementEntry) -> RazorpaySettlementEntry:
        ...

    async def save_refund(self, refund: RazorpayRefund) -> RazorpayRefund:
        ...

    async def save_transfer(self, transfer: RazorpayTransfer) -> RazorpayTransfer:
        ...

    async def save_adjustment(self, adjustment: RazorpayAdjustment) -> RazorpayAdjustment:
        ...