from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from cache import CACHE_DIR, ETF_VOLUME_CACHE_CSV, ETF_VOLUME_CACHE_HEADER, Cache


class ETFVolumeCache(Cache):

    cache_version = 1

    def __init__(self, etf_list):
        self.etf_list = etf_list

    def prune(self, cutoff_time, logger=None):
        if ETF_VOLUME_CACHE_CSV.exists():
            volume_df = pd.read_csv(ETF_VOLUME_CACHE_CSV)
            assert set(volume_df.columns) == set(ETF_VOLUME_CACHE_HEADER)
            assert volume_df["symbol"].duplicated().sum() == 0
            volume_df["entry_time"] = pd.to_datetime(volume_df["entry_time"])
            volume_df = volume_df[volume_df["entry_time"] > cutoff_time]
            volume_df.to_csv(ETF_VOLUME_CACHE_CSV, index=False)
            logger.info(
                f"Pruned volume cache to {ETF_VOLUME_CACHE_CSV}: {volume_df.shape}"
            )
            return volume_df.shape[0]
        else:
            return 0

    def populate(self, max_new_entries=100, logger=None):
        assert CACHE_DIR.exists(), f"{CACHE_DIR} does not exist"
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
                            "entry_time": datetime.now(timezone.utc),
                        }
                    )
                except yf.exceptions.YFTickerMissingError:
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
                            "entry_time": datetime.now(timezone.utc),
                        }
                    )
                except Exception as e:  # pylint: disable=broad-except
                    logger.error("Error for %s: %s", etf, e)
            if len(volume_list) > max_new_entries:
                break
        if len(volume_list) > 0:
            additional_volume_df = pd.DataFrame(volume_list)
            assert set(additional_volume_df.columns) == set(ETF_VOLUME_CACHE_HEADER)
            if volume_df is None:
                volume_df = additional_volume_df
            else:
                volume_df = pd.concat([volume_df, additional_volume_df])
            volume_df.to_csv(ETF_VOLUME_CACHE_CSV, index=False)
            logger.info(f"Saved volume cache to {ETF_VOLUME_CACHE_CSV}")
        return len(volume_list)

    def as_dataframe(self):
        return pd.read_csv(ETF_VOLUME_CACHE_CSV)
