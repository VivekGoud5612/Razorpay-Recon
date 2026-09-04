import asyncio 
from decimal import Decimal 

from recon.application.reconciliation.dto.request import ReconcileSettlementRequest
from recon.application.reconciliation.services.reconciliation_service import ReconcileSettlementService
from recon.application.reconciliation.use_cases.reconcile_setlement import ReconcileSettlementUseCase
from recon.infrastructure.persistence.postgres.connection import PostgresConnection
from recon.infrastructure.persistence.postgres.config import DatabaseConfig
from recon.infrastructure.persistence.postgres.repository import ReconcileSettlementPostgresRepository


async def main() -> None:
    db = PostgresConnection(DatabaseConfig.from_env())
    await db.connect()

    try:
        repository = ReconcileSettlementPostgresRepository(db)
        service = ReconcileSettlementService()

        use_case = ReconcileSettlementUseCase(
            repository=repository,
            service=service,
        )

        request = ReconcileSettlementRequest(
            settlement_id="setl_demo_001",
            source_ids=[
                "SRC_ERP_01",
                "SRC_BANK_01",
            ],
        )

        result = await use_case.execute(request)

        print(result)
    
    finally:
        await db.close()

    
if __name__ == "__main__":
    asyncio.run(main())