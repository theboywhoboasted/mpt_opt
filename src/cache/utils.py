from cache.etf_volume import ETFVolumeCache


def populate_all_caches(logger):
    # ETF Volume cache
    ETFVolumeCache.process_cache(logger, days_to_prune_after=3, chunk_size=50)
