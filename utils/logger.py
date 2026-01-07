import logging
import hashlib
import json
import os
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class AuditEventType(Enum):
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_MODIFIED = "ORDER_MODIFIED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIAL_FILL = "ORDER_PARTIAL_FILL"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    PRICE_UPDATE = "PRICE_UPDATE"
    BOT_DECISION = "BOT_DECISION"
    MARKET_EVENT = "MARKET_EVENT"
    MARKET_HALT = "MARKET_HALT"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"


@dataclass
class AuditEntry:
    timestamp: str
    event_type: str
    event_id: str
    user_id: Optional[str]
    symbol: Optional[str]
    details: Dict[str, Any]
    previous_hash: str
    entry_hash: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(',', ':'))


class HashChainHandler(RotatingFileHandler):
    # each log entry links to previous via hash - makes tampering detectable

    def __init__(self, filename: str, maxBytes: int = 10485760, 
                 backupCount: int = 5, encoding: str = 'utf-8'):
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)
        self._previous_hash = self._get_genesis_hash()
        self._lock = threading.Lock()
        self._entry_count = 0

    def _get_genesis_hash(self) -> str:
        genesis = f"GENESIS:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(genesis.encode()).hexdigest()[:16]

    def _compute_hash(self, message: str, previous_hash: str) -> str:
        content = f"{previous_hash}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def emit(self, record: logging.LogRecord):
        with self._lock:
            if hasattr(record, 'audit_entry'):
                entry_hash = self._compute_hash(record.getMessage(), self._previous_hash)
                record.msg = f"[HASH:{entry_hash}|PREV:{self._previous_hash}] {record.msg}"
                self._previous_hash = entry_hash
                self._entry_count += 1
            super().emit(record)


class AuditLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[Dict] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[Dict] = None):
        if self._initialized:
            return
        
        self._config = config or {}
        self._setup_loggers()
        self._event_counter = 0
        self._counter_lock = threading.Lock()
        self._previous_hash = "GENESIS"
        self._metrics = {
            'orders_logged': 0,
            'trades_logged': 0,
            'price_updates': 0,
            'errors_logged': 0
        }
        self._initialized = True

    def _setup_loggers(self):
        log_config = self._config.get('logging', {})
        log_file = log_config.get('audit_file', 'logs/audit.log')
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        max_bytes = log_config.get('max_file_size', 10485760)
        backup_count = log_config.get('backup_count', 5)

        self._audit_logger = logging.getLogger('stock_sim.audit')
        self._audit_logger.setLevel(log_level)
        self._audit_logger.handlers.clear()

        file_handler = HashChainHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        
        formatter = logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S.%f'
        )
        file_handler.setFormatter(formatter)
        self._audit_logger.addHandler(file_handler)

        # console for warnings+
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            '⚠️  %(asctime)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self._audit_logger.addHandler(console_handler)

    def _generate_event_id(self) -> str:
        with self._counter_lock:
            self._event_counter += 1
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
            return f"EVT-{timestamp}-{self._event_counter:08d}"

    def log_event(self, event_type: AuditEventType, user_id: Optional[str] = None,
                  symbol: Optional[str] = None, **details) -> str:
        event_id = self._generate_event_id()
        timestamp = datetime.utcnow().isoformat()

        entry = AuditEntry(
            timestamp=timestamp,
            event_type=event_type.value,
            event_id=event_id,
            user_id=user_id,
            symbol=symbol,
            details=details,
            previous_hash=self._previous_hash,
            entry_hash=""
        )

        record = self._audit_logger.makeRecord(
            'stock_sim.audit',
            logging.INFO,
            '', 0,
            entry.to_json(),
            None, None
        )
        record.audit_entry = True
        self._audit_logger.handle(record)

        self._update_metrics(event_type)
        self._previous_hash = entry.entry_hash

        return event_id

    def _update_metrics(self, event_type: AuditEventType):
        if event_type in [AuditEventType.ORDER_PLACED, AuditEventType.ORDER_CANCELLED]:
            self._metrics['orders_logged'] += 1
        elif event_type == AuditEventType.TRADE_EXECUTED:
            self._metrics['trades_logged'] += 1
        elif event_type == AuditEventType.PRICE_UPDATE:
            self._metrics['price_updates'] += 1
        elif event_type == AuditEventType.SYSTEM_ERROR:
            self._metrics['errors_logged'] += 1

    def log_order_placed(self, order_id: str, user_id: str, symbol: str,
                        side: str, order_type: str, quantity: int,
                        price: Optional[float] = None, **kwargs) -> str:
        return self.log_event(
            AuditEventType.ORDER_PLACED,
            user_id=user_id,
            symbol=symbol,
            order_id=order_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs
        )

    def log_order_cancelled(self, order_id: str, user_id: str, 
                           symbol: str, reason: str = "") -> str:
        return self.log_event(
            AuditEventType.ORDER_CANCELLED,
            user_id=user_id,
            symbol=symbol,
            order_id=order_id,
            reason=reason
        )

    def log_trade(self, trade_id: str, buyer_id: str, seller_id: str,
                  symbol: str, price: float, quantity: int,
                  buyer_order_id: str, seller_order_id: str) -> str:
        return self.log_event(
            AuditEventType.TRADE_EXECUTED,
            symbol=symbol,
            trade_id=trade_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            price=price,
            quantity=quantity,
            buyer_order_id=buyer_order_id,
            seller_order_id=seller_order_id
        )

    def log_price_update(self, symbol: str, old_price: float, 
                        new_price: float, volume: int) -> str:
        return self.log_event(
            AuditEventType.PRICE_UPDATE,
            symbol=symbol,
            old_price=old_price,
            new_price=new_price,
            change_pct=((new_price - old_price) / old_price) * 100 if old_price > 0 else 0,
            volume=volume
        )

    def log_bot_decision(self, bot_id: str, bot_type: str, symbol: str,
                        action: str, reason: str, indicators: Dict) -> str:
        return self.log_event(
            AuditEventType.BOT_DECISION,
            user_id=bot_id,
            symbol=symbol,
            bot_type=bot_type,
            action=action,
            reason=reason,
            indicators=indicators
        )

    def log_market_event(self, event_name: str, affected_symbols: list,
                        impact: str, sentiment_score: float) -> str:
        return self.log_event(
            AuditEventType.MARKET_EVENT,
            event_name=event_name,
            affected_symbols=affected_symbols,
            impact=impact,
            sentiment_score=sentiment_score
        )

    def log_error(self, error_type: str, message: str, 
                 stack_trace: Optional[str] = None) -> str:
        return self.log_event(
            AuditEventType.SYSTEM_ERROR,
            error_type=error_type,
            message=message,
            stack_trace=stack_trace
        )

    def log_validation_failure(self, user_id: str, action: str,
                              reason: str, details: Dict) -> str:
        return self.log_event(
            AuditEventType.VALIDATION_FAILURE,
            user_id=user_id,
            action=action,
            reason=reason,
            validation_details=details
        )

    def get_metrics(self) -> Dict[str, int]:
        return self._metrics.copy()

    def verify_chain_integrity(self, log_file: str = None) -> bool:
        log_file = log_file or self._config.get('logging', {}).get('audit_file', 'logs/audit.log')
        
        if not os.path.exists(log_file):
            return True
        
        previous_hash = None
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if '[HASH:' in line and '|PREV:' in line:
                        hash_start = line.find('[HASH:') + 6
                        hash_end = line.find('|PREV:')
                        prev_start = hash_end + 6
                        prev_end = line.find(']', prev_start)
                        
                        current_hash = line[hash_start:hash_end]
                        claimed_prev = line[prev_start:prev_end]
                        
                        if previous_hash and claimed_prev != previous_hash:
                            return False
                        
                        previous_hash = current_hash
            
            return True
        except Exception:
            return False


def get_logger(name: str = 'stock_sim') -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
