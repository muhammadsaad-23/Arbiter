import asyncio
import heapq
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
from collections import defaultdict


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    order_id: str
    user_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_short: bool = False
    
    fills: List[Tuple[float, int, datetime]] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.order_id:
            self.order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    def add_fill(self, price: float, quantity: int):
        self.fills.append((price, quantity, datetime.now()))
        
        total_value = self.avg_fill_price * self.filled_quantity + price * quantity
        self.filled_quantity += quantity
        self.avg_fill_price = total_value / self.filled_quantity if self.filled_quantity > 0 else 0
        
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.now()

    def cancel(self):
        if self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            self.status = OrderStatus.CANCELLED
            self.updated_at = datetime.now()
            return True
        return False

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'filled_quantity': self.filled_quantity,
            'remaining': self.remaining_quantity,
            'avg_fill_price': self.avg_fill_price,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'is_short': self.is_short
        }


class OrderBookLevel:
    def __init__(self, price: float):
        self.price = price
        self.orders: List[Order] = []
        self.total_quantity = 0
    
    def add_order(self, order: Order):
        self.orders.append(order)
        self.total_quantity += order.remaining_quantity
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                removed = self.orders.pop(i)
                self.total_quantity -= removed.remaining_quantity
                return removed
        return None
    
    def is_empty(self) -> bool:
        return len(self.orders) == 0


