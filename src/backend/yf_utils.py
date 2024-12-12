import numpy as np
import pandas as pd
import yfinance as yf


class YFError(Exception):
    def __init__(self, message):
        self._message = message

    def __str__(self):
        class_name = self.__class__.__name__
        return f"{class_name}: {self._message}"


def get_yf_return_series(
    tickr: str,
    start_date: str,
    end_date: str,
    max_return: int = 50,
    impute_prices: bool = True,
    return_column: str = "Adj Close",
) -> pd.Series:
    price_df = yf.download(tickr, start=start_date, end=end_date)
    if impute_prices:
        price_df = price_df.ffill()
    return_series = np.log(price_df[(return_column, tickr)]).diff() * 100
    if return_series.abs().max() > max_return:
        raise YFError(f"Tikcer {tickr} has returns > {max_return}")
    return return_series
