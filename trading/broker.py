"""
Brokerage System
================

Central broker that coordinates:
- Order routing and execution
- Portfolio management
- Risk checks
- Trade settlement
"""

import asyncio
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum

from .orderbook import OrderBook, Order, OrderType, OrderSide, OrderStatus
from .portfolio import Portfolio


@dataclass
class Trade:
    """Completed trade record."""
    trade_id: str
    symbol: str
    buyer_id: str
    seller_id: str
    price: float
    quantity: int
    buyer_order_id: str
    seller_order_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def value(self) -> float:
        return self.price * self.quantity

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'buyer_id': self.buyer_id,
            'seller_id': self.seller_id,
            'price': self.price,
            'quantity': self.quantity,
            'value': self.value,
            'timestamp': self.timestamp.isoformat()
        }


class Broker:
    """
    Central brokerage system.
    
    Features:
    - Multi-user support
    - Order validation and risk checks
    - Order routing to order books
    - Trade settlement
    - Portfolio updates
    """

    def __init__(self, config: Dict, market_engine: Any, logger: Any):
        self._config = config
        self._market = market_engine
        self._logger = logger
        
        # Configuration
        brokerage_config = config.get('brokerage', {})
        trading_config = config.get('trading', {})
        
        self._initial_balance = brokerage_config.get('initial_balance', 100000.0)
        self._transaction_fee = trading_config.get('transaction_fee', 0.001)
        self._margin_requirement = trading_config.get('margin_requirement', 0.5)
        self._short_selling_enabled = trading_config.get('short_selling_enabled', True)
        self._partial_fills_enabled = trading_config.get('partial_fills_enabled', True)
        self._min_order_size = trading_config.get('min_order_size', 1)
        self._max_order_size = trading_config.get('max_order_size', 100000)
        
        # Order books by symbol
        self._order_books: Dict[str, OrderBook] = {}
        
        # User portfolios
        self._portfolios: Dict[str, Portfolio] = {}
        
        # Trade history
        self._trades: List[Trade] = []
        
        # Callbacks
        self._trade_callbacks: List[Callable] = []
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        # Stats
        self._total_orders = 0
        self._rejected_orders = 0

    async def initialize(self):
        """Initialize broker with order books for all symbols."""
        symbols = self._market.asset_manager.get_symbols()
        
        for symbol in symbols:
            order_book = OrderBook(symbol, self._logger)
            order_book.register_trade_callback(self._on_trade)
            self._order_books[symbol] = order_book
        
        # Seed initial market maker liquidity
        await self._seed_liquidity()

    async def _seed_liquidity(self):
        """Seed order books with market maker liquidity."""
        for symbol in self._order_books.keys():
            await self._add_market_maker_quotes(symbol)

    async def _add_market_maker_quotes(self, symbol: str):
        """Add bid/ask quotes from market maker."""
        asset = self._market.asset_manager.get_asset(symbol)
        if not asset:
            return
        
        price = asset.price
        book = self._order_books[symbol]
        
        # Create market maker quotes at multiple levels
        spread_pct = 0.001  # 0.1% spread
        
        for i in range(5):  # 5 levels of depth
            level_offset = spread_pct * (i + 1)
            quantity = 1000 * (5 - i)  # More liquidity at tighter levels
            
            # Bid side (buy orders)
            bid_price = round(price * (1 - level_offset), 2)
            bid_order = Order(
                order_id=f"MM-BID-{symbol}-{i}",
                user_id="MARKET_MAKER",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=bid_price
            )
            book.submit_order(bid_order)
            
            # Ask side (sell orders)
            ask_price = round(price * (1 + level_offset), 2)
            ask_order = Order(
                order_id=f"MM-ASK-{symbol}-{i}",
                user_id="MARKET_MAKER",
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=ask_price
            )
            book.submit_order(ask_order)

    async def refresh_liquidity(self):
        """Refresh market maker quotes (call periodically)."""
        for symbol in self._order_books.keys():
            # Cancel old MM orders and add new ones at current prices
            book = self._order_books[symbol]
            
            # Get current MM orders and cancel them
            mm_orders = [o for o in book._orders.values() 
                        if o.user_id == "MARKET_MAKER" and o.is_active]
            for order in mm_orders:
                book.cancel_order(order.order_id)
            
            # Add fresh quotes
            await self._add_market_maker_quotes(symbol)

    def get_or_create_portfolio(self, user_id: str) -> Portfolio:
        """Get existing portfolio or create new one."""
        if user_id not in self._portfolios:
            self._portfolios[user_id] = Portfolio(
                user_id=user_id,
                initial_balance=self._initial_balance,
                transaction_fee_pct=self._transaction_fee,
                margin_requirement=self._margin_requirement
            )
        return self._portfolios[user_id]

    def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        """Get portfolio for user."""
        return self._portfolios.get(user_id)

    def get_all_portfolios(self) -> List[Portfolio]:
        """Get all portfolios."""
        return list(self._portfolios.values())

    async def submit_order(self, user_id: str, symbol: str, side: str,
                          order_type: str, quantity: int,
                          price: Optional[float] = None,
                          stop_price: Optional[float] = None,
                          is_short: bool = False) -> Tuple[bool, str, Optional[Order]]:
        """
        Submit a new order.
        
        Returns (success, message, order).
        """
        async with self._lock:
            self._total_orders += 1
            
            # Validate inputs
            validation = await self._validate_order(
                user_id, symbol, side, order_type, quantity, price, stop_price, is_short
            )
            if not validation[0]:
                self._rejected_orders += 1
                self._logger.log_validation_failure(
                    user_id, "order_submit", validation[1],
                    {'symbol': symbol, 'quantity': quantity}
                )
                return validation[0], validation[1], None
            
            # Get portfolio
            portfolio = self.get_or_create_portfolio(user_id)
            
            # Additional balance check for buys
            if side.lower() == 'buy':
                current_price = price or self._market.get_price(symbol)
                if current_price is None:
                    return False, "Cannot determine price", None
                
                can_buy, msg = portfolio.can_buy(symbol, quantity, current_price)
                if not can_buy:
                    self._rejected_orders += 1
                    return False, msg, None
            
            # Check for sells
            if side.lower() == 'sell' and not is_short:
                can_sell, msg = portfolio.can_sell(symbol, quantity, is_short)
                if not can_sell:
                    self._rejected_orders += 1
                    return False, msg, None
            
            # Create order
            order = Order(
                order_id=f"ORD-{uuid.uuid4().hex[:12].upper()}",
                user_id=user_id,
                symbol=symbol,
                side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
                order_type=OrderType[order_type.upper()],
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                is_short=is_short
            )
            
            # Submit to order book
            order_book = self._order_books.get(symbol)
            if not order_book:
                return False, f"No order book for {symbol}", None
            
            success, message = order_book.submit_order(order)
            
            # Handle immediate fills for market orders
            if order.filled_quantity > 0:
                await self._settle_fills(order, portfolio)
            
            return success, message, order

    async def _validate_order(self, user_id: str, symbol: str, side: str,
                             order_type: str, quantity: int,
                             price: Optional[float], stop_price: Optional[float],
                             is_short: bool) -> Tuple[bool, str]:
        """Validate order parameters."""
        # Check symbol exists
        if symbol not in self._order_books:
            return False, f"Unknown symbol: {symbol}"
        
        # Check asset is not halted
        asset = self._market.asset_manager.get_asset(symbol)
        if asset and asset.is_halted:
            return False, f"{symbol} is halted: {asset.halt_reason}"
        
        # Check quantity
        if quantity < self._min_order_size:
            return False, f"Quantity below minimum ({self._min_order_size})"
        if quantity > self._max_order_size:
            return False, f"Quantity above maximum ({self._max_order_size})"
        
        # Check side
        if side.lower() not in ['buy', 'sell']:
            return False, "Side must be 'buy' or 'sell'"
        
        # Check order type
        valid_types = ['market', 'limit', 'stop_loss', 'take_profit', 'stop_limit']
        if order_type.lower() not in valid_types:
            return False, f"Invalid order type: {order_type}"
        
        # Check limit price for limit orders
        if order_type.lower() == 'limit' and (price is None or price <= 0):
            return False, "Limit order requires positive price"
        
        # Check stop price for stop orders
        if order_type.lower() in ['stop_loss', 'take_profit', 'stop_limit']:
            if stop_price is None or stop_price <= 0:
                return False, "Stop order requires positive stop price"
        
        # Check short selling
        if is_short and not self._short_selling_enabled:
            return False, "Short selling is disabled"
        
        return True, "OK"

    async def _settle_fills(self, order: Order, portfolio: Portfolio):
        """Settle filled portions of an order."""
        for fill_price, fill_qty, fill_time in order.fills:
            if order.side == OrderSide.BUY:
                success, cost, msg = portfolio.execute_buy(
                    order.symbol, fill_qty, fill_price, order.order_id
                )
            else:
                success, proceeds, msg = portfolio.execute_sell(
                    order.symbol, fill_qty, fill_price, order.is_short, order.order_id
                )

    def _on_trade(self, trade_info: Dict):
        """Handle trade execution callback from order book."""
        trade = Trade(
            trade_id=trade_info['trade_id'],
            symbol=trade_info['symbol'],
            buyer_id=trade_info['buyer_id'],
            seller_id=trade_info['seller_id'],
            price=trade_info['price'],
            quantity=trade_info['quantity'],
            buyer_order_id=trade_info['buyer_order_id'],
            seller_order_id=trade_info['seller_order_id'],
            timestamp=trade_info['timestamp']
        )
        self._trades.append(trade)
        
        # Update portfolios
        buyer_portfolio = self._portfolios.get(trade.buyer_id)
        seller_portfolio = self._portfolios.get(trade.seller_id)
        
        # Note: Portfolio updates happen in _settle_fills for the order initiator
        # For passive orders (market makers), we'd need additional handling
        
        # Notify callbacks
        for callback in self._trade_callbacks:
            try:
                callback(trade)
            except Exception:
                pass

    async def cancel_order(self, user_id: str, order_id: str) -> Tuple[bool, str]:
        """Cancel an order."""
        async with self._lock:
            # Find the order book containing this order
            for symbol, book in self._order_books.items():
                order = book.get_order(order_id)
                if order and order.user_id == user_id:
                    return book.cancel_order(order_id)
            
            return False, "Order not found"

    async def modify_order(self, user_id: str, order_id: str,
                          new_quantity: Optional[int] = None,
                          new_price: Optional[float] = None) -> Tuple[bool, str]:
        """Modify an existing order."""
        async with self._lock:
            # Find the order
            for symbol, book in self._order_books.items():
                order = book.get_order(order_id)
                if order and order.user_id == user_id:
                    if not order.is_active:
                        return False, f"Cannot modify order in status {order.status.value}"
                    
                    # Cancel and resubmit with new parameters
                    success, msg = book.cancel_order(order_id)
                    if not success:
                        return False, msg
                    
                    # Create new order with updated params
                    new_order = Order(
                        order_id=f"ORD-{uuid.uuid4().hex[:12].upper()}",
                        user_id=user_id,
                        symbol=symbol,
                        side=order.side,
                        order_type=order.order_type,
                        quantity=new_quantity or order.remaining_quantity,
                        price=new_price or order.price,
                        stop_price=order.stop_price,
                        is_short=order.is_short
                    )
                    
                    return book.submit_order(new_order)
            
            return False, "Order not found"

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        for book in self._order_books.values():
            order = book.get_order(order_id)
            if order:
                return order
        return None

    def get_user_orders(self, user_id: str, symbol: Optional[str] = None,
                       active_only: bool = True) -> List[Order]:
        """Get orders for a user."""
        orders = []
        books = [self._order_books[symbol]] if symbol else self._order_books.values()
        
        for book in books:
            orders.extend(book.get_user_orders(user_id, active_only))
        
        return orders

    def get_order_book_depth(self, symbol: str, levels: int = 5) -> Optional[Dict]:
        """Get order book depth for a symbol."""
        if symbol not in self._order_books:
            return None
        return self._order_books[symbol].get_book_depth(levels)

    async def update_stop_orders(self):
        """Check and trigger stop orders based on current prices."""
        for symbol, book in self._order_books.items():
            current_price = self._market.get_price(symbol)
            if current_price:
                book.check_stop_orders(current_price)

    def get_trade_history(self, symbol: Optional[str] = None,
                         limit: int = 100) -> List[Dict]:
        """Get recent trades."""
        trades = self._trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        return [t.to_dict() for t in trades[-limit:]]

    def register_trade_callback(self, callback: Callable):
        """Register callback for trade notifications."""
        self._trade_callbacks.append(callback)

    def get_broker_stats(self) -> Dict:
        """Get broker statistics."""
        total_value = sum(
            t.value for t in self._trades
        )
        
        return {
            'total_orders': self._total_orders,
            'rejected_orders': self._rejected_orders,
            'rejection_rate': (self._rejected_orders / self._total_orders * 100) if self._total_orders > 0 else 0,
            'total_trades': len(self._trades),
            'total_trade_value': total_value,
            'active_users': len(self._portfolios),
            'order_books': len(self._order_books),
            'active_orders': sum(book.get_stats()['active_orders'] for book in self._order_books.values())
        }

    def get_market_depth_summary(self) -> Dict[str, Dict]:
        """Get summary of market depth for all symbols."""
        return {
            symbol: book.get_stats()
            for symbol, book in self._order_books.items()
        }

    async def run_settlement_cycle(self):
        """
        Run periodic settlement tasks.
        
        - Update stop orders
        - Process pending settlements
        - Update margin requirements
        """
        await self.update_stop_orders()
        
        # Update portfolio values for margin checks
        prices = {
            symbol: self._market.get_price(symbol)
            for symbol in self._order_books.keys()
        }
        prices = {k: v for k, v in prices.items() if v is not None}
        
        for portfolio in self._portfolios.values():
            portfolio.update_peak_value(prices)


