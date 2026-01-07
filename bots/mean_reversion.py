"""
Mean Reversion Trading Bot
==========================

Strategy that profits from price returning to mean.
Buys oversold conditions, sells overbought.

Indicators used:
- Bollinger Bands for extremes
- RSI for overbought/oversold
- Z-score for deviation measurement
- SMA for mean price
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import TradingBot


class MeanReversionBot(TradingBot):
    """
    Mean reversion trading strategy.
    
    Entry (Long):
    - Price below lower Bollinger Band
    - RSI < 30 (oversold)
    - Z-score < -2
    
    Entry (Short):
    - Price above upper Bollinger Band
    - RSI > 70 (overbought)
    - Z-score > 2
    
    Exit:
    - Price returns to mean (SMA)
    - Or partial reversion target hit
    """

    def __init__(self, bot_id: str, config: Dict, broker: Any,
                 market: Any, indicators: Any, logger: Any):
        super().__init__(
            bot_id=bot_id,
            name="Mean Reversion Trader",
            config=config,
            broker=broker,
            market=market,
            indicators=indicators,
            logger=logger
        )
        
        # Strategy parameters
        self._lookback = self._bot_config.get('lookback_period', 50)
        self._std_threshold = self._bot_config.get('std_threshold', 2.0)
        self._reversion_target = self._bot_config.get('reversion_target', 0.5)
        self._stop_loss_pct = self._bot_config.get('stop_loss', 0.03)
        
        # Track positions
        self._entry_data: Dict[str, Dict] = {}

    def _get_strategy_name(self) -> str:
        return "mean_reversion"

    async def analyze(self, symbol: str) -> Optional[Dict]:
        """
        Analyze mean reversion signals.
        """
        # Get current price
        price = self._market.get_price(symbol)
        if not price:
            return None
        
        # Update indicator data
        asset = self._market.asset_manager.get_asset(symbol)
        if asset:
            self._indicators.update(symbol, price, asset.volume)
        
        # Get mean reversion signal from indicators
        mr_signal = self._indicators.get_mean_reversion_signal(
            symbol, self._lookback, self._std_threshold
        )
        
        if not mr_signal:
            return None
        
        # Additional indicators
        rsi = self._indicators.rsi(symbol)
        bollinger = self._indicators.bollinger_bands(symbol, 20, self._std_threshold)
        sma = self._indicators.sma(symbol, self._lookback)
        
        # Build indicator dict
        indicator_values = {
            'z_score': mr_signal['z_score'],
            'mean': mr_signal['mean'],
            'distance_pct': mr_signal['distance_pct'],
            'rsi': rsi.value if rsi else None,
            'rsi_signal': rsi.signal if rsi else None,
            'bb_percent_b': bollinger['percent_b'] if bollinger else None,
            'bb_signal': bollinger['signal'] if bollinger else None,
            'sma': sma,
            'price': price
        }
        
        # Get current position
        position = self.portfolio.get_position(symbol)
        has_position = position is not None and position.quantity > 0
        
        # Check for exit if we have position
        if has_position:
            return self._check_exit_signals(symbol, price, position, indicator_values, mr_signal)
        
        # Check for entry
        return self._check_entry_signals(symbol, price, indicator_values, mr_signal)

    def _check_entry_signals(self, symbol: str, price: float,
                            indicators: Dict, mr_signal: Dict) -> Optional[Dict]:
        """Check for mean reversion entry signals."""
        z_score = mr_signal['z_score']
        rsi = indicators['rsi']
        bb_signal = indicators['bb_signal']
        
        # Need key indicators
        if z_score is None:
            return {'action': 'hold', 'reason': 'Insufficient data'}
        
        signals = []
        score = 0
        action = 'hold'
        
        # Oversold conditions (buy signal)
        if z_score < -self._std_threshold:
            signals.append(f"Price {abs(z_score):.1f} std below mean")
            score += 2
            action = 'buy'
        
        if rsi is not None and rsi < 30:
            signals.append(f"RSI oversold ({rsi:.1f})")
            score += 1
            action = 'buy'
        
        if bb_signal == 'oversold':
            signals.append("Below Bollinger lower band")
            score += 1
            action = 'buy'
        
        # Overbought conditions (short signal) - but we'll skip shorting for simplicity
        # In production, you could add short selling here
        
        # Entry decision for long
        if action == 'buy' and score >= 2:
            target_price = mr_signal['mean'] + (
                (price - mr_signal['mean']) * (1 - self._reversion_target)
            )
            
            return {
                'action': 'buy',
                'symbol': symbol,
                'price': price,
                'confidence': min(1.0, score / 4),
                'reason': '; '.join(signals),
                'indicators': indicators,
                'mean_price': mr_signal['mean'],
                'target_price': target_price,
                'z_score': z_score,
                'stop_loss': price * (1 - self._stop_loss_pct)
            }
        
        return {
            'action': 'hold',
            'symbol': symbol,
            'reason': f"No extreme detected (Z: {z_score:.2f})",
            'indicators': indicators
        }

    def _check_exit_signals(self, symbol: str, price: float,
                           position: Any, indicators: Dict,
                           mr_signal: Dict) -> Optional[Dict]:
        """Check for exit signals."""
        entry_data = self._entry_data.get(symbol, {})
        entry_price = entry_data.get('price', position.avg_cost)
        target_price = entry_data.get('target', mr_signal['mean'])
        
        current_pnl_pct = (price - entry_price) / entry_price if entry_price > 0 else 0
        
        # Stop loss
        if current_pnl_pct <= -self._stop_loss_pct:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 1.0,
                'reason': f"Stop loss at {current_pnl_pct*100:.1f}%",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # Reversion target hit
        if price >= target_price:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 1.0,
                'reason': f"Reversion target reached (${target_price:.2f})",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # Mean reversion complete
        z_score = mr_signal['z_score']
        if z_score is not None and abs(z_score) < 0.5:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 0.8,
                'reason': f"Mean reversion complete (Z: {z_score:.2f})",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # RSI back to neutral
        rsi = indicators['rsi']
        if rsi is not None and 45 <= rsi <= 55:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 0.6,
                'reason': f"RSI normalized ({rsi:.1f})",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        return {
            'action': 'hold',
            'symbol': symbol,
            'reason': f"Waiting for reversion (P&L: {current_pnl_pct*100:.1f}%)",
            'indicators': indicators
        }

    async def execute(self, signal: Dict) -> bool:
        """Execute mean reversion trade."""
        if signal['action'] == 'hold':
            return False
        
        symbol = signal['symbol']
        price = signal['price']
        
        if signal['action'] == 'buy':
            # Calculate position size
            quantity = self.get_position_size(symbol, price)
            if quantity <= 0:
                return False
            
            # Execute buy
            success, msg = await self._api.buy_market(symbol, quantity)
            
            if success:
                # Store entry data for exit decisions
                self._entry_data[symbol] = {
                    'price': price,
                    'mean': signal.get('mean_price'),
                    'target': signal.get('target_price'),
                    'z_score': signal.get('z_score'),
                    'time': datetime.now()
                }
                
                # Set stop loss
                if 'stop_loss' in signal:
                    await self._api.set_stop_loss(symbol, quantity, signal['stop_loss'])
                
                return True
            
        elif signal['action'] == 'sell':
            quantity = signal.get('quantity')
            if not quantity:
                position = self.portfolio.get_position(symbol)
                quantity = position.quantity if position else 0
            
            if quantity <= 0:
                return False
            
            # Execute sell
            success, msg = await self._api.sell_market(symbol, quantity)
            
            if success:
                # Update stats
                pnl_pct = signal.get('pnl_pct', 0)
                is_win = pnl_pct > 0
                pnl = pnl_pct * quantity * price
                self.update_stats(pnl, is_win)
                
                # Clean up entry data
                if symbol in self._entry_data:
                    del self._entry_data[symbol]
                
                return True
        
        return False

