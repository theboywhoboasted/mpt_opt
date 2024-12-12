import pandas as pd
from pyetfdb_scraper.etf import load_etfs

from cache.etf_volume import ETFVolumeCache


def populate_all_caches(logger):
    # ETF Volume cache
    etf_list = load_etfs()
    etf_volume_cache = ETFVolumeCache(etf_list)
    cache_cutoff_time = pd.Timestamp.now("UTC") - pd.Timedelta(days=7)
    cache_len = etf_volume_cache.prune(cache_cutoff_time, logger)
    logger.info(f"Pruned ETF Volume cache has {cache_len} entries")
    chunk_size = 50
    added_entries = chunk_size
    while added_entries >= chunk_size:
        added_entries = etf_volume_cache.populate(chunk_size, logger)
        logger.info(f"Populated ETF Volume cache with {added_entries} new entries")
    logger.info(f"Populated ETF Volume cache with {added_entries} new entries")