class TradingAPI:
    """
    High-level trading API for bots and users.
    
    Provides simple interface for common trading operations.
    """

    def __init__(self, broker: Broker, user_id: str):
        self._broker = broker
        self._user_id = user_id

    @property
    def portfolio(self) -> Portfolio:
        return self._broker.get_or_create_portfolio(self._user_id)

    async def buy_market(self, symbol: str, quantity: int) -> Tuple[bool, str]:
        """Place a market buy order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'buy', 'market', quantity
        )
        return success, msg

    async def sell_market(self, symbol: str, quantity: int) -> Tuple[bool, str]:
        """Place a market sell order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'sell', 'market', quantity
        )
        return success, msg

    async def buy_limit(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:
        """Place a limit buy order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'buy', 'limit', quantity, price=price
        )
        return success, msg

    async def sell_limit(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:
        """Place a limit sell order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'sell', 'limit', quantity, price=price
        )
        return success, msg

    async def set_stop_loss(self, symbol: str, quantity: int, stop_price: float) -> Tuple[bool, str]:
        """Set a stop-loss order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'sell', 'stop_loss', quantity, stop_price=stop_price
        )
        return success, msg

    async def set_take_profit(self, symbol: str, quantity: int, target_price: float) -> Tuple[bool, str]:
        """Set a take-profit order."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'sell', 'take_profit', quantity, stop_price=target_price
        )
        return success, msg

    async def short_sell(self, symbol: str, quantity: int) -> Tuple[bool, str]:
        """Short sell a symbol."""
        success, msg, order = await self._broker.submit_order(
            self._user_id, symbol, 'sell', 'market', quantity, is_short=True
        )
        return success, msg

    async def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """Cancel an order."""
        return await self._broker.cancel_order(self._user_id, order_id)

    def get_position(self, symbol: str):
        """Get position for a symbol."""
        return self.portfolio.get_position(symbol)

    def get_cash(self) -> float:
        """Get available cash."""
        return self.portfolio.cash

    def get_orders(self, active_only: bool = True) -> List[Order]:
        """Get all orders."""
        return self._broker.get_user_orders(self._user_id, active_only=active_only)

