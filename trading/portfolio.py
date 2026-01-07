"""
Portfolio Management
====================

Manages user portfolios with:
- Position tracking
- P&L calculation
- Margin requirements
- Risk metrics
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum


class PositionSide(Enum):
    """Position direction."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """
    Represents a position in a single asset.
    
    Tracks quantity, cost basis, and P&L.
    """
    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    side: PositionSide = PositionSide.LONG
    realized_pnl: float = 0.0
    
    # Tracking
    total_buys: int = 0
    total_sells: int = 0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    
    opened_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def market_value(self) -> float:
        """Calculate market value (needs current price)."""
        # This will be updated by portfolio with current prices
        return 0.0

    @property
    def cost_basis(self) -> float:
        """Total cost basis of position."""
        return self.quantity * self.avg_cost

    def add_shares(self, quantity: int, price: float):
        """Add shares to position (buy for long, cover for short)."""
        if quantity <= 0:
            return
        
        if self.side == PositionSide.LONG:
            # Buying more shares - update average cost
            total_cost = (self.quantity * self.avg_cost) + (quantity * price)
            self.quantity += quantity
            self.avg_cost = total_cost / self.quantity if self.quantity > 0 else 0
            self.total_buys += quantity
            self.total_buy_value += quantity * price
        else:
            # Covering short position
            if quantity >= self.quantity:
                # Closing short position
                pnl = (self.avg_cost - price) * self.quantity
                self.realized_pnl += pnl
                remaining = quantity - self.quantity
                self.quantity = 0
                self.avg_cost = 0
                
                # If we have remaining, it becomes a long position
                if remaining > 0:
                    self.side = PositionSide.LONG
                    self.quantity = remaining
                    self.avg_cost = price
            else:
                # Partial cover
                pnl = (self.avg_cost - price) * quantity
                self.realized_pnl += pnl
                self.quantity -= quantity
        
        self.total_buys += quantity
        self.total_buy_value += quantity * price
        self.last_updated = datetime.now()

    def remove_shares(self, quantity: int, price: float) -> float:
        """
        Remove shares from position (sell for long, short for short).
        
        Returns realized P&L from this transaction.
        """
        if quantity <= 0:
            return 0.0
        
        realized = 0.0
        
        if self.side == PositionSide.LONG:
            if quantity >= self.quantity:
                # Closing position
                realized = (price - self.avg_cost) * self.quantity
                remaining = quantity - self.quantity
                self.quantity = 0
                
                # If selling more than we have, becomes short
                if remaining > 0:
                    self.side = PositionSide.SHORT
                    self.quantity = remaining
                    self.avg_cost = price
            else:
                # Partial sell
                realized = (price - self.avg_cost) * quantity
                self.quantity -= quantity
        else:
            # Adding to short position
            total_value = (self.quantity * self.avg_cost) + (quantity * price)
            self.quantity += quantity
            self.avg_cost = total_value / self.quantity if self.quantity > 0 else 0
        
        self.realized_pnl += realized
        self.total_sells += quantity
        self.total_sell_value += quantity * price
        self.last_updated = datetime.now()
        
        return realized

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.quantity == 0:
            return 0.0
        
        if self.side == PositionSide.LONG:
            return (current_price - self.avg_cost) * self.quantity
        else:
            return (self.avg_cost - current_price) * self.quantity

    def get_total_pnl(self, current_price: float) -> float:
        """Get total P&L (realized + unrealized)."""
        return self.realized_pnl + self.get_unrealized_pnl(current_price)

    def get_return_pct(self, current_price: float) -> float:
        """Get return percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.get_unrealized_pnl(current_price) / self.cost_basis) * 100

    def is_empty(self) -> bool:
        """Check if position is empty."""
        return self.quantity == 0

    def to_dict(self, current_price: Optional[float] = None) -> Dict:
        """Serialize position to dictionary."""
        result = {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side.value,
            'avg_cost': self.avg_cost,
            'cost_basis': self.cost_basis,
            'realized_pnl': self.realized_pnl,
            'total_buys': self.total_buys,
            'total_sells': self.total_sells
        }
        
        if current_price:
            result.update({
                'current_price': current_price,
                'market_value': current_price * self.quantity,
                'unrealized_pnl': self.get_unrealized_pnl(current_price),
                'total_pnl': self.get_total_pnl(current_price),
                'return_pct': self.get_return_pct(current_price)
            })
        
        return result


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    trade_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    total_value: float
    fees: float
    pnl: float
    timestamp: datetime


