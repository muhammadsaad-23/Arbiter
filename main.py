#!/usr/bin/env python3
"""
stock market sim - run with python main.py
"""

import asyncio
import argparse
import signal
import sys
import os
from datetime import datetime
from typing import Dict, Optional

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.market import MarketEngine
from engine.events import EventType, Sentiment
from trading.broker import Broker
from bots.base import BotManager
from bots.momentum import MomentumBot
from bots.mean_reversion import MeanReversionBot
from bots.arbitrage import ArbitrageBot
from utils.logger import AuditLogger
from utils.indicators import TechnicalIndicators


class TerminalDashboard:
    def __init__(self, market: MarketEngine, broker: Broker, 
                 bot_manager: BotManager, config: Dict):
        self._market = market
        self._broker = broker
        self._bot_manager = bot_manager
        self._config = config
        
        self._refresh_rate = config.get('dashboard', {}).get('refresh_rate', 1.0)
        self._is_running = False
        self._start_time = datetime.now()
        
        # try rich, fall back to basic output
        try:
            from rich.console import Console
            from rich.table import Table
            self._console = Console()
            self._use_rich = True
        except ImportError:
            self._use_rich = False
            print("tip: pip install rich for better output")

    def _format_price_change(self, change: float, change_pct: float) -> str:
        if change >= 0:
            return f"+${change:.2f} (+{change_pct:.2f}%)"
        else:
            return f"-${abs(change):.2f} ({change_pct:.2f}%)"

    def _create_prices_table(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append(f"{'Symbol':<8} {'Price':>10} {'Change':>15} {'Volume':>12} {'Status':<10}")
        lines.append("-" * 70)
        
        for asset in self._market.asset_manager.get_all_assets():
            change, pct = asset.get_daily_change()
            status = "HALTED" if asset.is_halted else "ACTIVE"
            change_str = self._format_price_change(change, pct)
            
            arrow = "▲" if change >= 0 else "▼"
            lines.append(
                f"{asset.symbol:<8} ${asset.price:>9.2f} {arrow} {change_str:>12} "
                f"{asset.volume:>11,} {status:<10}"
            )
        
        lines.append("=" * 70)
        return "\n".join(lines)

    def _create_bots_table(self) -> str:
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("BOT PERFORMANCE")
        lines.append("-" * 60)
        lines.append(f"{'Bot':<25} {'P&L':>12} {'Trades':>8} {'Win Rate':>10}")
        lines.append("-" * 60)
        
        for bot in self._bot_manager.get_all_bots():
            summary = bot.get_summary()
            pnl = summary['stats']['total_pnl']
            pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
            
            lines.append(
                f"{summary['name']:<25} {pnl_str:>12} "
                f"{summary['stats']['trades']:>8} "
                f"{summary['stats']['win_rate']:>9.1f}%"
            )
        
        lines.append("=" * 60)
        return "\n".join(lines)

    def _create_market_summary(self) -> str:
        summary = self._market.get_market_summary()
        stats = self._market.asset_manager.get_market_stats()
        
        elapsed = (datetime.now() - self._start_time).total_seconds()
        
        lines = []
        lines.append("\n" + "=" * 50)
        lines.append("MARKET SUMMARY")
        lines.append("-" * 50)
        lines.append(f"Elapsed Time:     {int(elapsed)}s")
        lines.append(f"Tick Count:       {summary['tick_count']:,}")
        lines.append(f"Total Volume:     {stats['total_volume']:,}")
        lines.append(f"Avg Volatility:   {stats['avg_volatility']*100:.2f}%")
        lines.append(f"Advancing:        {stats['advancing']}")
        lines.append(f"Declining:        {stats['declining']}")
        lines.append(f"Halted:           {stats['halted']}")
        lines.append(f"Events:           {summary['events_processed']}")
        lines.append("=" * 50)
        
        return "\n".join(lines)

    def render(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("\n" + "█" * 70)
        print("█" + " " * 20 + "STOCK MARKET SIMULATOR" + " " * 26 + "█")
        print("█" * 70 + "\n")
        
        print(self._create_prices_table())
        print(self._create_bots_table())
        print(self._create_market_summary())
        print("\nPress Ctrl+C to stop simulation")

    async def run(self):
        self._is_running = True
        while self._is_running:
            self.render()
            await asyncio.sleep(self._refresh_rate)

    def stop(self):
        self._is_running = False


class StockSimulator:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        self._logger = AuditLogger(self._config)
        
        self._market: Optional[MarketEngine] = None
        self._broker: Optional[Broker] = None
        self._bot_manager: Optional[BotManager] = None
        self._indicators: Optional[TechnicalIndicators] = None
        self._dashboard: Optional[TerminalDashboard] = None
        
        self._is_running = False
        self._shutdown_event = asyncio.Event()
        self._start_time: Optional[datetime] = None

    async def initialize(self):
        print("Initializing simulation...")
        
        self._market = MarketEngine(self._config, self._logger)
        await self._market.initialize()
        print(f"  ✓ Market initialized with {len(self._market.asset_manager.get_symbols())} assets")
        
        self._broker = Broker(self._config, self._market, self._logger)
        await self._broker.initialize()
        print("  ✓ Broker initialized")
        
        self._indicators = TechnicalIndicators()
        print("  ✓ Technical indicators ready")
        
        self._bot_manager = BotManager(
            self._config, self._broker, self._market, 
            self._indicators, self._logger
        )
        
        self._market.register_price_callback(self._on_price_update)
        print("  ✓ Bot manager initialized")

    async def _on_price_update(self, updates: Dict[str, float]):
        for symbol, price in updates.items():
            asset = self._market.asset_manager.get_asset(symbol)
            if asset:
                self._indicators.update(symbol, price, asset.volume)

    async def setup_bots(self, enable_bots: bool = True):
        if not enable_bots:
            print("  ℹ Bots disabled")
            return
        
        # momentum bot
        mom_bot = MomentumBot(
            bot_id="BOT-MOMENTUM-001",
            config=self._config,
            broker=self._broker,
            market=self._market,
            indicators=self._indicators,
            logger=self._logger
        )
        self._bot_manager.register_bot(mom_bot)
        print("  ✓ Momentum bot registered")
        
        # mean reversion
        mr_bot = MeanReversionBot(
            bot_id="BOT-MEANREV-001",
            config=self._config,
            broker=self._broker,
            market=self._market,
            indicators=self._indicators,
            logger=self._logger
        )
        self._bot_manager.register_bot(mr_bot)
        print("  ✓ Mean Reversion bot registered")
        
        # arbitrage - TODO: this one needs more testing
        arb_bot = ArbitrageBot(
            bot_id="BOT-ARB-001",
            config=self._config,
            broker=self._broker,
            market=self._market,
            indicators=self._indicators,
            logger=self._logger
        )
        self._bot_manager.register_bot(arb_bot)
        print("  ✓ Arbitrage bot registered")

    async def run(self, duration: Optional[int] = None, 
                  tick_rate: Optional[float] = None,
                  enable_bots: bool = True,
                  show_dashboard: bool = True):
        
        if duration:
            self._config['simulation']['duration_seconds'] = duration
            self._market._duration = duration
        if tick_rate:
            self._config['simulation']['tick_rate'] = tick_rate
            self._market._tick_rate = tick_rate
            self._market._tick_interval = 1.0 / tick_rate
        
        await self.setup_bots(enable_bots)
        
        self._start_time = datetime.now()
        self._is_running = True
        
        print(f"\nStarting simulation...")
        print(f"  Duration: {self._market._duration}s")
        print(f"  Tick Rate: {self._market._tick_rate}/s")
        print(f"  Bots: {'Enabled' if enable_bots else 'Disabled'}")
        print()
        
        if enable_bots:
            await self._bot_manager.start_all()
        
        if show_dashboard:
            self._dashboard = TerminalDashboard(
                self._market, self._broker, self._bot_manager, self._config
            )
        
        tasks = [self._market.start()]
        
        if enable_bots:
            tasks.append(self._bot_manager.run_loop())
        
        if show_dashboard:
            tasks.append(self._dashboard.run())
        
        tasks.append(self._run_settlement_loop())
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def _run_settlement_loop(self):
        while self._is_running and self._market.is_running:
            await self._broker.run_settlement_cycle()
            await asyncio.sleep(1)

    async def shutdown(self):
        self._is_running = False
        
        if self._dashboard:
            self._dashboard.stop()
        
        if self._bot_manager:
            await self._bot_manager.stop_all()
        
        if self._market:
            await self._market.stop()
        
        self._print_summary()

    def _print_summary(self):
        print("\n" + "=" * 70)
        print(" " * 20 + "SIMULATION COMPLETE")
        print("=" * 70 + "\n")
        
        if self._market:
            summary = self._market.get_market_summary()
            elapsed = (datetime.now() - self._start_time).total_seconds()
            
            print(f"Duration:              {int(elapsed)} seconds")
            print(f"Total Ticks:           {summary['tick_count']:,}")
            print(f"Events Processed:      {summary['events_processed']:,}")
            print(f"Avg Volatility:        {summary['avg_volatility']*100:.2f}%")
        
        if self._broker:
            broker_stats = self._broker.get_broker_stats()
            print(f"\nTotal Orders:          {broker_stats['total_orders']:,}")
            print(f"Total Trades:          {broker_stats['total_trades']:,}")
            print(f"Trade Value:           ${broker_stats['total_trade_value']:,.2f}")
        
        if self._bot_manager:
            print("\n" + "-" * 50)
            print("BOT PERFORMANCE SUMMARY")
            print("-" * 50)
            
            leaderboard = self._bot_manager.get_leaderboard()
            best_bot = None
            best_pnl = float('-inf')
            
            for i, bot in enumerate(leaderboard, 1):
                pnl = bot['stats']['total_pnl']
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                
                print(f"  {i}. {bot['name']:<25}")
                print(f"     P&L: {pnl_str}")
                print(f"     Trades: {bot['stats']['trades']}")
                print(f"     Win Rate: {bot['stats']['win_rate']:.1f}%")
                print(f"     Portfolio Value: ${bot['portfolio_value']:,.2f}")
                print()
                
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_bot = bot['name']
            
            if best_bot:
                print("-" * 50)
                pnl_display = f"+${best_pnl:,.2f}" if best_pnl >= 0 else f"-${abs(best_pnl):,.2f}"
                print(f"Most Profitable Bot: {best_bot} ({pnl_display})")
        
        if self._broker:
            portfolios = self._broker.get_all_portfolios()
            if portfolios:
                max_peak = max(p.peak_value for p in portfolios)
                print(f"Portfolio Peak Value: ${max_peak:,.2f}")
        
        print("\n" + "=" * 70)
        print("Logs saved to: logs/audit.log")
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description='Stock Market Simulator')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--duration', type=int, help='Simulation duration in seconds')
    parser.add_argument('--tick-rate', type=float, help='Price updates per second')
    parser.add_argument('--no-bots', action='store_true', help='Disable trading bots')
    parser.add_argument('--no-dashboard', action='store_true', help='Disable terminal dashboard')
    
    args = parser.parse_args()
    
    simulator = StockSimulator(args.config)
    
    def signal_handler(sig, frame):
        print("\n\nShutting down...")
        asyncio.create_task(simulator.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    async def run():
        await simulator.initialize()
        await simulator.run(
            duration=args.duration,
            tick_rate=args.tick_rate,
            enable_bots=not args.no_bots,
            show_dashboard=not args.no_dashboard
        )
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
