from __future__ import annotations

from typing import Protocol

from recon.application.razorpay.dto.requests import (
    CreateOrderRequest,
    FetchSettlementReconRequest,
)
from recon.application.razorpay.dto.responses import (
    AdjustmentResponse,
    CreateOrderResponse,
    PaymentResponse,
    RefundResponse,
    SettlementReconResponse,
    SettlementResponse,
    TransferResponse,
)


class RazorpayGateway(Protocol):

    async def create_order(
        self,
        request: CreateOrderRequest,
    ) -> CreateOrderResponse:
        ...

    async def fetch_order_payments(
        self,
        order_id: str,
    ) -> list[PaymentResponse]:
        ...

    async def fetch_payment(
        self,
        payment_id: str,
    ) -> PaymentResponse:
        ...

    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
        currency: str,
    ) -> PaymentResponse:
        ...

    async def fetch_refund(
        self,
        payment_id: str,
        refund_id: str,
    ) -> RefundResponse:
        ...

    async def fetch_transfer(
        self,
        transfer_id: str,
    ) -> TransferResponse:
        ...

    async def fetch_adjustment(
        self,
        adjustment_id: str,
    ) -> AdjustmentResponse:
        ...

    async def fetch_settlements(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        count: int = 100,
        skip: int = 0,
    ) -> list[SettlementResponse]:
        ...
        
    async def fetch_settlement(
        self,
        settlement_id: str,
    ) -> SettlementResponse:
        ...

    async def fetch_settlement_recon(
        self,
        request: FetchSettlementReconRequest,
    ) -> list[SettlementReconResponse]:
        ...