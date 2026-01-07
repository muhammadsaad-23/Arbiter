"""
Technical Indicators Library
=============================

Production-grade implementation of trading indicators:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Relative Strength Index (RSI)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume Analysis
- Custom indicators for bot strategies
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import deque


@dataclass
class IndicatorResult:
    """Container for indicator calculation results."""
    value: float
    signal: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # 0.0 to 1.0


class TechnicalIndicators:
    """
    Efficient technical indicator calculations with streaming support.
    
    Optimized for real-time calculation with incremental updates.
    """

    def __init__(self, max_history: int = 500):
        self._max_history = max_history
        self._price_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        self._ema_state: Dict[str, Dict[int, float]] = {}

    def update(self, symbol: str, price: float, volume: int = 0):
        """Update price history for a symbol."""
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=self._max_history)
            self._volume_history[symbol] = deque(maxlen=self._max_history)
            self._ema_state[symbol] = {}
        
        self._price_history[symbol].append(price)
        self._volume_history[symbol].append(volume)

    def get_prices(self, symbol: str, periods: Optional[int] = None) -> np.ndarray:
        """Get price history as numpy array."""
        if symbol not in self._price_history:
            return np.array([])
        
        prices = list(self._price_history[symbol])
        if periods:
            prices = prices[-periods:]
        return np.array(prices)

    def get_volumes(self, symbol: str, periods: Optional[int] = None) -> np.ndarray:
        """Get volume history as numpy array."""
        if symbol not in self._volume_history:
            return np.array([])
        
        volumes = list(self._volume_history[symbol])
        if periods:
            volumes = volumes[-periods:]
        return np.array(volumes)

    # ==================== MOVING AVERAGES ====================

    def sma(self, symbol: str, period: int) -> Optional[float]:
        """
        Simple Moving Average.
        
        SMA = (P1 + P2 + ... + Pn) / n
        """
        prices = self.get_prices(symbol, period)
        if len(prices) < period:
            return None
        return float(np.mean(prices[-period:]))

    def ema(self, symbol: str, period: int) -> Optional[float]:
        """
        Exponential Moving Average with incremental updates.
        
        EMA = Price(t) * k + EMA(y) * (1 - k)
        where k = 2 / (period + 1)
        """
        prices = self.get_prices(symbol)
        if len(prices) < period:
            return None

        k = 2.0 / (period + 1)
        
        # Check for cached EMA state
        if period in self._ema_state.get(symbol, {}):
            prev_ema = self._ema_state[symbol][period]
            current_ema = prices[-1] * k + prev_ema * (1 - k)
        else:
            # Calculate from scratch
            ema_values = [float(np.mean(prices[:period]))]
            for price in prices[period:]:
                ema_values.append(price * k + ema_values[-1] * (1 - k))
            current_ema = ema_values[-1]
        
        # Cache the state
        if symbol not in self._ema_state:
            self._ema_state[symbol] = {}
        self._ema_state[symbol][period] = current_ema
        
        return current_ema

    def weighted_ma(self, symbol: str, period: int) -> Optional[float]:
        """
        Weighted Moving Average - more weight to recent prices.
        """
        prices = self.get_prices(symbol, period)
        if len(prices) < period:
            return None
        
        weights = np.arange(1, period + 1)
        return float(np.average(prices[-period:], weights=weights))

    # ==================== MOMENTUM INDICATORS ====================

    def rsi(self, symbol: str, period: int = 14) -> Optional[IndicatorResult]:
        """
        Relative Strength Index.
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        
        Interpretation:
        - RSI > 70: Overbought (bearish signal)
        - RSI < 30: Oversold (bullish signal)
        """
        prices = self.get_prices(symbol)
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        deltas = np.diff(prices[-(period + 1):])
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        # Determine signal
        if rsi > 70:
            signal = 'bearish'
            strength = (rsi - 70) / 30
        elif rsi < 30:
            signal = 'bullish'
            strength = (30 - rsi) / 30
        else:
            signal = 'neutral'
            strength = abs(50 - rsi) / 20

        return IndicatorResult(value=rsi, signal=signal, strength=min(1.0, strength))

    def macd(self, symbol: str, fast: int = 12, slow: int = 26, 
             signal_period: int = 9) -> Optional[Dict[str, float]]:
        """
        Moving Average Convergence Divergence.
        
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) of MACD Line
        Histogram = MACD Line - Signal Line
        
        Signals:
        - MACD crosses above signal: Bullish
        - MACD crosses below signal: Bearish
        - Histogram direction: Momentum
        """
        prices = self.get_prices(symbol)
        if len(prices) < slow + signal_period:
            return None

        # Calculate EMAs manually for MACD
        k_fast = 2.0 / (fast + 1)
        k_slow = 2.0 / (slow + 1)
        k_signal = 2.0 / (signal_period + 1)

        # Fast EMA
        ema_fast = [float(np.mean(prices[:fast]))]
        for price in prices[fast:]:
            ema_fast.append(price * k_fast + ema_fast[-1] * (1 - k_fast))

        # Slow EMA
        ema_slow = [float(np.mean(prices[:slow]))]
        for price in prices[slow:]:
            ema_slow.append(price * k_slow + ema_slow[-1] * (1 - k_slow))

        # Align arrays and calculate MACD line
        offset = slow - fast
        macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]

        # Signal line (EMA of MACD)
        if len(macd_line) < signal_period:
            return None
        
        signal_line = [float(np.mean(macd_line[:signal_period]))]
        for val in macd_line[signal_period:]:
            signal_line.append(val * k_signal + signal_line[-1] * (1 - k_signal))

        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        histogram = current_macd - current_signal

        return {
            'macd': current_macd,
            'signal': current_signal,
            'histogram': histogram,
            'trend': 'bullish' if current_macd > current_signal else 'bearish'
        }

    def momentum(self, symbol: str, period: int = 10) -> Optional[float]:
        """
        Price Momentum - rate of price change.
        
        Momentum = Current Price - Price n periods ago
        """
        prices = self.get_prices(symbol)
        if len(prices) < period + 1:
            return None
        return float(prices[-1] - prices[-(period + 1)])

    def rate_of_change(self, symbol: str, period: int = 10) -> Optional[float]:
        """
        Rate of Change (ROC) - percentage change.
        
        ROC = ((Current Price - Price n periods ago) / Price n periods ago) * 100
        """
        prices = self.get_prices(symbol)
        if len(prices) < period + 1:
            return None
        
        old_price = prices[-(period + 1)]
        if old_price == 0:
            return None
        return float(((prices[-1] - old_price) / old_price) * 100)

    # ==================== VOLATILITY INDICATORS ====================

    def bollinger_bands(self, symbol: str, period: int = 20, 
                       std_dev: float = 2.0) -> Optional[Dict[str, float]]:
        """
        Bollinger Bands - volatility bands around SMA.
        
        Middle Band = SMA(20)
        Upper Band = SMA(20) + 2 * StdDev
        Lower Band = SMA(20) - 2 * StdDev
        
        Width indicates volatility.
        Price touching bands may signal reversal.
        """
        prices = self.get_prices(symbol, period)
        if len(prices) < period:
            return None

        middle = float(np.mean(prices))
        std = float(np.std(prices))
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        current_price = prices[-1]
        
        # Calculate %B (where price is relative to bands)
        if upper - lower > 0:
            percent_b = (current_price - lower) / (upper - lower)
        else:
            percent_b = 0.5
        
        # Band width as percentage
        bandwidth = ((upper - lower) / middle) * 100 if middle > 0 else 0

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'current': current_price,
            'percent_b': percent_b,
            'bandwidth': bandwidth,
            'signal': 'overbought' if percent_b > 1 else 'oversold' if percent_b < 0 else 'neutral'
        }

    def atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Average True Range - volatility measure.
        
        TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        ATR = EMA(TR, period)
        
        Note: Using close prices only, so TR = |Close - Close_prev|
        """
        prices = self.get_prices(symbol)
        if len(prices) < period + 1:
            return None

        true_ranges = np.abs(np.diff(prices[-(period + 1):]))
        return float(np.mean(true_ranges))

    def volatility(self, symbol: str, period: int = 20) -> Optional[float]:
        """
        Historical Volatility - annualized standard deviation of returns.
        """
        prices = self.get_prices(symbol)
        if len(prices) < period + 1:
            return None

        returns = np.diff(np.log(prices[-(period + 1):]))
        return float(np.std(returns) * np.sqrt(252))  # Annualized

    # ==================== VOLUME INDICATORS ====================

    def volume_sma(self, symbol: str, period: int = 20) -> Optional[float]:
        """Simple Moving Average of volume."""
        volumes = self.get_volumes(symbol, period)
        if len(volumes) < period:
            return None
        return float(np.mean(volumes))

    def volume_spike(self, symbol: str, period: int = 20, 
                    threshold: float = 2.0) -> Optional[bool]:
        """
        Detect volume spikes above threshold * average.
        """
        volumes = self.get_volumes(symbol)
        if len(volumes) < period:
            return None

        avg_volume = np.mean(volumes[-period:-1]) if len(volumes) > period else np.mean(volumes[:-1])
        current_volume = volumes[-1]
        
        return current_volume > (avg_volume * threshold) if avg_volume > 0 else False

    def obv(self, symbol: str) -> Optional[float]:
        """
        On-Balance Volume - cumulative volume based on price direction.
        
        OBV increases when close > previous close
        OBV decreases when close < previous close
        """
        prices = self.get_prices(symbol)
        volumes = self.get_volumes(symbol)
        
        if len(prices) < 2 or len(volumes) < 2:
            return None

        obv = 0.0
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                obv += volumes[i]
            elif prices[i] < prices[i - 1]:
                obv -= volumes[i]
        
        return obv

    # ==================== COMPOSITE ANALYSIS ====================

    def get_all_indicators(self, symbol: str) -> Dict[str, any]:
        """
        Calculate all major indicators for comprehensive analysis.
        """
        return {
            'sma_20': self.sma(symbol, 20),
            'sma_50': self.sma(symbol, 50),
            'ema_12': self.ema(symbol, 12),
            'ema_26': self.ema(symbol, 26),
            'rsi': self.rsi(symbol),
            'macd': self.macd(symbol),
            'bollinger': self.bollinger_bands(symbol),
            'momentum': self.momentum(symbol),
            'roc': self.rate_of_change(symbol),
            'volatility': self.volatility(symbol),
            'volume_sma': self.volume_sma(symbol),
            'volume_spike': self.volume_spike(symbol)
        }

    def get_trend_signal(self, symbol: str) -> str:
        """
        Aggregate trend signal from multiple indicators.
        
        Returns: 'strong_bullish', 'bullish', 'neutral', 'bearish', 'strong_bearish'
        """
        bullish_count = 0
        bearish_count = 0
        
        # RSI
        rsi = self.rsi(symbol)
        if rsi:
            if rsi.signal == 'bullish':
                bullish_count += 1
            elif rsi.signal == 'bearish':
                bearish_count += 1
        
        # MACD
        macd = self.macd(symbol)
        if macd:
            if macd['trend'] == 'bullish':
                bullish_count += 1
            else:
                bearish_count += 1
        
        # SMA crossover
        sma_20 = self.sma(symbol, 20)
        sma_50 = self.sma(symbol, 50)
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                bullish_count += 1
            else:
                bearish_count += 1
        
        # Bollinger position
        bb = self.bollinger_bands(symbol)
        if bb:
            if bb['signal'] == 'oversold':
                bullish_count += 1
            elif bb['signal'] == 'overbought':
                bearish_count += 1
        
        # Momentum
        momentum = self.momentum(symbol)
        if momentum is not None:
            if momentum > 0:
                bullish_count += 1
            else:
                bearish_count += 1

        # Determine overall signal
        diff = bullish_count - bearish_count
        if diff >= 3:
            return 'strong_bullish'
        elif diff >= 1:
            return 'bullish'
        elif diff <= -3:
            return 'strong_bearish'
        elif diff <= -1:
            return 'bearish'
        return 'neutral'

    def calculate_correlation(self, symbol1: str, symbol2: str, 
                             period: int = 50) -> Optional[float]:
        """
        Calculate price correlation between two symbols.
        
        Used for arbitrage strategy.
        """
        prices1 = self.get_prices(symbol1, period)
        prices2 = self.get_prices(symbol2, period)
        
        if len(prices1) < period or len(prices2) < period:
            return None

        # Calculate returns
        returns1 = np.diff(prices1) / prices1[:-1]
        returns2 = np.diff(prices2) / prices2[:-1]

        # Pearson correlation
        correlation = np.corrcoef(returns1, returns2)[0, 1]
        return float(correlation) if not np.isnan(correlation) else None

    def get_mean_reversion_signal(self, symbol: str, 
                                  lookback: int = 50,
                                  std_threshold: float = 2.0) -> Optional[Dict]:
        """
        Mean reversion analysis for mean reversion bot.
        """
        prices = self.get_prices(symbol, lookback)
        if len(prices) < lookback:
            return None

        mean = np.mean(prices)
        std = np.std(prices)
        current = prices[-1]
        
        z_score = (current - mean) / std if std > 0 else 0
        
        return {
            'mean': float(mean),
            'std': float(std),
            'current': float(current),
            'z_score': float(z_score),
            'signal': 'buy' if z_score < -std_threshold else 'sell' if z_score > std_threshold else 'hold',
            'distance_pct': float(((current - mean) / mean) * 100) if mean > 0 else 0
        }

