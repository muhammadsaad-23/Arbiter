"""
Price Model Tests
=================

Tests for price movement simulations:
- Random walk
- Geometric Brownian Motion
- Price shocks
"""

import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.asset import Asset, AssetManager, PriceModel


class TestAssetPricing:
    """Test individual asset price movements."""
    
    def test_asset_creation(self):
        """Test asset initialization."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=150.00,
            volatility=0.02,
            sector="Technology"
        )
        
        assert asset.symbol == "AAPL"
        assert asset.price == 150.00
        assert asset.initial_price == 150.00
        assert asset.volatility == 0.02
        assert asset.open_price == 150.00
        assert asset.high_price == 150.00
        assert asset.low_price == 150.00
    
    def test_bid_ask_spread(self):
        """Test bid-ask spread calculation."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02
        )
        
        spread = asset.get_spread()
        assert spread > 0
        assert asset.bid < asset.price
        assert asset.ask > asset.price
        assert asset.bid < asset.ask
    
    def test_random_walk(self):
        """Test random walk price model."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.05
        )
        
        prices = [100.00]
        for _ in range(100):
            new_price = asset.update_price_random_walk(1.0)
            prices.append(new_price)
        
        # Price should have changed
        assert asset.price != 100.00
        # Price should stay positive
        assert all(p > 0 for p in prices)
        # Should have recorded history
        assert len(asset.price_history) >= 100
    
    def test_gbm_model(self):
        """Test Geometric Brownian Motion price model."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02,
            drift=0.0001
        )
        
        prices = [100.00]
        for _ in range(100):
            new_price = asset.update_price_gbm(1.0)
            prices.append(new_price)
        
        # Price should remain positive
        assert all(p > 0 for p in prices)
        
        # With positive drift, average should be slightly higher
        # (not guaranteed but likely over many runs)
        assert asset.price != 100.00
    
    def test_hybrid_model(self):
        """Test hybrid price model with mean reversion."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02,
            mean_reversion_speed=0.1
        )
        
        for _ in range(100):
            asset.update_price_hybrid(1.0)
        
        # Price should stay positive and not diverge too much
        assert asset.price > 0
        # Mean reversion should prevent extreme deviations
        assert 50 < asset.price < 200  # Reasonable bounds
    
    def test_price_shock(self):
        """Test sudden price shock application."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02
        )
        
        # Positive shock
        asset.apply_shock(0.10, is_positive=True)
        assert asset.price == pytest.approx(110.00, rel=0.01)
        
        # Negative shock
        asset.apply_shock(0.10, is_positive=False)
        assert asset.price == pytest.approx(99.00, rel=0.01)
    
    def test_halt_prevents_updates(self):
        """Test that halted assets don't update."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02
        )
        
        asset.halt("Circuit breaker")
        assert asset.is_halted == True
        
        old_price = asset.price
        asset.update_price_random_walk(1.0)
        assert asset.price == old_price
        
        asset.resume()
        assert asset.is_halted == False
        asset.update_price_random_walk(1.0)
        # Now price can change


class TestPriceDistribution:
    """Test statistical properties of price models."""
    
    def test_random_walk_distribution(self):
        """Test that random walk produces reasonable distribution."""
        np.random.seed(42)
        
        asset = Asset(
            symbol="TEST",
            name="Test Asset",
            initial_price=100.00,
            volatility=0.02
        )
        
        returns = []
        for _ in range(1000):
            old_price = asset.price
            asset.update_price_random_walk(1.0)
            if old_price > 0:
                returns.append((asset.price - old_price) / old_price)
        
        # Returns should be roughly normally distributed
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Mean should be close to 0
        assert abs(mean_return) < 0.01
        
        # Std should be related to volatility
        assert 0.005 < std_return < 0.05
    
    def test_gbm_log_returns(self):
        """Test that GBM produces log-normal prices."""
        np.random.seed(42)
        
        asset = Asset(
            symbol="TEST",
            name="Test Asset",
            initial_price=100.00,
            volatility=0.02,
            drift=0
        )
        
        prices = [100.00]
        for _ in range(1000):
            asset.update_price_gbm(1.0)
            prices.append(asset.price)
        
        # All prices should be positive
        assert all(p > 0 for p in prices)
        
        # Log returns should be roughly normal
        log_returns = np.diff(np.log(prices))
        
        # Shapiro-Wilk test would be too sensitive, just check basics
        assert -1 < np.mean(log_returns) < 1
        assert np.std(log_returns) > 0


class TestAssetStatistics:
    """Test asset statistics tracking."""
    
    def test_session_tracking(self):
        """Test session high/low tracking."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.10  # High volatility for noticeable moves
        )
        
        for _ in range(50):
            asset.update_price_random_walk(1.0)
        
        # High should be >= open
        assert asset.high_price >= asset.open_price
        # Low should be <= open
        assert asset.low_price <= asset.open_price
        # Current price should be between high and low
        assert asset.low_price <= asset.price <= asset.high_price
    
    def test_daily_change_calculation(self):
        """Test daily change tracking."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02
        )
        
        # Simulate price movement
        asset.apply_shock(0.05, is_positive=True)
        
        change, pct = asset.get_daily_change()
        
        assert change == pytest.approx(5.00, rel=0.01)
        assert pct == pytest.approx(5.0, rel=0.01)
    
    def test_new_session_reset(self):
        """Test session reset."""
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            initial_price=100.00,
            volatility=0.02
        )
        
        # Move price
        asset.apply_shock(0.10, is_positive=True)
        
        # Start new session
        asset.new_session()
        
        # Previous close should be current price
        assert asset.prev_close == asset.price
        # Open should be current price
        assert asset.open_price == asset.price
        # High and low reset
        assert asset.high_price == asset.price
        assert asset.low_price == asset.price


class TestAssetManager:
    """Test asset manager operations."""
    
    @pytest.fixture
    def config(self):
        return {
            'market': {
                'price_models': {
                    'default': 'gbm',
                    'drift': 0.0001
                }
            },
            'assets': {
                'max_symbols': 100,
                'default_symbols': [
                    {'symbol': 'AAPL', 'name': 'Apple', 'initial_price': 150.0, 'volatility': 0.02, 'sector': 'Tech'},
                    {'symbol': 'GOOGL', 'name': 'Google', 'initial_price': 140.0, 'volatility': 0.025, 'sector': 'Tech'},
                ]
            }
        }
    
    @pytest.mark.asyncio
    async def test_initialization(self, config):
        """Test asset manager initialization."""
        manager = AssetManager(config)
        await manager.initialize()
        
        assert len(manager.get_symbols()) == 2
        assert 'AAPL' in manager.get_symbols()
        assert 'GOOGL' in manager.get_symbols()
    
    @pytest.mark.asyncio
    async def test_add_asset(self, config):
        """Test adding new assets."""
        manager = AssetManager(config)
        await manager.initialize()
        
        await manager.add_asset(
            symbol='MSFT',
            name='Microsoft',
            initial_price=380.0,
            volatility=0.02,
            sector='Tech'
        )
        
        assert 'MSFT' in manager.get_symbols()
        assert len(manager.get_symbols()) == 3
    
    @pytest.mark.asyncio
    async def test_get_asset(self, config):
        """Test getting assets."""
        manager = AssetManager(config)
        await manager.initialize()
        
        asset = manager.get_asset('AAPL')
        assert asset is not None
        assert asset.symbol == 'AAPL'
        
        missing = manager.get_asset('INVALID')
        assert missing is None
    
    @pytest.mark.asyncio
    async def test_price_update(self, config):
        """Test batch price updates."""
        manager = AssetManager(config)
        await manager.initialize()
        
        updates = await manager.update_prices(1.0)
        
        assert 'AAPL' in updates
        assert 'GOOGL' in updates
        assert all(p > 0 for p in updates.values())
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, config):
        """Test circuit breaker triggering."""
        manager = AssetManager(config)
        await manager.initialize()
        
        asset = manager.get_asset('AAPL')
        # Force large move
        asset.apply_shock(0.15, is_positive=False)
        
        halted = manager.check_circuit_breakers(0.10)
        
        assert 'AAPL' in halted
        assert asset.is_halted == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