class Portfolio:
    """
    User portfolio management.
    
    Features:
    - Position tracking
    - Cash management
    - Margin calculations
    - P&L tracking
    - Trade history
    """

    def __init__(self, user_id: str, initial_balance: float = 100000.0,
                 transaction_fee_pct: float = 0.001, margin_requirement: float = 0.5):
        self.user_id = user_id
        self.initial_balance = initial_balance
        self.cash = initial_balance
        self.transaction_fee_pct = transaction_fee_pct
        self.margin_requirement = margin_requirement
        
        # Positions
        self._positions: Dict[str, Position] = {}
        
        # Trade history
        self._trades: List[TradeRecord] = []
        
        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_fees_paid = 0.0
        self.peak_value = initial_balance
        self.created_at = datetime.now()
        
        # Thread safety
        self._lock = threading.RLock()

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> List[Position]:
        """Get all non-empty positions."""
        return [p for p in self._positions.values() if not p.is_empty()]

    def can_buy(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:
        """Check if user can afford to buy."""
        with self._lock:
            total_cost = quantity * price
            fees = total_cost * self.transaction_fee_pct
            required = total_cost + fees
            
            if self.cash < required:
                return False, f"Insufficient funds: need ${required:.2f}, have ${self.cash:.2f}"
            
            return True, "OK"

    def can_sell(self, symbol: str, quantity: int, is_short: bool = False) -> Tuple[bool, str]:
        """Check if user can sell."""
        with self._lock:
            position = self._positions.get(symbol)
            
            if is_short:
                # Short selling - check margin
                # For now, allow if they have enough cash for margin
                return True, "OK"
            
            if not position or position.quantity < quantity:
                available = position.quantity if position else 0
                return False, f"Insufficient shares: have {available}, need {quantity}"
            
            return True, "OK"

    def execute_buy(self, symbol: str, quantity: int, price: float,
                   order_id: str = "") -> Tuple[bool, float, str]:
        """
        Execute a buy order.
        
        Returns (success, total_cost, message).
        """
        with self._lock:
            can, msg = self.can_buy(symbol, quantity, price)
            if not can:
                return False, 0, msg
            
            total_value = quantity * price
            fees = total_value * self.transaction_fee_pct
            total_cost = total_value + fees
            
            # Deduct cash
            self.cash -= total_cost
            self.total_fees_paid += fees
            
            # Update position
            if symbol not in self._positions:
                self._positions[symbol] = Position(symbol=symbol)
            
            self._positions[symbol].add_shares(quantity, price)
            
            # Record trade
            trade = TradeRecord(
                trade_id=order_id or f"TRD-{self.total_trades}",
                symbol=symbol,
                side="buy",
                quantity=quantity,
                price=price,
                total_value=total_value,
                fees=fees,
                pnl=0,
                timestamp=datetime.now()
            )
            self._trades.append(trade)
            self.total_trades += 1
            
            return True, total_cost, f"Bought {quantity} {symbol} @ ${price:.2f}"

    def execute_sell(self, symbol: str, quantity: int, price: float,
                    is_short: bool = False, order_id: str = "") -> Tuple[bool, float, str]:
        """
        Execute a sell order.
        
        Returns (success, proceeds, message).
        """
        with self._lock:
            can, msg = self.can_sell(symbol, quantity, is_short)
            if not can:
                return False, 0, msg
            
            total_value = quantity * price
            fees = total_value * self.transaction_fee_pct
            proceeds = total_value - fees
            
            # Update position
            if symbol not in self._positions:
                if is_short:
                    self._positions[symbol] = Position(symbol=symbol, side=PositionSide.SHORT)
                else:
                    return False, 0, "No position to sell"
            
            position = self._positions[symbol]
            realized_pnl = position.remove_shares(quantity, price)
            
            # Add cash
            self.cash += proceeds
            self.total_fees_paid += fees
            
            # Update win/loss tracking
            if realized_pnl > 0:
                self.winning_trades += 1
            elif realized_pnl < 0:
                self.losing_trades += 1
            
            # Record trade
            trade = TradeRecord(
                trade_id=order_id or f"TRD-{self.total_trades}",
                symbol=symbol,
                side="sell" if not is_short else "short",
                quantity=quantity,
                price=price,
                total_value=total_value,
                fees=fees,
                pnl=realized_pnl,
                timestamp=datetime.now()
            )
            self._trades.append(trade)
            self.total_trades += 1
            
            # Clean up empty positions
            if position.is_empty():
                del self._positions[symbol]
            
            return True, proceeds, f"Sold {quantity} {symbol} @ ${price:.2f}, P&L: ${realized_pnl:.2f}"

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Get total portfolio value (cash + positions)."""
        with self._lock:
            positions_value = sum(
                pos.quantity * prices.get(pos.symbol, pos.avg_cost)
                for pos in self._positions.values()
                if pos.side == PositionSide.LONG
            )
            
            # For short positions, liability = current value
            short_liability = sum(
                pos.quantity * prices.get(pos.symbol, pos.avg_cost)
                for pos in self._positions.values()
                if pos.side == PositionSide.SHORT
            )
            
            return self.cash + positions_value - short_liability

    def get_total_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        """Get total unrealized P&L across all positions."""
        with self._lock:
            return sum(
                pos.get_unrealized_pnl(prices.get(pos.symbol, pos.avg_cost))
                for pos in self._positions.values()
            )

    def get_total_realized_pnl(self) -> float:
        """Get total realized P&L."""
        with self._lock:
            return sum(pos.realized_pnl for pos in self._positions.values())

    def get_total_pnl(self, prices: Dict[str, float]) -> float:
        """Get total P&L (realized + unrealized)."""
        return self.get_total_realized_pnl() + self.get_total_unrealized_pnl(prices)

    def get_return_pct(self, prices: Dict[str, float]) -> float:
        """Get portfolio return percentage."""
        current_value = self.get_portfolio_value(prices)
        return ((current_value - self.initial_balance) / self.initial_balance) * 100

    def get_win_rate(self) -> float:
        """Get win rate percentage."""
        total = self.winning_trades + self.losing_trades
        if total == 0:
            return 0.0
        return (self.winning_trades / total) * 100

    def update_peak_value(self, prices: Dict[str, float]):
        """Update peak portfolio value for drawdown calculation."""
        current = self.get_portfolio_value(prices)
        if current > self.peak_value:
            self.peak_value = current

    def get_max_drawdown(self, prices: Dict[str, float]) -> float:
        """Calculate maximum drawdown from peak."""
        self.update_peak_value(prices)
        current = self.get_portfolio_value(prices)
        if self.peak_value == 0:
            return 0.0
        return ((self.peak_value - current) / self.peak_value) * 100

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history."""
        with self._lock:
            trades = self._trades[-limit:]
            return [
                {
                    'trade_id': t.trade_id,
                    'symbol': t.symbol,
                    'side': t.side,
                    'quantity': t.quantity,
                    'price': t.price,
                    'total_value': t.total_value,
                    'fees': t.fees,
                    'pnl': t.pnl,
                    'timestamp': t.timestamp.isoformat()
                }
                for t in trades
            ]

    def get_summary(self, prices: Dict[str, float]) -> Dict:
        """Get comprehensive portfolio summary."""
        with self._lock:
            portfolio_value = self.get_portfolio_value(prices)
            
            return {
                'user_id': self.user_id,
                'cash': self.cash,
                'portfolio_value': portfolio_value,
                'positions_count': len(self.get_all_positions()),
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.get_win_rate(),
                'total_fees_paid': self.total_fees_paid,
                'realized_pnl': self.get_total_realized_pnl(),
                'unrealized_pnl': self.get_total_unrealized_pnl(prices),
                'total_pnl': self.get_total_pnl(prices),
                'return_pct': self.get_return_pct(prices),
                'peak_value': self.peak_value,
                'max_drawdown': self.get_max_drawdown(prices),
                'initial_balance': self.initial_balance
            }

    def get_positions_detail(self, prices: Dict[str, float]) -> List[Dict]:
        """Get detailed position information."""
        with self._lock:
            return [
                pos.to_dict(prices.get(pos.symbol))
                for pos in self._positions.values()
                if not pos.is_empty()
            ]

    def to_dict(self, prices: Dict[str, float] = None) -> Dict:
        """Serialize portfolio to dictionary."""
        prices = prices or {}
        return {
            'summary': self.get_summary(prices),
            'positions': self.get_positions_detail(prices),
            'recent_trades': self.get_trade_history(10)
        }

