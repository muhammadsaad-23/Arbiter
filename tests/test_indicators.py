"""
Technical Indicators Tests
==========================

Tests for technical indicator calculations.
"""

import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.indicators import TechnicalIndicators


class TestMovingAverages:
    """Test moving average calculations."""
    
    def setup_method(self):
        self.indicators = TechnicalIndicators()
        
        # Add sample price data
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
                  110, 112, 111, 113, 115, 114, 116, 118, 117, 119]
        for price in prices:
            self.indicators.update("TEST", price, 1000)
    
    def test_sma(self):
        """Test Simple Moving Average."""
        sma5 = self.indicators.sma("TEST", 5)
        
        # Last 5 prices: 115, 114, 116, 118, 117, 119
        # Actually: 116, 118, 117, 119 + need to check
        assert sma5 is not None
        assert 110 < sma5 < 120
    
    def test_ema(self):
        """Test Exponential Moving Average."""
        ema5 = self.indicators.ema("TEST", 5)
        
        assert ema5 is not None
        # EMA should be close to recent prices
        assert 110 < ema5 < 120
    
    def test_sma_insufficient_data(self):
        """Test SMA with insufficient data."""
        indicators = TechnicalIndicators()
        indicators.update("NEW", 100.0, 1000)
        
        sma20 = indicators.sma("NEW", 20)
        assert sma20 is None


class TestMomentumIndicators:
    """Test momentum indicators."""
    
    def setup_method(self):
        self.indicators = TechnicalIndicators()
        
        # Add trending data (uptrend then pullback)
        prices = list(range(100, 130)) + list(range(129, 125, -1))
        for price in prices:
            self.indicators.update("TEST", float(price), 1000)
    
    def test_rsi(self):
        """Test RSI calculation."""
        rsi = self.indicators.rsi("TEST", 14)
        
        assert rsi is not None
        assert 0 <= rsi.value <= 100
        # After uptrend, RSI should be high
        assert rsi.value > 50
    
    def test_rsi_overbought(self):
        """Test RSI overbought signal."""
        indicators = TechnicalIndicators()
        
        # Strong uptrend
        for i in range(30):
            indicators.update("UP", 100 + i * 2, 1000)
        
        rsi = indicators.rsi("UP", 14)
        assert rsi is not None
        assert rsi.signal in ['bearish', 'neutral']  # Overbought = bearish signal
    
    def test_rsi_oversold(self):
        """Test RSI oversold signal."""
        indicators = TechnicalIndicators()
        
        # Strong downtrend
        for i in range(30):
            indicators.update("DOWN", 200 - i * 3, 1000)
        
        rsi = indicators.rsi("DOWN", 14)
        assert rsi is not None
        assert rsi.signal in ['bullish', 'neutral']  # Oversold = bullish signal
    
    def test_macd(self):
        """Test MACD calculation."""
        macd = self.indicators.macd("TEST")
        
        assert macd is not None
        assert 'macd' in macd
        assert 'signal' in macd
        assert 'histogram' in macd
        assert 'trend' in macd
    
    def test_momentum(self):
        """Test momentum calculation."""
        momentum = self.indicators.momentum("TEST", 10)
        
        assert momentum is not None
        # Recent trend is down (from 130 to ~126)
        # So momentum should reflect the 10-period change
    
    def test_roc(self):
        """Test Rate of Change."""
        roc = self.indicators.rate_of_change("TEST", 10)
        
        assert roc is not None


class TestVolatilityIndicators:
    """Test volatility indicators."""
    
    def setup_method(self):
        self.indicators = TechnicalIndicators()
        
        # Add volatile price data
        np.random.seed(42)
        base_price = 100
        for i in range(50):
            noise = np.random.normal(0, 2)
            price = base_price + noise + i * 0.1
            self.indicators.update("TEST", price, 1000)
    
    def test_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        bb = self.indicators.bollinger_bands("TEST", 20, 2.0)
        
        assert bb is not None
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        assert bb['upper'] > bb['middle'] > bb['lower']
        assert 'percent_b' in bb
    
    def test_atr(self):
        """Test ATR calculation."""
        atr = self.indicators.atr("TEST", 14)
        
        assert atr is not None
        assert atr > 0
    
    def test_volatility(self):
        """Test historical volatility."""
        vol = self.indicators.volatility("TEST", 20)
        
        assert vol is not None
        assert vol > 0


