from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import TradingBot


class MomentumBot(TradingBot):
    """
    buys when things are going up, sells when they stop
    classic trend following stuff
    """

    def __init__(self, bot_id: str, config: Dict, broker: Any, 
                 market: Any, indicators: Any, logger: Any):
        super().__init__(
            bot_id=bot_id,
            name="Momentum Trader",
            config=config,
            broker=broker,
            market=market,
            indicators=indicators,
            logger=logger
        )
        
        self._lookback = self._bot_config.get('lookback_period', 20)
        self._entry_threshold = self._bot_config.get('entry_threshold', 0.02)
        self._stop_loss_pct = self._bot_config.get('stop_loss', 0.05)
        self._take_profit_pct = self._bot_config.get('take_profit', 0.10)
        
        self._entry_prices: Dict[str, float] = {}

    def _get_strategy_name(self) -> str:
        return "momentum"

    async def analyze(self, symbol: str) -> Optional[Dict]:
        price = self._market.get_price(symbol)
        if not price:
            return None
        
        asset = self._market.asset_manager.get_asset(symbol)
        if asset:
            self._indicators.update(symbol, price, asset.volume)
        
        roc = self._indicators.rate_of_change(symbol, self._lookback)
        rsi = self._indicators.rsi(symbol)
        macd = self._indicators.macd(symbol)
        volume_spike = self._indicators.volume_spike(symbol)
        momentum = self._indicators.momentum(symbol, self._lookback)
        
        indicator_values = {
            'roc': roc,
            'rsi': rsi.value if rsi else None,
            'macd_trend': macd['trend'] if macd else None,
            'macd_histogram': macd['histogram'] if macd else None,
            'volume_spike': volume_spike,
            'momentum': momentum,
            'price': price
        }
        
        position = self.portfolio.get_position(symbol)
        has_position = position is not None and position.quantity > 0
        
        if has_position:
            return self._check_exit_signals(symbol, price, position, indicator_values)
        
        return self._check_entry_signals(symbol, price, indicator_values)

    def _check_entry_signals(self, symbol: str, price: float,
                            indicators: Dict) -> Optional[Dict]:
        roc = indicators['roc']
        rsi = indicators['rsi']
        macd = indicators['macd_trend']
        momentum = indicators['momentum']
        
        if None in [roc, rsi, macd, momentum]:
            return {'action': 'hold', 'reason': 'not enough data yet'}
        
        signals = []
        score = 0
        
        # main signal - is there momentum?
        if roc > self._entry_threshold * 100:
            signals.append("strong momentum")
            score += 2
        elif roc > 0:
            signals.append("positive momentum")
            score += 1
        
        # rsi check - dont buy overbought
        if 30 <= rsi <= 60:
            signals.append("rsi ok")
            score += 1
        elif rsi > 70:
            signals.append("overbought warning")
            score -= 1
        
        if macd == 'bullish':
            signals.append("macd bullish")
            score += 1
        
        if indicators['volume_spike']:
            signals.append("volume confirms")
            score += 1
        
        if score >= 3:
            return {
                'action': 'buy',
                'symbol': symbol,
                'price': price,
                'confidence': min(1.0, score / 5),
                'reason': '; '.join(signals),
                'indicators': indicators,
                'stop_loss': price * (1 - self._stop_loss_pct),
                'take_profit': price * (1 + self._take_profit_pct)
            }
        
        return {
            'action': 'hold',
            'symbol': symbol,
            'reason': f"score {score} too low",
            'indicators': indicators
        }

    def _check_exit_signals(self, symbol: str, price: float,
                           position: Any, indicators: Dict) -> Optional[Dict]:
        entry_price = self._entry_prices.get(symbol, position.avg_cost)
        current_pnl_pct = (price - entry_price) / entry_price
        
        roc = indicators['roc']
        rsi = indicators['rsi']
        
        # stop loss
        if current_pnl_pct <= -self._stop_loss_pct:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 1.0,
                'reason': f"stop loss hit at {current_pnl_pct*100:.1f}%",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # take profit
        if current_pnl_pct >= self._take_profit_pct:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 1.0,
                'reason': f"target hit! +{current_pnl_pct*100:.1f}%",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # momentum died
        if roc is not None and roc < -self._entry_threshold * 50:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 0.7,
                'reason': f"momentum fading (roc: {roc:.2f}%)",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        # too overbought
        if rsi is not None and rsi > 80:
            return {
                'action': 'sell',
                'symbol': symbol,
                'price': price,
                'quantity': position.quantity,
                'confidence': 0.6,
                'reason': f"rsi way overbought ({rsi:.1f})",
                'indicators': indicators,
                'pnl_pct': current_pnl_pct
            }
        
        return {
            'action': 'hold',
            'symbol': symbol,
            'reason': f"holding, pnl: {current_pnl_pct*100:.1f}%",
            'indicators': indicators
        }

    async def execute(self, signal: Dict) -> bool:
        if signal['action'] == 'hold':
            return False
        
        symbol = signal['symbol']
        price = signal['price']
        
        if signal['action'] == 'buy':
            quantity = self.get_position_size(symbol, price)
            if quantity <= 0:
                return False
            
            success, msg = await self._api.buy_market(symbol, quantity)
            
            if success:
                self._entry_prices[symbol] = price
                
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
            
            success, msg = await self._api.sell_market(symbol, quantity)
            
            if success:
                pnl_pct = signal.get('pnl_pct', 0)
                is_win = pnl_pct > 0
                pnl = pnl_pct * quantity * price
                self.update_stats(pnl, is_win)
                
                if symbol in self._entry_prices:
                    del self._entry_prices[symbol]
                
                return True
        
        return False
