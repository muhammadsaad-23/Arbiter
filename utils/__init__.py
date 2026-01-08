"""
Utility modules for the Stock Market Simulator.
"""

from .logger import AuditLogger, get_logger
from .indicators import TechnicalIndicators

# Optional import - only available if yfinance is installed
try:
    from .data_fetcher import HistoricalDataFetcher
    __all__ = ['AuditLogger', 'get_logger', 'TechnicalIndicators', 'HistoricalDataFetcher']
except ImportError:
    __all__ = ['AuditLogger', 'get_logger', 'TechnicalIndicators']

