"""
Base Trading Bot Framework
==========================

Abstract base class and manager for trading bots.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class BotStatus(Enum):
    """Bot operational status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class BotStats:
    """Bot performance statistics."""
    trades_executed: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    peak_pnl: float = 0.0
    max_drawdown: float = 0.0
    decisions_made: int = 0
    signals_generated: int = 0
    start_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None

    @property
    def win_rate(self) -> float:
        total = self.winning_trades + self.losing_trades
        return (self.winning_trades / total * 100) if total > 0 else 0.0

    @property
    def avg_pnl_per_trade(self) -> float:
        return self.total_pnl / self.trades_executed if self.trades_executed > 0 else 0.0


class TradingBot(ABC):
    """
    Abstract base class for trading bots.
    
    All trading strategies must implement:
    - analyze(): Analyze market and generate signals
    - execute(): Execute trading decisions
    """

    def __init__(self, bot_id: str, name: str, config: Dict,
                 broker: Any, market: Any, indicators: Any, logger: Any):
        self.bot_id = bot_id
        self.name = name
        self._config = config
        self._broker = broker
        self._market = market
        self._indicators = indicators
        self._logger = logger
        
        # Bot-specific config
        self._bot_config = config.get('bots', {}).get(self._get_strategy_name(), {})
        self._trading_interval = config.get('bots', {}).get('trading_interval', 5)
        self._position_size_pct = self._bot_config.get('position_size', 0.1)
        
        # Trading API for this bot
        from trading.broker import TradingAPI
        self._api = TradingAPI(broker, bot_id)
        
        # State
        self._status = BotStatus.IDLE
        self._stats = BotStats()
        self._last_decision_time: Optional[datetime] = None
        self._active_positions: Dict[str, Dict] = {}
        self._pending_orders: List[str] = []
        
        # Running flag
        self._is_running = False

    @abstractmethod
    def _get_strategy_name(self) -> str:
        """Get strategy name for config lookup."""
        pass

    @abstractmethod
    async def analyze(self, symbol: str) -> Optional[Dict]:
        """
        Analyze market data and generate trading signal.
        
        Returns:
            Signal dict with 'action' ('buy', 'sell', 'hold'),
            'confidence', 'reason', and strategy-specific data.
        """
        pass

    @abstractmethod
    async def execute(self, signal: Dict) -> bool:
        """
        Execute a trading decision based on signal.
        
        Returns True if trade was executed.
        """
        pass

    @property
    def status(self) -> BotStatus:
        return self._status

    @property
    def stats(self) -> BotStats:
        return self._stats

    @property
    def portfolio(self):
        return self._api.portfolio

    def get_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols."""
        return {
            symbol: self._market.get_price(symbol)
            for symbol in self._market.asset_manager.get_symbols()
        }

    def get_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on config."""
        portfolio_value = self.portfolio.get_portfolio_value(self.get_prices())
        position_value = portfolio_value * self._position_size_pct
        shares = int(position_value / price)
        return max(1, shares)

    async def start(self):
        """Start the bot."""
        self._is_running = True
        self._status = BotStatus.RUNNING
        self._stats.start_time = datetime.now()
        
        self._logger.log_bot_decision(
            self.bot_id, self._get_strategy_name(), "",
            "start", "Bot started", {}
        )

    async def stop(self):
        """Stop the bot."""
        self._is_running = False
        self._status = BotStatus.STOPPED
        
        self._logger.log_bot_decision(
            self.bot_id, self._get_strategy_name(), "",
            "stop", "Bot stopped", {}
        )

    def pause(self):
        """Pause the bot."""
        self._status = BotStatus.PAUSED

    def resume(self):
        """Resume the bot."""
        if self._status == BotStatus.PAUSED:
            self._status = BotStatus.RUNNING

    async def run_cycle(self, symbols: List[str]):
        """Run one trading cycle across all symbols."""
        if self._status != BotStatus.RUNNING:
            return
        
        for symbol in symbols:
            try:
                # Analyze
                signal = await self.analyze(symbol)
                self._stats.decisions_made += 1
                
                if signal and signal.get('action') != 'hold':
                    self._stats.signals_generated += 1
                    
                    # Log decision
                    self._logger.log_bot_decision(
                        self.bot_id, self._get_strategy_name(), symbol,
                        signal['action'], signal.get('reason', ''),
                        signal.get('indicators', {})
                    )
                    
                    # Execute if action required
                    executed = await self.execute(signal)
                    if executed:
                        self._stats.trades_executed += 1
                        self._stats.last_trade_time = datetime.now()
                
            except Exception as e:
                self._logger.log_error(
                    "bot_error", f"Bot {self.bot_id} error on {symbol}: {str(e)}"
                )
                self._status = BotStatus.ERROR

    def update_stats(self, pnl: float, is_win: bool):
        """Update bot statistics after a trade."""
        self._stats.total_pnl += pnl
        
        if is_win:
            self._stats.winning_trades += 1
        else:
            self._stats.losing_trades += 1
        
        # Track peak P&L
        if self._stats.total_pnl > self._stats.peak_pnl:
            self._stats.peak_pnl = self._stats.total_pnl
        
        # Track drawdown
        if self._stats.peak_pnl > 0:
            drawdown = (self._stats.peak_pnl - self._stats.total_pnl) / self._stats.peak_pnl * 100
            if drawdown > self._stats.max_drawdown:
                self._stats.max_drawdown = drawdown

    def get_summary(self) -> Dict:
        """Get bot summary."""
        prices = self.get_prices()
        return {
            'bot_id': self.bot_id,
            'name': self.name,
            'strategy': self._get_strategy_name(),
            'status': self._status.value,
            'stats': {
                'trades': self._stats.trades_executed,
                'wins': self._stats.winning_trades,
                'losses': self._stats.losing_trades,
                'win_rate': self._stats.win_rate,
                'total_pnl': self._stats.total_pnl,
                'avg_pnl': self._stats.avg_pnl_per_trade,
                'max_drawdown': self._stats.max_drawdown,
                'decisions': self._stats.decisions_made,
                'signals': self._stats.signals_generated
            },
            'portfolio_value': self.portfolio.get_portfolio_value(prices),
            'positions': len(self.portfolio.get_all_positions())
        }


