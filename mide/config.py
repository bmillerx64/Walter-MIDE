from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    min_price: float = 0.05
    max_price: float = 50.00
    max_free_float: int = 50_000_000
    include_etfs: bool = False
    min_pct_change: float = 3.0
    min_day_volume: int = 100_000
    min_dollar_volume: float = 100_000.0
    max_spread_pct: float = 6.0
    monitor_score: float = 58.0
    watch_score: float = 76.0
    critical_score: float = 88.0
    refresh_seconds: int = 60
    feed: str = "iex"
    batch_size: int = 150
    max_seed_symbols: int = 350

    @classmethod
    def from_mapping(cls, mapping=None):
        mapping = mapping or {}
        defaults = cls()

        def get(name, default):
            return mapping.get(name, os.getenv(name, default))

        return cls(
            min_price=float(get("MIN_PRICE", defaults.min_price)),
            max_price=float(get("MAX_PRICE", defaults.max_price)),
            max_free_float=int(get("MAX_FREE_FLOAT", defaults.max_free_float)),
            include_etfs=str(get("INCLUDE_ETFS", "false")).lower() in {"1", "true", "yes"},
            refresh_seconds=int(get("SCAN_REFRESH_SECONDS", defaults.refresh_seconds)),
            feed=str(get("ALPACA_FEED", defaults.feed)).lower(),
        )
