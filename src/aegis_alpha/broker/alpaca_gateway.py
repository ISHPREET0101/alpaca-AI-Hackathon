from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from alpaca.data.enums import DataFeed, OptionsFeed
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    ContractType,
    OrderClass,
    OrderSide,
    OrderType,
    PositionIntent,
    TimeInForce,
)
from alpaca.trading.requests import GetOptionContractsRequest, LimitOrderRequest, OptionLegRequest

from aegis_alpha.config import Settings
from aegis_alpha.models import (
    AccountSnapshot,
    ExecutionRecord,
    MarketBar,
    MarketClock,
    OptionSnapshot,
    OptionType,
    OrderIntent,
    PositionSnapshot,
)


def _request_id_from_exception(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) if response is not None else {}
    return headers.get("X-Request-ID") or headers.get("x-request-id")


class AlpacaGateway:
    def __init__(self, settings: Settings) -> None:
        settings.validate_safety(require_credentials=True)
        self.settings = settings
        self.trading = TradingClient(
            settings.api_key,
            settings.secret_key,
            paper=True,
            url_override=settings.base_url,
        )
        self.stocks = StockHistoricalDataClient(settings.api_key, settings.secret_key)
        self.options = OptionHistoricalDataClient(settings.api_key, settings.secret_key)

    def get_account(self) -> AccountSnapshot:
        account = self.trading.get_account()
        return AccountSnapshot(
            account_id=str(account.id),
            equity=float(account.equity),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            options_buying_power=float(account.options_buying_power or account.buying_power),
            status=getattr(account.status, "value", str(account.status)),
        )

    def get_clock(self) -> MarketClock:
        clock = self.trading.get_clock()
        return MarketClock(
            timestamp=clock.timestamp,
            is_open=clock.is_open,
            next_open=clock.next_open,
            next_close=clock.next_close,
        )

    def get_bars(self, symbol: str, end: datetime | None = None) -> list[MarketBar]:
        end = end or datetime.now(timezone.utc)
        feed = DataFeed(self.settings.data_feed)
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame(5, TimeFrameUnit.Minute),
            start=end - timedelta(days=5),
            end=end,
            limit=300,
            feed=feed,
        )
        response = self.stocks.get_stock_bars(request)
        raw_bars = response.data.get(symbol, [])
        return [
            MarketBar(
                timestamp=bar.timestamp,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=float(bar.volume),
                vwap=float(bar.vwap) if bar.vwap is not None else None,
            )
            for bar in raw_bars
        ]

    def get_option_chain(self, symbol: str, now: datetime | None = None) -> list[OptionSnapshot]:
        now = now or datetime.now(timezone.utc)
        minimum = now.date() + timedelta(days=self.settings.min_dte)
        maximum = now.date() + timedelta(days=self.settings.max_dte)
        contracts_response = self.trading.get_option_contracts(
            GetOptionContractsRequest(
                underlying_symbols=[symbol],
                expiration_date_gte=minimum,
                expiration_date_lte=maximum,
                limit=1_000,
            )
        )
        contracts = {contract.symbol: contract for contract in contracts_response.option_contracts}
        snapshots = self.options.get_option_chain(
            OptionChainRequest(
                underlying_symbol=symbol,
                expiration_date_gte=minimum,
                expiration_date_lte=maximum,
                feed=OptionsFeed.INDICATIVE,
            )
        )
        result: list[OptionSnapshot] = []
        for contract_symbol, snapshot in snapshots.items():
            contract = contracts.get(contract_symbol)
            quote = snapshot.latest_quote
            greeks = snapshot.greeks
            if contract is None or quote is None or greeks is None or greeks.delta is None:
                continue
            if quote.ask_price is None or quote.bid_price is None or quote.timestamp is None:
                continue
            option_type = OptionType.CALL if contract.type is ContractType.CALL else OptionType.PUT
            try:
                result.append(
                    OptionSnapshot(
                        symbol=contract.symbol,
                        underlying=contract.underlying_symbol,
                        expiry=contract.expiration_date,
                        strike=float(contract.strike_price),
                        option_type=option_type,
                        bid=float(quote.bid_price),
                        ask=float(quote.ask_price),
                        delta=float(greeks.delta),
                        quote_timestamp=quote.timestamp,
                        tradable=bool(contract.tradable),
                    )
                )
            except ValueError:
                continue
        return result

    def get_positions(self) -> list[PositionSnapshot]:
        positions = self.trading.get_all_positions()
        return [
            PositionSnapshot(
                symbol=position.symbol,
                quantity=float(position.qty),
                market_value=float(position.market_value or 0),
                unrealized_pl=float(position.unrealized_pl or 0),
                asset_class=getattr(position.asset_class, "value", str(position.asset_class)),
            )
            for position in positions
        ]

    def submit_spread(self, intent: OrderIntent, dry_run: bool) -> ExecutionRecord:
        if dry_run:
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=intent.client_order_id,
                status="dry_run",
                dry_run=True,
                raw=intent.model_dump(mode="json"),
            )
        legs = [
            OptionLegRequest(
                symbol=leg.symbol,
                ratio_qty=1,
                side=OrderSide(leg.side.value),
                position_intent=PositionIntent(leg.position_intent),
            )
            for leg in intent.legs
        ]
        request = LimitOrderRequest(
            qty=intent.quantity,
            type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            client_order_id=intent.client_order_id,
            legs=legs,
            limit_price=round(intent.limit_debit, 2),
        )
        try:
            order = self.trading.submit_order(order_data=request)
            raw: dict[str, Any] = order.model_dump(mode="json")
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=intent.client_order_id,
                alpaca_order_id=str(order.id),
                status=getattr(order.status, "value", str(order.status)),
                dry_run=False,
                raw=raw,
            )
        except Exception as exc:
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=intent.client_order_id,
                request_id=_request_id_from_exception(exc),
                status="error",
                error=str(exc),
                dry_run=False,
            )

    def close_spread(
        self, intent: OrderIntent, limit_credit: float, dry_run: bool
    ) -> ExecutionRecord:
        close_id = f"{intent.client_order_id}-close"
        if dry_run:
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=close_id,
                status="dry_run",
                dry_run=True,
                raw={"limit_credit": limit_credit},
            )
        legs = []
        for leg in intent.legs:
            if leg.side.value == "buy":
                side = OrderSide.SELL
                position_intent = PositionIntent.SELL_TO_CLOSE
            else:
                side = OrderSide.BUY
                position_intent = PositionIntent.BUY_TO_CLOSE
            legs.append(
                OptionLegRequest(
                    symbol=leg.symbol,
                    ratio_qty=1,
                    side=side,
                    position_intent=position_intent,
                )
            )
        request = LimitOrderRequest(
            qty=intent.quantity,
            type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            client_order_id=close_id,
            legs=legs,
            limit_price=-round(abs(limit_credit), 2),
        )
        try:
            order = self.trading.submit_order(order_data=request)
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=close_id,
                alpaca_order_id=str(order.id),
                status=getattr(order.status, "value", str(order.status)),
                dry_run=False,
                raw=order.model_dump(mode="json"),
            )
        except Exception as exc:
            return ExecutionRecord(
                cycle_id=intent.cycle_id,
                client_order_id=close_id,
                request_id=_request_id_from_exception(exc),
                status="error",
                error=str(exc),
                dry_run=False,
            )
