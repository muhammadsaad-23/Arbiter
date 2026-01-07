"""
AI Trading Bots
===============

Automated trading strategies:
- Momentum trading
- Mean reversion
- Arbitrage
"""

from .momentum import MomentumBot
from .mean_reversion import MeanReversionBot
from .arbitrage import ArbitrageBot
from .base import TradingBot, BotManager

__all__ = [
    'TradingBot',
    'BotManager',
    'MomentumBot',
    'MeanReversionBot',
    'ArbitrageBot'
]