class OrderBook:
    def __init__(self, symbol: str, logger=None, max_depth: int = 50):
        self.symbol = symbol
        self._logger = logger
        self._max_depth = max_depth
        
        self._bids: Dict[float, OrderBookLevel] = {}
        self._asks: Dict[float, OrderBookLevel] = {}
        
        # heaps for fast best price lookup
        self._bid_prices: List[float] = []  # negative for max-heap
        self._ask_prices: List[float] = []
        
        self._orders: Dict[str, Order] = {}
        self._stop_orders: Dict[float, List[Order]] = defaultdict(list)
        
        self._trade_callbacks: List[Callable] = []
        self._lock = threading.RLock()
        
        self._total_trades = 0
        self._total_volume = 0

    @property
    def best_bid(self) -> Optional[float]:
        with self._lock:
            while self._bid_prices:
                price = -self._bid_prices[0]
                if price in self._bids and not self._bids[price].is_empty():
                    return price
                heapq.heappop(self._bid_prices)
            return None

    @property
    def best_ask(self) -> Optional[float]:
        with self._lock:
            while self._ask_prices:
                price = self._ask_prices[0]
                if price in self._asks and not self._asks[price].is_empty():
                    return price
                heapq.heappop(self._ask_prices)
            return None

    @property
    def spread(self) -> Optional[float]:
        bid = self.best_bid
        ask = self.best_ask
        if bid and ask:
            return ask - bid
        return None

    @property
    def mid_price(self) -> Optional[float]:
        bid = self.best_bid
        ask = self.best_ask
        if bid and ask:
            return (bid + ask) / 2
        return None

    def register_trade_callback(self, callback: Callable):
        self._trade_callbacks.append(callback)

    def submit_order(self, order: Order) -> Tuple[bool, str]:
        with self._lock:
            if order.quantity <= 0:
                order.status = OrderStatus.REJECTED
                return False, "Invalid quantity"
            
            if order.order_type == OrderType.LIMIT and order.price is None:
                order.status = OrderStatus.REJECTED
                return False, "Limit order needs price"
            
            if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT] and order.stop_price is None:
                order.status = OrderStatus.REJECTED
                return False, "Stop order needs stop price"
            
            self._orders[order.order_id] = order
            order.status = OrderStatus.OPEN
            
            if self._logger:
                self._logger.log_order_placed(
                    order.order_id, order.user_id, order.symbol,
                    order.side.value, order.order_type.value,
                    order.quantity, order.price
                )
            
            if order.order_type == OrderType.MARKET:
                return self._execute_market_order(order)
            elif order.order_type == OrderType.LIMIT:
                return self._process_limit_order(order)
            elif order.order_type in [OrderType.STOP_LOSS, OrderType.TAKE_PROFIT, OrderType.STOP_LIMIT]:
                return self._add_stop_order(order)
            
            return True, "Order submitted"

    def _execute_market_order(self, order: Order) -> Tuple[bool, str]:
        if order.side == OrderSide.BUY:
            book = self._asks
            price_heap = self._ask_prices
            is_ascending = True
        else:
            book = self._bids
            price_heap = self._bid_prices
            is_ascending = False
        
        remaining = order.remaining_quantity
        
        while remaining > 0 and price_heap:
            if is_ascending:
                if not price_heap:
                    break
                best_price = price_heap[0]
            else:
                if not price_heap:
                    break
                best_price = -price_heap[0]
            
            if best_price not in book:
                heapq.heappop(price_heap)
                continue
            
            level = book[best_price]
            
            while remaining > 0 and level.orders:
                counter_order = level.orders[0]
                
                if not counter_order.is_active:
                    level.orders.pop(0)
                    continue
                
                fill_qty = min(remaining, counter_order.remaining_quantity)
                
                self._execute_trade(order, counter_order, best_price, fill_qty)
                
                remaining = order.remaining_quantity
                
                if counter_order.status == OrderStatus.FILLED:
                    level.orders.pop(0)
                    level.total_quantity -= fill_qty
            
            if level.is_empty():
                del book[best_price]
                heapq.heappop(price_heap)
        
        if order.filled_quantity > 0:
            return True, f"Filled {order.filled_quantity}/{order.quantity}"
        else:
            order.status = OrderStatus.REJECTED
            return False, "No liquidity"

    def _process_limit_order(self, order: Order) -> Tuple[bool, str]:
        # try to match first
        if order.side == OrderSide.BUY:
            while order.remaining_quantity > 0 and self.best_ask and self.best_ask <= order.price:
                ask_price = self.best_ask
                level = self._asks[ask_price]
                
                while order.remaining_quantity > 0 and level.orders:
                    counter = level.orders[0]
                    fill_qty = min(order.remaining_quantity, counter.remaining_quantity)
                    
                    self._execute_trade(order, counter, ask_price, fill_qty)
                    
                    if counter.status == OrderStatus.FILLED:
                        level.orders.pop(0)
                        level.total_quantity -= fill_qty
                
                if level.is_empty():
                    del self._asks[ask_price]
                    if self._ask_prices and self._ask_prices[0] == ask_price:
                        heapq.heappop(self._ask_prices)
        else:
            while order.remaining_quantity > 0 and self.best_bid and self.best_bid >= order.price:
                bid_price = self.best_bid
                level = self._bids[bid_price]
                
                while order.remaining_quantity > 0 and level.orders:
                    counter = level.orders[0]
                    fill_qty = min(order.remaining_quantity, counter.remaining_quantity)
                    
                    self._execute_trade(order, counter, bid_price, fill_qty)
                    
                    if counter.status == OrderStatus.FILLED:
                        level.orders.pop(0)
                        level.total_quantity -= fill_qty
                
                if level.is_empty():
                    del self._bids[bid_price]
                    if self._bid_prices and -self._bid_prices[0] == bid_price:
                        heapq.heappop(self._bid_prices)
        
        # leftover goes to book
        if order.remaining_quantity > 0:
            self._add_to_book(order)
        
        return True, f"Processed: {order.filled_quantity}/{order.quantity} filled"

    def _add_to_book(self, order: Order):
        if order.side == OrderSide.BUY:
            if order.price not in self._bids:
                self._bids[order.price] = OrderBookLevel(order.price)
                heapq.heappush(self._bid_prices, -order.price)
            self._bids[order.price].add_order(order)
        else:
            if order.price not in self._asks:
                self._asks[order.price] = OrderBookLevel(order.price)
                heapq.heappush(self._ask_prices, order.price)
            self._asks[order.price].add_order(order)

    def _add_stop_order(self, order: Order) -> Tuple[bool, str]:
        self._stop_orders[order.stop_price].append(order)
        return True, "Stop order placed"

    def _execute_trade(self, taker: Order, maker: Order, price: float, quantity: int):
        taker.add_fill(price, quantity)
        maker.add_fill(price, quantity)
        
        self._total_trades += 1
        self._total_volume += quantity * price
        
        if taker.side == OrderSide.BUY:
            buyer_id, seller_id = taker.user_id, maker.user_id
            buyer_order_id, seller_order_id = taker.order_id, maker.order_id
        else:
            buyer_id, seller_id = maker.user_id, taker.user_id
            buyer_order_id, seller_order_id = maker.order_id, taker.order_id
        
        trade_id = f"TRD-{uuid.uuid4().hex[:12].upper()}"
        if self._logger:
            self._logger.log_trade(
                trade_id, buyer_id, seller_id, self.symbol,
                price, quantity, buyer_order_id, seller_order_id
            )
        
        trade_info = {
            'trade_id': trade_id,
            'symbol': self.symbol,
            'price': price,
            'quantity': quantity,
            'buyer_id': buyer_id,
            'seller_id': seller_id,
            'buyer_order_id': buyer_order_id,
            'seller_order_id': seller_order_id,
            'timestamp': datetime.now()
        }
        
        for callback in self._trade_callbacks:
            try:
                callback(trade_info)
            except Exception:
                pass  # dont let callbacks break us

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        with self._lock:
            if order_id not in self._orders:
                return False, "Order not found"
            
            order = self._orders[order_id]
            
            if not order.cancel():
                return False, f"Cant cancel order in {order.status.value}"
            
            if order.price:
                if order.side == OrderSide.BUY and order.price in self._bids:
                    self._bids[order.price].remove_order(order_id)
                elif order.side == OrderSide.SELL and order.price in self._asks:
                    self._asks[order.price].remove_order(order_id)
            
            if self._logger:
                self._logger.log_order_cancelled(order_id, order.user_id, order.symbol, "User requested")
            
            return True, "Order cancelled"

    def check_stop_orders(self, current_price: float):
        with self._lock:
            triggered = []
            
            for stop_price, orders in list(self._stop_orders.items()):
                for order in orders:
                    should_trigger = False
                    
                    if order.order_type == OrderType.STOP_LOSS:
                        if order.side == OrderSide.SELL and current_price <= stop_price:
                            should_trigger = True
                        elif order.side == OrderSide.BUY and current_price >= stop_price:
                            should_trigger = True
                    
                    elif order.order_type == OrderType.TAKE_PROFIT:
                        if order.side == OrderSide.SELL and current_price >= stop_price:
                            should_trigger = True
                        elif order.side == OrderSide.BUY and current_price <= stop_price:
                            should_trigger = True
                    
                    if should_trigger:
                        triggered.append(order)
                
                self._stop_orders[stop_price] = [o for o in orders if o not in triggered]
                if not self._stop_orders[stop_price]:
                    del self._stop_orders[stop_price]
            
            for order in triggered:
                order.order_type = OrderType.MARKET
                self._execute_market_order(order)

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_user_orders(self, user_id: str, active_only: bool = True) -> List[Order]:
        orders = [o for o in self._orders.values() if o.user_id == user_id]
        if active_only:
            orders = [o for o in orders if o.is_active]
        return orders

    def get_book_depth(self, levels: int = 5) -> Dict:
        with self._lock:
            bids = []
            asks = []
            
            bid_prices = sorted([p for p in self._bids.keys() if not self._bids[p].is_empty()], reverse=True)
            for price in bid_prices[:levels]:
                level = self._bids[price]
                bids.append({
                    'price': price,
                    'quantity': level.total_quantity,
                    'orders': len(level.orders)
                })
            
            ask_prices = sorted([p for p in self._asks.keys() if not self._asks[p].is_empty()])
            for price in ask_prices[:levels]:
                level = self._asks[price]
                asks.append({
                    'price': price,
                    'quantity': level.total_quantity,
                    'orders': len(level.orders)
                })
            
            return {
                'symbol': self.symbol,
                'bids': bids,
                'asks': asks,
                'spread': self.spread,
                'mid_price': self.mid_price
            }

    def get_stats(self) -> Dict:
        return {
            'symbol': self.symbol,
            'total_orders': len(self._orders),
            'active_orders': sum(1 for o in self._orders.values() if o.is_active),
            'total_trades': self._total_trades,
            'total_volume': self._total_volume,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'spread': self.spread,
            'bid_depth': sum(l.total_quantity for l in self._bids.values()),
            'ask_depth': sum(l.total_quantity for l in self._asks.values()),
            'stop_orders': sum(len(orders) for orders in self._stop_orders.values())
        }
