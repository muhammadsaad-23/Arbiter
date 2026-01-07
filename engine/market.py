"""
Market Simulation Engine
========================

Core engine that orchestrates market simulation:
- Async price updates at configurable tick rate
- Handles 10,000+ concurrent events efficiently
- Coordinates assets, events, and trading
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

from .asset import AssetManager, PriceModel
from .events import EventSystem, MarketEvent


@dataclass
class MarketStats:
    """Aggregate market statistics."""
    tick_count: int = 0
    total_volume: int = 0
    events_processed: int = 0
    avg_volatility: float = 0.0
    market_sentiment: float = 0.0  # -1.0 to 1.0
    advancing: int = 0
    declining: int = 0
    halted: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)


class MarketEngine:
    """
    Main market simulation engine.
    
    Features:
    - Async event loop for high-performance simulation
    - Configurable tick rate
    - Event-driven architecture
    - Thread-safe operations
    - Graceful shutdown handling
    """

    def __init__(self, config: Dict, logger: Any):
        self._config = config
        self._logger = logger
        
        # Core components
        self._asset_manager = AssetManager(config)
        self._event_system: Optional[EventSystem] = None
        
        # Simulation settings
        sim_config = config.get('simulation', {})
        self._tick_rate = sim_config.get('tick_rate', 1.0)
        self._duration = sim_config.get('duration_seconds', 300)
        self._tick_interval = 1.0 / self._tick_rate
        
        # State
        self._is_running = False
        self._is_paused = False
        self._stats = MarketStats()
        self._start_time: Optional[datetime] = None
        
        # Event queue for high-throughput event processing
        self._event_queue: asyncio.Queue = None
        self._price_update_callbacks: List[Callable] = []
        self._event_callbacks: List[Callable] = []
        
        # Thread pool for CPU-intensive calculations
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    @property
    def asset_manager(self) -> AssetManager:
        return self._asset_manager

    @property
    def event_system(self) -> EventSystem:
        return self._event_system

    @property
    def stats(self) -> MarketStats:
        return self._stats

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def initialize(self):
        """Initialize all market components."""
        # Initialize assets
        await self._asset_manager.initialize()
        
        # Initialize event system
        self._event_system = EventSystem(self._config, self._asset_manager, self._logger)
        await self._event_system.initialize()
        
        # Set up event queue
        self._event_queue = asyncio.Queue(maxsize=10000)
        
        # Register internal event handlers
        self._event_system.register_callback(self._on_market_event)
        
        # Log market initialization
        if hasattr(self._logger, 'log_market_event'):
            self._logger.log_market_event(
                event_name="Market Initialized",
                affected_symbols=self._asset_manager.get_symbols(),
                impact="initialization",
                sentiment_score=0.0
            )

    async def start(self):
        """Start the market simulation."""
        if self._is_running:
            return
        
        self._is_running = True
        self._is_paused = False
        self._start_time = datetime.now()
        self._stats = MarketStats(start_time=self._start_time)
        
        # Start main simulation loop
        await self._run_simulation()

    async def stop(self):
        """Stop the market simulation gracefully."""
        self._is_running = False
        
        # Allow pending tasks to complete
        await asyncio.sleep(0.1)
        
        # Shutdown thread pool
        self._executor.shutdown(wait=True)

    def pause(self):
        """Pause price updates."""
        self._is_paused = True

    def resume(self):
        """Resume price updates."""
        self._is_paused = False

    async def _run_simulation(self):
        """Main simulation loop."""
        end_time = self._start_time.timestamp() + self._duration
        
        while self._is_running:
            loop_start = time.time()
            
            # Check if simulation duration exceeded
            if time.time() >= end_time:
                self._is_running = False
                break
            
            if not self._is_paused:
                # Run tick tasks concurrently
                await asyncio.gather(
                    self._tick_prices(),
                    self._tick_events(),
                    self._process_event_queue()
                )
                
                # Update stats
                self._stats.tick_count += 1
                self._stats.last_update = datetime.now()
            
            # Calculate sleep time to maintain tick rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, self._tick_interval - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def _tick_prices(self):
        """Update all asset prices."""
        async with self._lock:
            updates = await self._asset_manager.update_prices(self._tick_interval)
            
            # Update stats
            market_stats = self._asset_manager.get_market_stats()
            self._stats.total_volume = market_stats.get('total_volume', 0)
            self._stats.avg_volatility = market_stats.get('avg_volatility', 0)
            self._stats.advancing = market_stats.get('advancing', 0)
            self._stats.declining = market_stats.get('declining', 0)
            self._stats.halted = market_stats.get('halted', 0)
            
            # Log price updates (sampling to avoid log spam)
            if self._stats.tick_count % 10 == 0:
                for symbol, price in updates.items():
                    asset = self._asset_manager.get_asset(symbol)
                    if asset and len(asset.price_history) >= 2:
                        old_price = asset.price_history[-2].price
                        self._logger.log_price_update(symbol, old_price, price, asset.volume)
            
            # Notify callbacks
            for callback in self._price_update_callbacks:
                try:
                    await callback(updates) if asyncio.iscoroutinefunction(callback) else callback(updates)
                except Exception as e:
                    self._logger.log_error("callback_error", str(e))

    async def _tick_events(self):
        """Generate and process market events."""
        events = await self._event_system.generate_events()
        self._stats.events_processed += len(events)
        
        # Add events to queue for processing
        for event in events:
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                # Queue full, skip event (shouldn't happen with proper sizing)
                pass

    async def _process_event_queue(self):
        """Process events from the queue."""
        processed = 0
        max_per_tick = 100  # Limit events per tick to prevent blocking
        
        while processed < max_per_tick:
            try:
                event = self._event_queue.get_nowait()
                await self._handle_event(event)
                processed += 1
            except asyncio.QueueEmpty:
                break

    async def _handle_event(self, event: MarketEvent):
        """Handle a single market event."""
        # Notify registered callbacks
        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                self._logger.log_error("event_callback_error", str(e))

    def _on_market_event(self, event: MarketEvent):
        """Internal handler for market events."""
        # Update market sentiment based on events
        sentiment_impact = event.sentiment.value * event.impact_magnitude
        self._stats.market_sentiment = (
            self._stats.market_sentiment * 0.9 + sentiment_impact * 0.1
        )

    def register_price_callback(self, callback: Callable):
        """Register callback for price updates."""
        self._price_update_callbacks.append(callback)

    def register_event_callback(self, callback: Callable):
        """Register callback for market events."""
        self._event_callbacks.append(callback)

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        asset = self._asset_manager.get_asset(symbol)
        return asset.price if asset else None

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get full quote for a symbol."""
        asset = self._asset_manager.get_asset(symbol)
        if not asset:
            return None
        return {
            'symbol': symbol,
            'price': asset.price,
            'bid': asset.bid,
            'ask': asset.ask,
            'volume': asset.volume,
            'change': asset.get_daily_change()[0],
            'change_pct': asset.get_daily_change()[1]
        }

    def get_all_quotes(self) -> Dict[str, Dict]:
        """Get quotes for all assets."""
        return {
            symbol: self.get_quote(symbol)
            for symbol in self._asset_manager.get_symbols()
        }

    def get_market_summary(self) -> Dict:
        """Get comprehensive market summary."""
        elapsed = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return {
            'status': 'running' if self._is_running else 'stopped',
            'paused': self._is_paused,
            'tick_count': self._stats.tick_count,
            'elapsed_seconds': elapsed,
            'tick_rate': self._tick_rate,
            'total_assets': len(self._asset_manager.get_symbols()),
            'total_volume': self._stats.total_volume,
            'events_processed': self._stats.events_processed,
            'avg_volatility': self._stats.avg_volatility,
            'market_sentiment': self._stats.market_sentiment,
            'advancing': self._stats.advancing,
            'declining': self._stats.declining,
            'halted': self._stats.halted,
            'active_events': len(self._event_system.get_active_events()) if self._event_system else 0
        }

    async def run_stress_test(self, num_events: int = 10000) -> Dict:
        """
        Run stress test with high volume of concurrent events.
        
        Tests system capability to handle 10,000+ concurrent events.
        """
        start_time = time.time()
        tasks = []
        
        # Generate many events concurrently
        for i in range(num_events):
            symbol = self._asset_manager.get_symbols()[i % len(self._asset_manager.get_symbols())]
            tasks.append(
                self._event_system.trigger_event(
                    event_type=self._event_system._event_generator.generate_company_event().event_type,
                    symbol=symbol,
                    sentiment=self._event_system._event_generator.generate_company_event().sentiment,
                    magnitude=0.1
                )
            )
        
        # Execute all events concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        events_per_second = num_events / elapsed if elapsed > 0 else 0
        
        return {
            'total_events': num_events,
            'elapsed_seconds': elapsed,
            'events_per_second': events_per_second,
            'success': events_per_second > 1000
        }


class MarketSimulator:
    """
    High-level simulator interface.
    
    Provides simple API for running simulations.
    """

    def __init__(self, config_path: str = "config.yaml"):
        import yaml
        
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        # Import logger here to avoid circular imports
        from utils.logger import AuditLogger
        self._logger = AuditLogger(self._config)
        
        self._engine: Optional[MarketEngine] = None
        self._is_initialized = False

    async def setup(self):
        """Set up the simulator."""
        self._engine = MarketEngine(self._config, self._logger)
        await self._engine.initialize()
        self._is_initialized = True

    async def run(self, duration: Optional[int] = None):
        """Run the simulation."""
        if not self._is_initialized:
            await self.setup()
        
        if duration:
            self._engine._duration = duration
        
        await self._engine.start()

    async def stop(self):
        """Stop the simulation."""
        if self._engine:
            await self._engine.stop()

    @property
    def engine(self) -> MarketEngine:
        return self._engine

    @property
    def config(self) -> Dict:
        return self._config