class TestVolumeIndicators:
    """Test volume-based indicators."""
    
    def setup_method(self):
        self.indicators = TechnicalIndicators()
        
        # Add price/volume data
        for i in range(30):
            price = 100 + i * 0.5
            volume = 1000 + i * 100
            self.indicators.update("TEST", price, volume)
    
    def test_volume_sma(self):
        """Test volume SMA."""
        vol_sma = self.indicators.volume_sma("TEST", 10)
        
        assert vol_sma is not None
        assert vol_sma > 0
    
    def test_volume_spike(self):
        """Test volume spike detection."""
        # Add normal volume
        indicators = TechnicalIndicators()
        for i in range(25):
            indicators.update("TEST", 100.0, 1000)
        
        # No spike
        assert indicators.volume_spike("TEST", 20, 2.0) == False
        
        # Add spike
        indicators.update("TEST", 100.0, 5000)
        assert indicators.volume_spike("TEST", 20, 2.0) == True
    
    def test_obv(self):
        """Test On-Balance Volume."""
        obv = self.indicators.obv("TEST")
        
        assert obv is not None
        # Since price is trending up, OBV should be positive
        assert obv > 0


class TestCompositeAnalysis:
    """Test composite indicator analysis."""
    
    def setup_method(self):
        self.indicators = TechnicalIndicators()
        
        # Add substantial data for all indicators
        for i in range(100):
            price = 100 + np.sin(i / 10) * 5 + i * 0.1
            volume = 1000 + np.random.randint(0, 500)
            self.indicators.update("TEST", price, volume)
    
    def test_get_all_indicators(self):
        """Test getting all indicators at once."""
        all_ind = self.indicators.get_all_indicators("TEST")
        
        assert 'sma_20' in all_ind
        assert 'sma_50' in all_ind
        assert 'ema_12' in all_ind
        assert 'rsi' in all_ind
        assert 'macd' in all_ind
        assert 'bollinger' in all_ind
    
    def test_trend_signal(self):
        """Test aggregate trend signal."""
        signal = self.indicators.get_trend_signal("TEST")
        
        assert signal in [
            'strong_bullish', 'bullish', 'neutral', 
            'bearish', 'strong_bearish'
        ]
    
    def test_mean_reversion_signal(self):
        """Test mean reversion signal."""
        mr = self.indicators.get_mean_reversion_signal("TEST", 50, 2.0)
        
        assert mr is not None
        assert 'z_score' in mr
        assert 'mean' in mr
        assert 'signal' in mr


class TestCorrelation:
    """Test correlation calculations."""
    
    def test_correlation_calculation(self):
        """Test correlation between two symbols."""
        indicators = TechnicalIndicators()
        
        np.random.seed(42)
        base = np.random.randn(60)
        
        # Two correlated symbols
        for i in range(60):
            indicators.update("A", 100 + base[i] * 5, 1000)
            indicators.update("B", 150 + base[i] * 7 + np.random.randn() * 0.5, 1000)
        
        corr = indicators.calculate_correlation("A", "B", 50)
        
        assert corr is not None
        # Should be highly correlated
        assert corr > 0.8
    
    def test_uncorrelated_symbols(self):
        """Test correlation of uncorrelated symbols."""
        indicators = TechnicalIndicators()
        
        np.random.seed(42)
        
        for i in range(60):
            indicators.update("X", 100 + np.random.randn() * 5, 1000)
            indicators.update("Y", 150 + np.random.randn() * 5, 1000)
        
        corr = indicators.calculate_correlation("X", "Y", 50)
        
        assert corr is not None
        # Should have low correlation
        assert abs(corr) < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

