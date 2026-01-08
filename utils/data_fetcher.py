"""
Historical Data Fetcher
=======================

Fetches real historical stock data from Yahoo Finance
for backtesting and replay simulation.
"""

import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class HistoricalBar:
    """Single bar of historical data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalDataFetcher:
    """
    Fetches real historical stock data from Yahoo Finance.
    
    Usage:
        fetcher = HistoricalDataFetcher()
        prices = fetcher.get_price_series("AAPL", period="1mo")
        bars = fetcher.get_bars("AAPL", period="1mo")
    """
    
    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}
        self._failed_symbols: set = set()
    
    def fetch(self, symbol: str, period: str = "1mo", 
              interval: str = "1h") -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol.
        
        Args:
            symbol: Stock ticker (e.g., "AAPL")
            period: How far back - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"
            interval: Data frequency - "1m", "2m", "5m", "15m", "30m", "60m", "90m", 
                      "1h", "1d", "5d", "1wk", "1mo", "3mo"
        
        Returns:
            DataFrame with Open, High, Low, Close, Volume columns
            None if fetch failed
        
        Note:
            - 1m data only available for last 7 days
            - 2m-90m data available for last 60 days
            - 1h data available for last 730 days
        """
        cache_key = f"{symbol}_{period}_{interval}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if symbol in self._failed_symbols:
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                print(f"Warning: No data returned for {symbol}")
                self._failed_symbols.add(symbol)
                return None
            
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            self._failed_symbols.add(symbol)
            return None
    
    def fetch_multiple(self, symbols: List[str], period: str = "1mo", 
                       interval: str = "1h") -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols."""
        results = {}
        for symbol in symbols:
            df = self.fetch(symbol, period, interval)
            if df is not None:
                results[symbol] = df
        return results
    
    def get_price_series(self, symbol: str, period: str = "1mo", 
                         interval: str = "1h") -> List[float]:
        """
        Get just the closing prices as a list.
        
        This is the main method for feeding prices into the simulation.
        """
        df = self.fetch(symbol, period, interval)
        if df is None or df.empty:
            return []
        return df['Close'].tolist()
    
    def get_volume_series(self, symbol: str, period: str = "1mo",
                          interval: str = "1h") -> List[int]:
        """Get just the volumes as a list."""
        df = self.fetch(symbol, period, interval)
        if df is None or df.empty:
            return []
        return df['Volume'].astype(int).tolist()
    
    def get_bars(self, symbol: str, period: str = "1mo",
                 interval: str = "1h") -> List[HistoricalBar]:
        """Get full OHLCV bars."""
        df = self.fetch(symbol, period, interval)
        if df is None or df.empty:
            return []
        
        bars = []
        for idx, row in df.iterrows():
            bar = HistoricalBar(
                timestamp=idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx,
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=int(row['Volume'])
            )
            bars.append(bar)
        return bars
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the most recent price for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            # Try to get from fast_info first (faster)
            if hasattr(ticker, 'fast_info') and 'lastPrice' in ticker.fast_info:
                return float(ticker.fast_info['lastPrice'])
            
            # Fall back to history
            df = ticker.history(period="1d", interval="1m")
            if not df.empty:
                return float(df['Close'].iloc[-1])
            return None
        except Exception as e:
            print(f"Error getting current price for {symbol}: {e}")
            return None
    
    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()
        self._failed_symbols.clear()


def download_and_save_csv(symbols: List[str], output_dir: str = "data",
                          period: str = "1y", interval: str = "1d"):
    """
    Download historical data and save to CSV files.
    
    Useful for offline backtesting without API calls.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    fetcher = HistoricalDataFetcher()
    
    for symbol in symbols:
        df = fetcher.fetch(symbol, period, interval)
        if df is not None:
            filepath = os.path.join(output_dir, f"{symbol}.csv")
            df.to_csv(filepath)
            print(f"Saved {symbol} to {filepath} ({len(df)} rows)")
        else:
            print(f"Failed to download {symbol}")


# Test the fetcher
if __name__ == "__main__":
    fetcher = HistoricalDataFetcher()
    
    # Test single symbol
    print("Fetching AAPL data...")
    prices = fetcher.get_price_series("AAPL", period="1mo", interval="1h")
    print(f"Got {len(prices)} hourly prices for AAPL")
    
    if prices:
        print(f"First price: ${prices[0]:.2f}")
        print(f"Last price: ${prices[-1]:.2f}")
        print(f"Min: ${min(prices):.2f}, Max: ${max(prices):.2f}")
    
    # Test bars
    print("\nFetching GOOGL bars...")
    bars = fetcher.get_bars("GOOGL", period="5d", interval="1h")
    print(f"Got {len(bars)} bars for GOOGL")
    
    if bars:
        print(f"Latest bar: {bars[-1]}")
