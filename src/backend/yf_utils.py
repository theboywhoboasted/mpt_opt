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


def get_yf_return_series(
    tickr: str,
    start_date: str,
    end_date: str,
    max_return: int = 50,
    impute_prices: bool = True,
    return_column: str = "Adj Close",
    num_retries: int = 3,
) -> pd.Series:
    for _ in range(num_retries):
        price_df = yf.download(tickr, start=start_date, end=end_date)
        if (
            (price_df is not None)
            and isinstance(price_df, pd.DataFrame)
            and not (price_df.empty)
            and (return_column, tickr) in price_df.columns
        ):
            if impute_prices:
                price_df = price_df.ffill()
            return_series = price_df[(return_column, tickr)].apply(np.log).diff() * 100
            if return_series.abs().max() > max_return:
                raise YFDataQualityError(
                    f"Ticker {tickr} has at least one daily return"
                    f" > {max_return} in magnitude"
                )
            return return_series
    raise YFDownloadError(
        f"Failed to get return series for {tickr} even after {num_retries} retries"
    )
