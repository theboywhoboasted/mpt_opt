import time

import pandas as pd
import yfinance as yf
from filelock import FileLock, Timeout
from pyetfdb_scraper.etf import load_etfs
from yfinance.exceptions import YFTickerMissingError

from cache import CACHE_DIR, ETF_VOLUME_CACHE_CSV, ETF_VOLUME_CACHE_HEADER, Cache


class ETFVolumeCache(Cache):

    cache_version = 1

    def __init__(self, etf_list):
        self.etf_list = etf_list

    def prune(self, cutoff_time, logger) -> int:
        if ETF_VOLUME_CACHE_CSV.exists():
            lock = FileLock(str(ETF_VOLUME_CACHE_CSV) + ".lock")
            with lock.acquire(timeout=20):
                volume_df = pd.read_csv(ETF_VOLUME_CACHE_CSV)
                assert set(volume_df.columns) == set(ETF_VOLUME_CACHE_HEADER)
                assert volume_df["symbol"].duplicated().sum() == 0
                volume_df["entry_time"] = pd.to_datetime(volume_df["entry_time"])
                regular_cutoff = volume_df.notnull().all(axis=1) & (
                    volume_df["entry_time"] > cutoff_time
                )
                empty_cutoff_time = pd.Timestamp.now("UTC") - pd.Timedelta(hours=6)
                empty_cutoff = volume_df.isna().any(  # pylint: disable=no-member
                    axis=1
                ) & (volume_df["entry_time"] > empty_cutoff_time)
                volume_df = volume_df[regular_cutoff | empty_cutoff]
                volume_df.to_csv(ETF_VOLUME_CACHE_CSV, index=False)
                logger.info(
                    f"Pruned volume cache to {ETF_VOLUME_CACHE_CSV}: {volume_df.shape}"
                )
                return volume_df.shape[0]
        else:
            return 0

    def _populate(self, max_new_entries, logger) -> int:
        if ETF_VOLUME_CACHE_CSV.exists():
            volume_df = pd.read_csv(ETF_VOLUME_CACHE_CSV)
            logger.info(
                f"Loading volume cache from {ETF_VOLUME_CACHE_CSV}: {volume_df.shape}"
            )
        else:
            volume_df = None
        volume_list = []
        for etf in self.etf_list:
            if (volume_df is None) or (etf not in volume_df["symbol"].values):
                logger.info("Fetching volume for %s", etf)
                try:
                    info = yf.Ticker(etf).fast_info
                    assert info["quoteType"] in [
                        "ETF"
                    ], f"{etf} is not an ETF but {info['quoteType']}"
                    volume_list.append(
                        {
                            "symbol": etf,
                            "exchange": info["exchange"],
                            "volume": info["three_month_average_volume"],
                            "price": info["fifty_day_average"],
                            "currency": info["currency"],
                            "entry_time": pd.Timestamp.now("UTC"),
                        }
                    )
                except YFTickerMissingError:
                    info = yf.Ticker(etf).info
                    assert info["quoteType"] in [
                        "ETF"
                    ], f"{etf} is not an ETF but {info['quoteType']}"
                    volume_list.append(
                        {
                            "symbol": etf,
                            "exchange": info["exchange"],
                            "volume": info["three_month_average_volume"],
                            "price": info["fifty_day_average"],
                            "currency": info["currency"],
                            "entry_time": pd.Timestamp.now("UTC"),
                        }
                    )
                except Exception as e:  # pylint: disable=broad-except
                    logger.error("Error for %s: %s", etf, e)
                    volume_list.append(
                        {
                            "symbol": etf,
                            "exchange": None,
                            "volume": None,
                            "price": None,
                            "currency": None,
                            "entry_time": pd.Timestamp.now("UTC"),
                        }
                    )
            if len(volume_list) > max_new_entries:
                break
        if len(volume_list) > 0:
            additional_volume_df = pd.DataFrame(volume_list)
            assert set(additional_volume_df.columns) == set(ETF_VOLUME_CACHE_HEADER)
            if (volume_df is None) or (volume_df.empty):  # pylint: disable=no-member
                volume_df = additional_volume_df
            else:
                volume_df = pd.concat([volume_df, additional_volume_df])
            volume_df.to_csv(ETF_VOLUME_CACHE_CSV, index=False)
            logger.info(f"Saved volume cache to {ETF_VOLUME_CACHE_CSV}")
        return len(volume_list)

    def populate(self, max_new_entries=100, logger=None) -> int:
        assert CACHE_DIR.exists(), f"{CACHE_DIR} does not exist"
        lock = FileLock(str(ETF_VOLUME_CACHE_CSV) + ".lock")
        with lock.acquire(timeout=20):
            return self._populate(max_new_entries, logger)

    def as_dataframe(self) -> pd.DataFrame:
        return pd.read_csv(ETF_VOLUME_CACHE_CSV)

    @classmethod
    def process_cache(
        cls, logger, days_to_prune_after=7, chunk_size=100, num_retries=3
    ) -> None:
        etf_list = load_etfs()
        etf_volume_cache = ETFVolumeCache(etf_list)
        cache_cutoff_time = pd.Timestamp.now("UTC") - pd.Timedelta(
            days=days_to_prune_after
        )

        # prune the cache
        for _ in range(num_retries):
            try:
                cache_len = etf_volume_cache.prune(cache_cutoff_time, logger)
                logger.info(f"Pruned ETF Volume cache has {cache_len} entries")
                break
            except Timeout:
                logger.info("Another process is pruning the cache, waiting...")
                time.sleep(10)

        # populate the cache
        tries_left = num_retries
        while tries_left > 0:
            # at each iteration, either populate the cache with chunk_size entries
            # or reduce the number of retries left by 1
            # hence the loop will run at most k times where k is
            # tnum_retries + universe_length/chunk_size
            try:
                added_entries = etf_volume_cache.populate(chunk_size, logger)
                logger.info(
                    f"Populated ETF Volume cache with {added_entries} new entries"
                )
                if added_entries < chunk_size:
                    break
            except Timeout:
                logger.info("Another process is populating the cache, waiting...")
                time.sleep(10)
                tries_left -= 1
