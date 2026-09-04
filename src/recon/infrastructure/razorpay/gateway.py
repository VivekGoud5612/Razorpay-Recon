from __future__ import annotations

import asyncio

import httpx
import razorpay

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
from recon.application.razorpay.ports.gateway import RazorpayGateway


class RazorpayApiGateway(RazorpayGateway):

    def __init__(self, key_id: str, key_secret: str) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._client = razorpay.Client(auth=(key_id, key_secret))

    async def create_order(self, request: CreateOrderRequest) -> CreateOrderResponse:
        response = await asyncio.to_thread(
            self._client.order.create,
            data={
                "amount": request.amount,
                "currency": request.currency,
                "receipt": request.receipt,
            },
        )

        return CreateOrderResponse(
            order_id=response["id"],
            amount=response["amount"],
            amount_paid=response["amount_paid"],
            amount_due=response["amount_due"],
            currency=response["currency"],
            receipt=response.get("receipt"),
            status=response["status"],
            attempts=response["attempts"],
            created_at=response["created_at"],
        )

    async def fetch_order_payments(self, order_id: str) -> list[PaymentResponse]:
        response = await asyncio.to_thread(
            self._client.order.payments,
            order_id,
        )
        return [self._map_payment(payment) for payment in response["items"]]

    async def fetch_payment(self, payment_id: str) -> PaymentResponse:
        response = await asyncio.to_thread(
            self._client.payment.fetch,
            payment_id,
        )
        return self._map_payment(response)

    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
        currency: str,
    ) -> PaymentResponse:
        response = await asyncio.to_thread(
            self._client.payment.capture,
            payment_id,
            amount,
            {"currency": currency},
        )
        return self._map_payment(response)

    async def fetch_refund(
        self,
        payment_id: str,
        refund_id: str,
    ) -> RefundResponse:
        response = await asyncio.to_thread(
            self._client.refund.fetch,
            refund_id,
        )
        return RefundResponse(
            refund_id=response["id"],
            payment_id=response["payment_id"],
            amount=response["amount"],
            currency=response["currency"],
            status=response["status"],
            created_at=response["created_at"],
            processed_at=response.get("processed_at"),
        )

    async def fetch_transfer(self, transfer_id: str) -> TransferResponse:
        response = await asyncio.to_thread(
            self._client.transfer.fetch,
            transfer_id,
        )
        return TransferResponse(
            transfer_id=response["id"],
            payment_id=response["source"],
            amount=response["amount"],
            fee=response["fees"],
            tax=response["tax"],
            status=response["status"],
            created_at=response["created_at"],
        )

    async def fetch_adjustment(
        self,
        adjustment_id: str,
    ) -> AdjustmentResponse:
        raise NotImplementedError(
            "Verify the current Adjustment API/SDK method first."
        )

    async def fetch_settlements(
        self,
        count: int = 100,
        skip: int = 0,
    ) -> list[SettlementResponse]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.razorpay.com/v1/settlements/",
                auth=(self._key_id, self._key_secret),
                params={
                    "count": count,
                    "skip": skip,
                },
            )
            response.raise_for_status()

        return [
            SettlementResponse(
                settlement_id=item["id"],
                amount=item["amount"],
                fees=item["fees"],
                tax=item["tax"],
                utr=item.get("utr"),
                status=item["status"],
                created_at=item["created_at"],
                processed_at=None,
            )
            for item in response.json()["items"]
        ]

    async def fetch_settlement(
        self,
        settlement_id: str,
    ) -> SettlementResponse:
        response = await asyncio.to_thread(
            self._client.settlement.fetch,
            settlement_id,
        )

        return SettlementResponse(
            settlement_id=response["id"],
            amount=response["amount"],
            fees=response["fees"],
            tax=response["tax"],
            utr=response.get("utr"),
            status=response["status"],
            created_at=response["created_at"],
            processed_at=None,
        )

    async def fetch_settlement_recon(
        self,
        request: FetchSettlementReconRequest,
    ) -> list[SettlementReconResponse]:
        params = {
            "year": request.year,
            "month": request.month,
            "count": request.count,
            "skip": request.skip,
        }

        if request.day is not None:
            params["day"] = request.day

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.razorpay.com/v1/settlements/recon/combined",
                auth=(self._key_id, self._key_secret),
                params=params,
            )
            response.raise_for_status()

        return [
            SettlementReconResponse(
                entity_id=item["entity_id"],
                entity_type=item["type"],
                debit=item["debit"],
                credit=item["credit"],
                amount=item["amount"],
                currency=item["currency"],
                fee=item["fee"],
                tax=item["tax"],
                settled=item["settled"],
                settlement_id=item.get("settlement_id"),
                settlement_utr=item.get("settlement_utr"),
                order_id=item.get("order_id"),
                payment_id=item.get("payment_id"),
                created_at=item["created_at"],
                settled_at=item.get("settled_at"),
                description=item.get("description"),
            )
            for item in response.json()["items"]
        ]

    @staticmethod
    def _map_payment(response: dict) -> PaymentResponse:
        return PaymentResponse(
            payment_id=response["id"],
            order_id=response.get("order_id"),
            amount=response["amount"],
            currency=response["currency"],
            status=response["status"],
            method=response.get("method"),
            captured=bool(response.get("captured")),
            fee=response.get("fee"),
            tax=response.get("tax"),
            created_at=response["created_at"],
            captured_at=response.get("captured_at"),
        )