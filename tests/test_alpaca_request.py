from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from aegis_alpha.broker.alpaca_gateway import AlpacaGateway
from aegis_alpha.models import OrderIntent


class TradingStub:
    def __init__(self) -> None:
        self.request = None

    def submit_order(self, order_data):
        self.request = order_data
        return SimpleNamespace(
            id=uuid4(),
            status=SimpleNamespace(value="accepted"),
            model_dump=lambda mode: {"status": "accepted"},
        )


def test_atomic_multi_leg_order_request(candidate) -> None:
    intent = OrderIntent.from_candidate("cycle", candidate, 1, 0.4, -0.3)
    gateway = AlpacaGateway.__new__(AlpacaGateway)
    gateway.trading = TradingStub()
    result = gateway.submit_spread(intent, dry_run=False)
    request = gateway.trading.request
    assert result.status == "accepted"
    assert request.order_class.value == "mleg"
    assert len(request.legs) == 2
    assert request.client_order_id == intent.client_order_id
