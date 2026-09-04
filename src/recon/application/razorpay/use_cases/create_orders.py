from __future__ import annotations

from recon.application.razorpay.dto.requests import CreateOrderRequest
from recon.application.razorpay.ports.gateway import RazorpayGateway
from recon.application.razorpay.ports.repository import RazorpayRepository
from recon.application.razorpay.services.mappers import (
    map_order_response_to_domain,
)


class CreateRazorpayOrderUseCase:
    def __init__(
        self,
        gateway: RazorpayGateway,
        repository: RazorpayRepository,
    ) -> None:
        self.gateway = gateway
        self.repository = repository

    async def execute(
        self,
        request: CreateOrderRequest,
    ) -> str:

        response = await self.gateway.create_order(request)
        order = map_order_response_to_domain(response)

        await self.repository.save_order(order)

        return order.order_id