from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from recon.domain.payment.state import PaymentState


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_payment_state():
    state = PaymentState(
        payment_id="pay_001",
        order_id="order_001",
        status="captured",
        amount=Decimal("5000.00"),
        last_event_id="evt_002",
        last_event_occurred_at=NOW,
        updated_at=NOW,
    )

    assert state.payment_id == "pay_001"
    assert state.order_id == "order_001"
    assert state.status == "captured"
    assert state.amount == Decimal("5000.00")
    assert state.last_event_id == "evt_002"