class BotManager:
    """
    Manages multiple trading bots.
    
    Coordinates bot execution and tracks performance.
    """

    def __init__(self, config: Dict, broker: Any, market: Any, 
                 indicators: Any, logger: Any):
        self._config = config
        self._broker = broker
        self._market = market
        self._indicators = indicators
        self._logger = logger
        
        self._bots: Dict[str, TradingBot] = {}
        self._is_running = False
        self._trading_interval = config.get('bots', {}).get('trading_interval', 5)

    def register_bot(self, bot: TradingBot):
        """Register a bot."""
        self._bots[bot.bot_id] = bot

    def get_bot(self, bot_id: str) -> Optional[TradingBot]:
        """Get bot by ID."""
        return self._bots.get(bot_id)

    def get_all_bots(self) -> List[TradingBot]:
        """Get all registered bots."""
        return list(self._bots.values())

    async def start_all(self):
        """Start all bots."""
        self._is_running = True
        for bot in self._bots.values():
            await bot.start()

    async def stop_all(self):
        """Stop all bots."""
        self._is_running = False
        for bot in self._bots.values():
            await bot.stop()

    async def run_trading_cycle(self):
        """Run one trading cycle for all bots."""
        if not self._is_running:
            return
        
        symbols = self._market.asset_manager.get_symbols()
        
        # Run bots concurrently
        tasks = [
            bot.run_cycle(symbols)
            for bot in self._bots.values()
            if bot.status == BotStatus.RUNNING
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run_loop(self):
        """Continuous trading loop."""
        while self._is_running:
            await self.run_trading_cycle()
            await asyncio.sleep(self._trading_interval)

    def get_leaderboard(self) -> List[Dict]:
        """Get bot performance leaderboard."""
        summaries = [bot.get_summary() for bot in self._bots.values()]
        return sorted(summaries, key=lambda x: x['stats']['total_pnl'], reverse=True)

    def get_best_bot(self) -> Optional[Dict]:
        """Get the best performing bot."""
        leaderboard = self.get_leaderboard()
        return leaderboard[0] if leaderboard else None

    def get_aggregate_stats(self) -> Dict:
        """Get aggregate statistics across all bots."""
        total_trades = sum(b.stats.trades_executed for b in self._bots.values())
        total_pnl = sum(b.stats.total_pnl for b in self._bots.values())
        total_wins = sum(b.stats.winning_trades for b in self._bots.values())
        total_losses = sum(b.stats.losing_trades for b in self._bots.values())
        
        return {
            'total_bots': len(self._bots),
            'active_bots': sum(1 for b in self._bots.values() if b.status == BotStatus.RUNNING),
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'total_wins': total_wins,
            'total_losses': total_losses,
            'overall_win_rate': (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
        }

