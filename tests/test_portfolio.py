"""
Portfolio Tests
===============

Tests for portfolio management, positions, and P&L calculations.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.portfolio import Portfolio, Position, PositionSide


class TestPosition:
    """Test position management."""
    
    def test_create_long_position(self):
        """Test creating a long position."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100
        assert pos.avg_cost == 150.00
        assert pos.side == PositionSide.LONG
        assert pos.cost_basis == 15000.00
    
    def test_add_to_long_position(self):
        """Test adding to an existing long position."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        pos.add_shares(100, 160.00)
        
        assert pos.quantity == 200
        # Average cost: (100*150 + 100*160) / 200 = 155
        assert pos.avg_cost == 155.00
    
    def test_sell_from_long_position(self):
        """Test selling from long position."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        
        # Sell at profit
        realized = pos.remove_shares(50, 160.00)
        
        assert pos.quantity == 50
        # P&L: 50 * (160 - 150) = 500
        assert realized == 500.00
        assert pos.realized_pnl == 500.00
    
    def test_close_long_position(self):
        """Test closing entire position."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        
        realized = pos.remove_shares(100, 145.00)
        
        assert pos.quantity == 0
        # P&L: 100 * (145 - 150) = -500
        assert realized == -500.00
        assert pos.is_empty() == True
    
    def test_unrealized_pnl(self):
        """Test unrealized P&L calculation."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        
        # Current price 160
        unrealized = pos.get_unrealized_pnl(160.00)
        assert unrealized == 1000.00  # 100 * (160 - 150)
        
        # Current price 140
        unrealized = pos.get_unrealized_pnl(140.00)
        assert unrealized == -1000.00  # 100 * (140 - 150)
    
    def test_total_pnl(self):
        """Test total P&L (realized + unrealized)."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 150.00)
        
        # Sell half at profit
        pos.remove_shares(50, 160.00)  # +500 realized
        
        # Total P&L with current price 155
        total = pos.get_total_pnl(155.00)
        # Realized: 500, Unrealized: 50 * (155-150) = 250
        assert total == 750.00
    
    def test_return_percentage(self):
        """Test return percentage calculation."""
        pos = Position(symbol="AAPL")
        pos.add_shares(100, 100.00)  # $10,000 cost basis
        
        # 10% gain
        pct = pos.get_return_pct(110.00)
        assert pct == pytest.approx(10.0, rel=0.01)
        
        # 20% loss
        pct = pos.get_return_pct(80.00)
        assert pct == pytest.approx(-20.0, rel=0.01)


class TestPortfolio:
    """Test portfolio management."""
    
    def test_create_portfolio(self):
        """Test portfolio creation."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00
        )
        
        assert portfolio.user_id == "USER-001"
        assert portfolio.cash == 100000.00
        assert portfolio.initial_balance == 100000.00
        assert portfolio.total_trades == 0
    
    def test_execute_buy(self):
        """Test buying shares."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0.001
        )
        
        success, cost, msg = portfolio.execute_buy("AAPL", 100, 150.00)
        
        assert success == True
        # Cost: 100 * 150 * 1.001 = 15015
        assert cost == pytest.approx(15015.00, rel=0.01)
        assert portfolio.cash == pytest.approx(84985.00, rel=0.01)
        
        position = portfolio.get_position("AAPL")
        assert position is not None
        assert position.quantity == 100
    
    def test_execute_sell(self):
        """Test selling shares."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0.001
        )
        
        # Buy first
        portfolio.execute_buy("AAPL", 100, 150.00)
        
        # Sell at higher price
        success, proceeds, msg = portfolio.execute_sell("AAPL", 50, 160.00)
        
        assert success == True
        # Proceeds: 50 * 160 * 0.999 = 7992
        assert proceeds == pytest.approx(7992.00, rel=0.01)
        
        position = portfolio.get_position("AAPL")
        assert position.quantity == 50
    
    def test_insufficient_funds(self):
        """Test buying with insufficient funds."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=1000.00
        )
        
        success, cost, msg = portfolio.execute_buy("AAPL", 100, 150.00)
        
        assert success == False
        assert "Insufficient funds" in msg
    
    def test_insufficient_shares(self):
        """Test selling more shares than owned."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00
        )
        
        portfolio.execute_buy("AAPL", 50, 150.00)
        success, proceeds, msg = portfolio.execute_sell("AAPL", 100, 160.00)
        
        assert success == False
        assert "Insufficient shares" in msg
    
    def test_portfolio_value(self):
        """Test total portfolio value calculation."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0.001
        )
        
        portfolio.execute_buy("AAPL", 100, 150.00)
        portfolio.execute_buy("GOOGL", 50, 140.00)
        
        # Current prices
        prices = {"AAPL": 160.00, "GOOGL": 145.00}
        
        value = portfolio.get_portfolio_value(prices)
        
        # Cash remaining + positions value
        # Cash: 100000 - 15015 - 7007 = 77978
        # AAPL: 100 * 160 = 16000
        # GOOGL: 50 * 145 = 7250
        expected = 77978 + 16000 + 7250
        assert value == pytest.approx(expected, rel=0.01)
    
    def test_win_rate(self):
        """Test win rate calculation."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0
        )
        
        # Win: buy at 100, sell at 110
        portfolio.execute_buy("AAPL", 10, 100.00)
        portfolio.execute_sell("AAPL", 10, 110.00)
        
        # Loss: buy at 100, sell at 90
        portfolio.execute_buy("GOOGL", 10, 100.00)
        portfolio.execute_sell("GOOGL", 10, 90.00)
        
        # Win: buy at 100, sell at 105
        portfolio.execute_buy("MSFT", 10, 100.00)
        portfolio.execute_sell("MSFT", 10, 105.00)
        
        assert portfolio.winning_trades == 2
        assert portfolio.losing_trades == 1
        assert portfolio.get_win_rate() == pytest.approx(66.67, rel=0.1)
    
    def test_trade_history(self):
        """Test trade history tracking."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00
        )
        
        portfolio.execute_buy("AAPL", 100, 150.00)
        portfolio.execute_sell("AAPL", 50, 160.00)
        
        history = portfolio.get_trade_history()
        
        assert len(history) == 2
        assert history[0]['symbol'] == 'AAPL'
        assert history[0]['side'] == 'buy'
        assert history[1]['side'] == 'sell'
    
    def test_return_percentage(self):
        """Test portfolio return calculation."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0
        )
        
        portfolio.execute_buy("AAPL", 100, 100.00)  # $10,000 spent
        
        # 10% gain on position
        prices = {"AAPL": 110.00}
        
        # Portfolio value: 90,000 cash + 11,000 position = 101,000
        return_pct = portfolio.get_return_pct(prices)
        assert return_pct == pytest.approx(1.0, rel=0.1)  # 1% return
    
    def test_max_drawdown(self):
        """Test max drawdown tracking."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0
        )
        
        portfolio.execute_buy("AAPL", 100, 100.00)
        
        # Peak at 110
        portfolio.update_peak_value({"AAPL": 110.00})
        
        # Drawdown to 95
        drawdown = portfolio.get_max_drawdown({"AAPL": 95.00})
        
        # Peak: 90,000 + 11,000 = 101,000
        # Current: 90,000 + 9,500 = 99,500
        # Drawdown: (101,000 - 99,500) / 101,000 = 1.49%
        assert drawdown == pytest.approx(1.49, rel=0.1)


class TestPortfolioSummary:
    """Test portfolio summary generation."""
    
    def test_summary_generation(self):
        """Test generating portfolio summary."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0.001
        )
        
        portfolio.execute_buy("AAPL", 100, 150.00)
        portfolio.execute_buy("GOOGL", 50, 140.00)
        
        prices = {"AAPL": 160.00, "GOOGL": 145.00}
        summary = portfolio.get_summary(prices)
        
        assert 'user_id' in summary
        assert 'cash' in summary
        assert 'portfolio_value' in summary
        assert 'positions_count' in summary
        assert summary['positions_count'] == 2
    
    def test_positions_detail(self):
        """Test detailed position information."""
        portfolio = Portfolio(
            user_id="USER-001",
            initial_balance=100000.00,
            transaction_fee_pct=0
        )
        
        portfolio.execute_buy("AAPL", 100, 150.00)
        
        prices = {"AAPL": 160.00}
        positions = portfolio.get_positions_detail(prices)
        
        assert len(positions) == 1
        pos = positions[0]
        assert pos['symbol'] == 'AAPL'
        assert pos['quantity'] == 100
        assert pos['current_price'] == 160.00
        assert pos['unrealized_pnl'] == 1000.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

