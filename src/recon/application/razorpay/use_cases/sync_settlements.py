    from __future__ import annotations

    from recon.application.razorpay.dto.requests import FetchSettlementReconRequest
    from recon.application.razorpay.ports.gateway import RazorpayGateway
    from recon.application.razorpay.ports.repository import RazorpayRepository
    from recon.application.razorpay.services.mappers import (
        map_adjustment_response_to_domain,
        map_payment_response_to_domain,
        map_refund_response_to_domain,
        map_settlement_recon_to_domain,
        map_settlement_response_to_domain,
        map_transfer_response_to_domain,
    )

    class SyncRazorpaySettlementUseCase:

        def __init__(
            self,
            gateway: RazorpayGateway,
            repository: RazorpayRepository,
        ) -> None:
            self.gateway = gateway
            self.repository = repository

        async def execute(
            self,
            request: FetchSettlementReconRequest,
        ) -> None:

            settlements = await self.gateway.fetch_settlements()

            for settlement_response in settlements:
                settlement = map_settlement_response_to_domain(settlement_response)
                await self.repository.save_settlement(settlement)

                recon_rows = await self.gateway.fetch_settlement_recon(request)

                for row in recon_rows:
                    if row.settlement_id != settlement.settlement_id:
                        continue

                    entry = map_settlement_recon_to_domain(row)
                    await self.repository.save_settlement_entry(entry)

                    if row.entity_type == "payment":
                        response = await self.gateway.fetch_payment(row.entity_id)
                        payment = map_payment_response_to_domain(response)
                        await self.repository.save_payment(payment)

                    elif row.entity_type == "refund":
                        response = await self.gateway.fetch_refund(row.payment_id, row.entity_id)
                        refund = map_refund_response_to_domain(response)
                        await self.repository.save_refund(refund)

                    elif row.entity_type == "transfer":
                        response = await self.gateway.fetch_transfer(row.entity_id)
                        transfer = map_transfer_response_to_domain(response)
                        await self.repository.save_transfer(transfer)

                    elif row.entity_type == "adjustment":
                        response = await self.gateway.fetch_adjustment(row.entity_id)
                        adjustment = map_adjustment_response_to_domain(response)
                        await self.repository.save_adjustment(adjustment)