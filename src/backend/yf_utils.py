import time
import numpy as np
import pandas as pd
import yfinance as yf


class YFError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        class_name = self.__class__.__name__
        return f"{class_name}: {self.message}"


class YFDownloadError(YFError):
    pass


class YFDataQualityError(YFError):
    pass


class YFReturnsCache(object):
    def __init__(
        self,
        start_date,
        end_date,
        ticker_list,
        impute_prices=True,
        return_column="Adj Close",
        num_retries=3,
        chunk_size=25,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.ticker_list = ticker_list
        self.impute_prices = impute_prices
        self.return_column = return_column
        self.num_retries = num_retries
        self.chunk_size = chunk_size
        self.data = {}
        self.retry_count = {}

    def fetch_price_data(self):
        tickers = [
            x
            for x in self.ticker_list
            if (x not in self.data) and (self.retry_count.get(x, 0) <= self.num_retries)
        ][: self.chunk_size]
        if not tickers:
            return
        price_df = yf.download(tickers, start=self.start_date, end=self.end_date)
        if (
            (price_df is None)
            or not isinstance(price_df, pd.DataFrame)
            or price_df.empty
        ):
            raise YFDownloadError(
                "Failed to download price data for tickers: %s" % tickers
            )
        if self.impute_prices:
            price_df = price_df.ffill()
        for tickr in tickers:
            if (self.return_column, tickr) in price_df.columns:
                return_series = (
                    price_df[(self.return_column, tickr)].apply(np.log).diff() * 100
                )
                self.data[tickr] = return_series
            else:
                self.retry_count[tickr] = self.retry_count.get(tickr, 0) + 1

    def get_return_series(self, tickr, max_return=50):
        if tickr not in self.data:
            for _ in range(self.num_retries):
                self.fetch_price_data()
                if tickr in self.data:
                    break
                else:
                    time.sleep(30)
        return_series = self.data[tickr]
        if return_series.abs().max() > max_return:
            raise YFDataQualityError(
                f"{tickr} has at least one daily return > {max_return} in magnitude"
            )
        return return_series
