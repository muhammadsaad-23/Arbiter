"""
Order Book Tests
================

Tests for order matching, price-time priority, and order management.
"""

import pytest
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.orderbook import OrderBook, Order, OrderType, OrderSide, OrderStatus


class TestOrderCreation:
    """Test order creation and validation."""
    
    def test_create_market_order(self):
        """Test creating a market order."""
        order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        assert order.order_id == "ORD-001"
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 100
        assert order.filled_quantity == 0
        assert order.remaining_quantity == 100
        assert order.status == OrderStatus.PENDING

    def test_create_limit_order(self):
        """Test creating a limit order."""
        order = Order(
            order_id="ORD-002",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.00
        )
        
        assert order.price == 150.00
        assert order.order_type == OrderType.LIMIT

    def test_order_fill(self):
        """Test order fill recording."""
        order = Order(
            order_id="ORD-003",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        # Partial fill
        order.add_fill(150.00, 40)
        assert order.filled_quantity == 40
        assert order.remaining_quantity == 60
        assert order.avg_fill_price == 150.00
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Complete fill
        order.add_fill(151.00, 60)
        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert order.status == OrderStatus.FILLED
        # Average: (150*40 + 151*60) / 100 = 150.6
        assert abs(order.avg_fill_price - 150.6) < 0.01

    def test_order_cancel(self):
        """Test order cancellation."""
        order = Order(
            order_id="ORD-004",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        order.status = OrderStatus.OPEN
        
        assert order.cancel() == True
        assert order.status == OrderStatus.CANCELLED
        
        # Can't cancel again
        assert order.cancel() == False


class TestOrderBook:
    """Test order book matching engine."""
    
    def setup_method(self):
        """Set up test order book."""
        self.book = OrderBook("AAPL")
    
    def test_submit_limit_order(self):
        """Test submitting limit orders."""
        order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        
        success, msg = self.book.submit_order(order)
        assert success == True
        assert order.status == OrderStatus.OPEN
        assert self.book.best_bid == 150.00
    
    def test_limit_order_matching(self):
        """Test limit order matching."""
        # Place buy order
        buy_order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        self.book.submit_order(buy_order)
        
        # Place matching sell order
        sell_order = Order(
            order_id="ORD-002",
            user_id="USER-002",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        self.book.submit_order(sell_order)
        
        # Both should be filled
        assert buy_order.status == OrderStatus.FILLED
        assert sell_order.status == OrderStatus.FILLED
        assert buy_order.avg_fill_price == 150.00
        assert sell_order.avg_fill_price == 150.00
    
    def test_partial_fill(self):
        """Test partial order fills."""
        # Place buy for 100 shares
        buy_order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        self.book.submit_order(buy_order)
        
        # Sell only 40 shares
        sell_order = Order(
            order_id="ORD-002",
            user_id="USER-002",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=40,
            price=150.00
        )
        self.book.submit_order(sell_order)
        
        # Buy should be partially filled
        assert buy_order.status == OrderStatus.PARTIALLY_FILLED
        assert buy_order.filled_quantity == 40
        assert buy_order.remaining_quantity == 60
        
        # Sell should be fully filled
        assert sell_order.status == OrderStatus.FILLED
    
    def test_price_time_priority(self):
        """Test price-time priority matching."""
        # Place two buy orders at same price
        buy1 = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.00
        )
        self.book.submit_order(buy1)
        
        buy2 = Order(
            order_id="ORD-002",
            user_id="USER-002",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.00
        )
        self.book.submit_order(buy2)
        
        # Sell 50 - should match first order (time priority)
        sell = Order(
            order_id="ORD-003",
            user_id="USER-003",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.00
        )
        self.book.submit_order(sell)
        
        # First order should be filled, second should still be open
        assert buy1.status == OrderStatus.FILLED
        assert buy2.status == OrderStatus.OPEN
    
    def test_market_order_execution(self):
        """Test market order execution."""
        # Add liquidity
        sell = Order(
            order_id="ORD-001",
            user_id="MM",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        self.book.submit_order(sell)
        
        # Market buy
        buy = Order(
            order_id="ORD-002",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=50
        )
        success, msg = self.book.submit_order(buy)
        
        assert success == True
        assert buy.status == OrderStatus.FILLED
        assert buy.filled_quantity == 50
        assert buy.avg_fill_price == 150.00
    
    def test_cancel_order(self):
        """Test order cancellation."""
        order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        )
        self.book.submit_order(order)
        
        # Cancel
        success, msg = self.book.cancel_order("ORD-001")
        assert success == True
        assert order.status == OrderStatus.CANCELLED
        
        # Best bid should now be None
        assert self.book.best_bid is None
    
    def test_order_book_depth(self):
        """Test order book depth calculation."""
        # Add multiple levels
        for i, price in enumerate([150.00, 149.00, 148.00]):
            order = Order(
                order_id=f"BUY-{i}",
                user_id="USER-001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=price
            )
            self.book.submit_order(order)
        
        for i, price in enumerate([151.00, 152.00, 153.00]):
            order = Order(
                order_id=f"SELL-{i}",
                user_id="USER-002",
                symbol="AAPL",
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=price
            )
            self.book.submit_order(order)
        
        depth = self.book.get_book_depth(3)
        
        assert len(depth['bids']) == 3
        assert len(depth['asks']) == 3
        assert depth['bids'][0]['price'] == 150.00  # Best bid
        assert depth['asks'][0]['price'] == 151.00  # Best ask
        assert depth['spread'] == 1.00
    
    def test_stop_order_triggering(self):
        """Test stop order triggering."""
        # Create stop loss
        stop = Order(
            order_id="STOP-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            quantity=100,
            stop_price=145.00
        )
        self.book.submit_order(stop)
        
        # Add liquidity for when stop triggers
        bid = Order(
            order_id="BID-001",
            user_id="MM",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=144.00
        )
        self.book.submit_order(bid)
        
        # Trigger stop
        self.book.check_stop_orders(144.50)
        
        # Stop should have executed
        assert stop.status == OrderStatus.FILLED
    
    def test_reject_invalid_order(self):
        """Test rejection of invalid orders."""
        # Zero quantity
        order = Order(
            order_id="ORD-001",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0
        )
        success, msg = self.book.submit_order(order)
        assert success == False
        assert order.status == OrderStatus.REJECTED
        
        # Limit order without price
        order2 = Order(
            order_id="ORD-002",
            user_id="USER-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=None
        )
        success, msg = self.book.submit_order(order2)
        assert success == False


class TestOrderBookStats:
    """Test order book statistics."""
    
    def setup_method(self):
        self.book = OrderBook("AAPL")
    
    def test_spread_calculation(self):
        """Test bid-ask spread calculation."""
        # No orders - no spread
        assert self.book.spread is None
        
        # Add bid and ask
        self.book.submit_order(Order(
            order_id="BID",
            user_id="USER",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=149.50
        ))
        
        self.book.submit_order(Order(
            order_id="ASK",
            user_id="USER",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.50
        ))
        
        assert self.book.spread == 1.00
        assert self.book.mid_price == 150.00
    
    def test_stats(self):
        """Test order book statistics."""
        # Place orders and execute trade
        self.book.submit_order(Order(
            order_id="BID",
            user_id="USER1",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        ))
        
        self.book.submit_order(Order(
            order_id="ASK",
            user_id="USER2",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.00
        ))
        
        stats = self.book.get_stats()
        
        assert stats['total_trades'] == 1
        assert stats['total_volume'] == 15000.00  # 100 * 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

