from pathlib import Path

CACHE_DIR = Path.cwd() / "cache"
ETF_VOLUME_CACHE_CSV = CACHE_DIR / "etf_volume_cache.csv"
ETF_VOLUME_CACHE_HEADER = [
    "symbol",
    "exchange",
    "volume",
    "price",
    "currency",
    "entry_time",
]


class Cache(object):

    cache_version = 1

    def prune(self, cutoff_time, logger=None):
        raise NotImplementedError

    def populate(self, max_new_entries, logger=None):
        raise NotImplementedError
