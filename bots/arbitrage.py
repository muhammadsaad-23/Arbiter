"""
Arbitrage Trading Bot
=====================

Exploits price discrepancies between correlated assets.
When correlation breaks down, trade the convergence.

Strategy:
- Monitor highly correlated asset pairs
- When spread exceeds threshold, go long underperformer, short outperformer
- Exit when spread normalizes
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np

from .base import TradingBot


class ArbitrageBot(TradingBot):
    """
    Statistical arbitrage strategy.
    
    Trades pairs of correlated assets when their spread diverges
    from historical norms.
    
    Entry:
    - Pair correlation > threshold
    - Spread deviation > threshold
    - Volume confirmation
    
    Exit:
    - Spread returns to mean
    - Maximum holding period
    - Stop loss on pair P&L
    """

    def __init__(self, bot_id: str, config: Dict, broker: Any,
                 market: Any, indicators: Any, logger: Any):
        super().__init__(
            bot_id=bot_id,
            name="Arbitrage Trader",
            config=config,
            broker=broker,
            market=market,
            indicators=indicators,
            logger=logger
        )
        
        # Strategy parameters
        self._correlation_threshold = self._bot_config.get('correlation_threshold', 0.8)
        self._spread_threshold = self._bot_config.get('spread_threshold', 0.01)
        self._max_holding_ticks = 100  # Maximum ticks to hold position
        self._stop_loss_pct = 0.02  # 2% pair stop loss
        
        # Track pairs and positions
        self._correlated_pairs: List[Tuple[str, str, float]] = []
        self._active_pair_trades: Dict[str, Dict] = {}
        self._spread_history: Dict[str, List[float]] = {}

    def _get_strategy_name(self) -> str:
        return "arbitrage"

    async def start(self):
        """Initialize correlated pairs on start."""
        await super().start()
        self._update_correlated_pairs()

    def _update_correlated_pairs(self):
        """Update list of correlated pairs for trading."""
        self._correlated_pairs = self._market.asset_manager.get_correlated_pairs(
            self._correlation_threshold
        )

    def _get_pair_key(self, symbol1: str, symbol2: str) -> str:
        """Create consistent key for a pair."""
        return f"{min(symbol1, symbol2)}_{max(symbol1, symbol2)}"

    def _calculate_spread(self, price1: float, price2: float) -> float:
        """Calculate normalized spread between two prices."""
        if price1 == 0 or price2 == 0:
            return 0
        return (price1 - price2) / ((price1 + price2) / 2)

    def _update_spread_history(self, pair_key: str, spread: float):
        """Track spread history for a pair."""
        if pair_key not in self._spread_history:
            self._spread_history[pair_key] = []
        self._spread_history[pair_key].append(spread)
        # Keep last 100 spreads
        if len(self._spread_history[pair_key]) > 100:
            self._spread_history[pair_key] = self._spread_history[pair_key][-100:]

    def _get_spread_z_score(self, pair_key: str, current_spread: float) -> Optional[float]:
        """Calculate Z-score of current spread."""
        history = self._spread_history.get(pair_key, [])
        if len(history) < 20:
            return None
        
        mean = np.mean(history)
        std = np.std(history)
        if std == 0:
            return 0
        return (current_spread - mean) / std

    async def analyze(self, symbol: str) -> Optional[Dict]:
        """
        Analyze arbitrage opportunities involving this symbol.
        
        Note: This method is called per-symbol, but arbitrage requires pairs.
        We check if this symbol is in any active pairs.
        """
        # Update indicator data
        price = self._market.get_price(symbol)
        if not price:
            return None
        
        asset = self._market.asset_manager.get_asset(symbol)
        if asset:
            self._indicators.update(symbol, price, asset.volume)
        
        # Check pairs involving this symbol
        relevant_pairs = [
            (s1, s2, corr) for s1, s2, corr in self._correlated_pairs
            if symbol in (s1, s2)
        ]
        
        if not relevant_pairs:
            return None
        
        # Check each pair
        for symbol1, symbol2, correlation in relevant_pairs:
            signal = await self._analyze_pair(symbol1, symbol2, correlation)
            if signal and signal['action'] != 'hold':
                return signal
        
        return {'action': 'hold', 'reason': 'No arbitrage opportunity'}

    async def _analyze_pair(self, symbol1: str, symbol2: str,
                           correlation: float) -> Optional[Dict]:
        """Analyze a specific pair for arbitrage."""
        price1 = self._market.get_price(symbol1)
        price2 = self._market.get_price(symbol2)
        
        if not price1 or not price2:
            return None
        
        pair_key = self._get_pair_key(symbol1, symbol2)
        spread = self._calculate_spread(price1, price2)
        self._update_spread_history(pair_key, spread)
        
        z_score = self._get_spread_z_score(pair_key, spread)
        
        indicator_values = {
            'symbol1': symbol1,
            'symbol2': symbol2,
            'price1': price1,
            'price2': price2,
            'spread': spread,
            'z_score': z_score,
            'correlation': correlation
        }
        
        # Check if we have active position in this pair
        if pair_key in self._active_pair_trades:
            return self._check_pair_exit(pair_key, indicator_values)
        
        # Check for entry
        return self._check_pair_entry(pair_key, indicator_values)

    def _check_pair_entry(self, pair_key: str, 
                         indicators: Dict) -> Optional[Dict]:
        """Check for pair entry signals."""
        z_score = indicators['z_score']
        spread = indicators['spread']
        
        if z_score is None:
            return {'action': 'hold', 'reason': 'Insufficient spread history'}
        
        # Look for extreme spread deviation
        if abs(z_score) < 2.0:
            return {
                'action': 'hold',
                'reason': f'Spread Z-score ({z_score:.2f}) not extreme enough'
            }
        
        symbol1 = indicators['symbol1']
        symbol2 = indicators['symbol2']
        
        # Determine direction
        if z_score > 2.0:
            # Spread too high: symbol1 overpriced relative to symbol2
            # Long symbol2, short symbol1
            long_symbol = symbol2
            short_symbol = symbol1
            long_price = indicators['price2']
            short_price = indicators['price1']
        else:
            # Spread too low: symbol1 underpriced relative to symbol2
            # Long symbol1, short symbol2
            long_symbol = symbol1
            short_symbol = symbol2
            long_price = indicators['price1']
            short_price = indicators['price2']
        
        return {
            'action': 'arbitrage',
            'pair_key': pair_key,
            'long_symbol': long_symbol,
            'short_symbol': short_symbol,
            'long_price': long_price,
            'short_price': short_price,
            'z_score': z_score,
            'spread': spread,
            'confidence': min(1.0, abs(z_score) / 4),
            'reason': f'Spread divergence (Z: {z_score:.2f})',
            'indicators': indicators
        }

    def _check_pair_exit(self, pair_key: str,
                        indicators: Dict) -> Optional[Dict]:
        """Check for pair exit signals."""
        trade_data = self._active_pair_trades[pair_key]
        z_score = indicators['z_score']
        current_spread = indicators['spread']
        
        entry_spread = trade_data['entry_spread']
        entry_z = trade_data['entry_z_score']
        holding_ticks = trade_data.get('ticks', 0) + 1
        trade_data['ticks'] = holding_ticks
        
        # Calculate pair P&L
        long_symbol = trade_data['long_symbol']
        short_symbol = trade_data['short_symbol']
        
        if long_symbol == indicators['symbol1']:
            current_long_price = indicators['price1']
            current_short_price = indicators['price2']
        else:
            current_long_price = indicators['price2']
            current_short_price = indicators['price1']
        
        entry_long = trade_data['long_price']
        entry_short = trade_data['short_price']
        
        long_pnl_pct = (current_long_price - entry_long) / entry_long
        short_pnl_pct = (entry_short - current_short_price) / entry_short
        total_pnl_pct = (long_pnl_pct + short_pnl_pct) / 2
        
        # Check exit conditions
        
        # Spread normalized (Z-score returned to near 0)
        if z_score is not None and abs(z_score) < 0.5:
            return {
                'action': 'close_arbitrage',
                'pair_key': pair_key,
                'long_symbol': long_symbol,
                'short_symbol': short_symbol,
                'confidence': 1.0,
                'reason': f'Spread normalized (Z: {z_score:.2f})',
                'pnl_pct': total_pnl_pct,
                'indicators': indicators
            }
        
        # Stop loss on pair
        if total_pnl_pct < -self._stop_loss_pct:
            return {
                'action': 'close_arbitrage',
                'pair_key': pair_key,
                'long_symbol': long_symbol,
                'short_symbol': short_symbol,
                'confidence': 1.0,
                'reason': f'Stop loss on pair ({total_pnl_pct*100:.1f}%)',
                'pnl_pct': total_pnl_pct,
                'indicators': indicators
            }
        
        # Maximum holding period
        if holding_ticks > self._max_holding_ticks:
            return {
                'action': 'close_arbitrage',
                'pair_key': pair_key,
                'long_symbol': long_symbol,
                'short_symbol': short_symbol,
                'confidence': 0.7,
                'reason': 'Max holding period exceeded',
                'pnl_pct': total_pnl_pct,
                'indicators': indicators
            }
        
        # Profitable exit - spread moved in our favor
        if total_pnl_pct > 0.01:  # 1% profit
            return {
                'action': 'close_arbitrage',
                'pair_key': pair_key,
                'long_symbol': long_symbol,
                'short_symbol': short_symbol,
                'confidence': 0.8,
                'reason': f'Take profit ({total_pnl_pct*100:.1f}%)',
                'pnl_pct': total_pnl_pct,
                'indicators': indicators
            }
        
        return {
            'action': 'hold',
            'reason': f'Holding pair (P&L: {total_pnl_pct*100:.1f}%, Z: {z_score:.2f})',
            'indicators': indicators
        }

    async def execute(self, signal: Dict) -> bool:
        """Execute arbitrage trade."""
        action = signal['action']
        
        if action == 'hold':
            return False
        
        if action == 'arbitrage':
            return await self._execute_pair_entry(signal)
        
        if action == 'close_arbitrage':
            return await self._execute_pair_exit(signal)
        
        return False

    async def _execute_pair_entry(self, signal: Dict) -> bool:
        """Execute pair entry (long one, short the other)."""
        pair_key = signal['pair_key']
        long_symbol = signal['long_symbol']
        short_symbol = signal['short_symbol']
        long_price = signal['long_price']
        short_price = signal['short_price']
        
        # Calculate position sizes (equal dollar amounts)
        position_value = self.portfolio.cash * self._position_size_pct / 2
        long_qty = int(position_value / long_price)
        short_qty = int(position_value / short_price)
        
        if long_qty <= 0 or short_qty <= 0:
            return False
        
        # Execute long leg
        long_success, _ = await self._api.buy_market(long_symbol, long_qty)
        
        # Note: In a real implementation, you'd handle short selling properly
        # For simulation, we'll just track it
        
        if long_success:
            self._active_pair_trades[pair_key] = {
                'long_symbol': long_symbol,
                'short_symbol': short_symbol,
                'long_price': long_price,
                'short_price': short_price,
                'long_qty': long_qty,
                'short_qty': short_qty,
                'entry_spread': signal['spread'],
                'entry_z_score': signal['z_score'],
                'entry_time': datetime.now(),
                'ticks': 0
            }
            return True
        
        return False

    async def _execute_pair_exit(self, signal: Dict) -> bool:
        """Close pair trade."""
        pair_key = signal['pair_key']
        
        if pair_key not in self._active_pair_trades:
            return False
        
        trade_data = self._active_pair_trades[pair_key]
        long_symbol = trade_data['long_symbol']
        long_qty = trade_data['long_qty']
        
        # Close long position
        sell_success, _ = await self._api.sell_market(long_symbol, long_qty)
        
        if sell_success:
            # Update stats
            pnl_pct = signal.get('pnl_pct', 0)
            is_win = pnl_pct > 0
            # Approximate P&L
            pnl = pnl_pct * (long_qty * trade_data['long_price'])
            self.update_stats(pnl, is_win)
            
            del self._active_pair_trades[pair_key]
            return True
        
        return False

    async def run_cycle(self, symbols: List[str]):
        """Override to process pairs instead of individual symbols."""
        if self._status.value != 'running':
            return
        
        # Periodically update correlated pairs
        if self._stats.decisions_made % 10 == 0:
            self._update_correlated_pairs()
        
        # Process each pair
        processed_pairs = set()
        
        for symbol1, symbol2, correlation in self._correlated_pairs:
            pair_key = self._get_pair_key(symbol1, symbol2)
            
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            
            try:
                signal = await self._analyze_pair(symbol1, symbol2, correlation)
                self._stats.decisions_made += 1
                
                if signal and signal['action'] not in ['hold', None]:
                    self._stats.signals_generated += 1
                    
                    self._logger.log_bot_decision(
                        self.bot_id, 'arbitrage', f"{symbol1}/{symbol2}",
                        signal['action'], signal.get('reason', ''),
                        signal.get('indicators', {})
                    )
                    
                    executed = await self.execute(signal)
                    if executed:
                        self._stats.trades_executed += 1
                        self._stats.last_trade_time = datetime.now()
                        
            except Exception as e:
                self._logger.log_error(
                    "arbitrage_error", 
                    f"Pair {symbol1}/{symbol2} error: {str(e)}"
                )

