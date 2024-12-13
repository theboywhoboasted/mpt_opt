from typing import List, Optional

import numpy as np
import pandas as pd
from pyetfdb_scraper.etf import load_etfs

import web.optimizer
from backend.yf_utils import YFError, get_yf_return_series
from cache.etf_volume import ETFVolumeCache
from opt import calc_eff_front, find_min_var_portfolio
from portfolio import Portfolio


class ETFOptimizer:

    def __init__(
        self,
        currency: str,
        num_contracts: int,
        correlation_cutoff: float,
        num_years: float,
    ):
        self.currency = currency
        self.num_contracts = num_contracts
        self.correlation_cutoff = correlation_cutoff
        self.num_years = num_years
        self.contract_list: Optional[List[str]] = None
        self.now = pd.Timestamp.now("UTC")
        self.cache_cutoff_time = self.now - pd.Timedelta(days=7)
        self.start_date = (
            self.now - pd.Timedelta(days=int(365 * self.num_years))
        ).strftime("%Y-%m-%d")
        self.end_date = self.now.strftime("%Y-%m-%d")
        self.portfolio: Optional[Portfolio] = None
        self.returns_df: Optional[pd.DataFrame] = None
        self.etf_volume_cache: Optional[ETFVolumeCache] = None

    def set_contract_list(self, logger):
        assert self.etf_volume_cache is not None
        df = self.etf_volume_cache.as_dataframe()
        df = df[
            pd.notnull(df["volume"])
            & pd.notnull(df["price"])
            & pd.notnull(df["currency"])
            & (df["volume"] > 0)
            & (df["price"] > 0)
            & (df["currency"] == self.currency)
        ]
        df["notional"] = df["volume"] * df["price"]
        df = df.sort_values("notional", ascending=False)
        self.contract_list = list(df["symbol"].values)
        assert self.contract_list is not None
        logger.info(f"Using {len(self.contract_list)} ETFs in {self.currency}")

    def set_top_etf_return_df(self, logger):
        returns_df = None
        assert self.contract_list is not None
        for etf in self.contract_list:
            try:
                return_series = get_yf_return_series(
                    etf,
                    self.start_date,
                    self.end_date,
                    max_return=50,
                )
            except YFError as e:
                logger.info(f"Error getting return series for {etf}: {e}")
                continue
            if returns_df is None:
                returns_df = pd.DataFrame(index=return_series.index)
            else:
                old_index = returns_df.index
                new_index = return_series.index
                combined_index = sorted(old_index.union(new_index))
                if len(combined_index) > len(old_index):
                    returns_df = returns_df.reindex(combined_index)
            if return_series.notnull().sum() < 0.8 * len(return_series):
                logger.info(f"{etf} has too many missing values")
                continue
            returns_df[etf] = return_series
            for col in returns_df:
                if col != etf:
                    corr = returns_df[etf].corr(returns_df[col])
                    if corr > self.correlation_cutoff:
                        logger.info(f"{etf} and {col} have high correlation: {corr}")
                        avg_return = returns_df[[etf, col]].mean().sort_values()
                        lower_return_col, higher_return_col = (
                            avg_return.index[0],
                            avg_return.index[1],
                        )
                        logger.info(
                            f"Removing {lower_return_col} in favour of "
                            f"{higher_return_col} from returns_df due to lower return",
                        )
                        returns_df = returns_df.drop(columns=[lower_return_col])
                        break
            if len(returns_df.columns) >= self.num_contracts:
                break
        assert returns_df is not None
        returns_df = returns_df.dropna(axis=0, how="all")
        self.returns_df = returns_df

    def run_optimizer(self, task_id: str, logger):
        def write_to_log(msg: str):
            log_text = web.optimizer.TaskDB.get("log", task_id)
            assert log_text is not None
            ts = pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M:%S")
            new_msg = f"{log_text.rstrip()}\n{ts}: {msg}"
            web.optimizer.TaskDB.put("log", task_id, new_msg)

        write_to_log("Starting optimizer")
        ETFVolumeCache.process_cache(logger, days_to_prune_after=7, chunk_size=100)
        write_to_log("Updated ETF metadata cache")
        etf_list = load_etfs()
        self.etf_volume_cache = ETFVolumeCache(etf_list)
        self.set_contract_list(logger)
        self.set_top_etf_return_df(logger)
        write_to_log("ETF data from Yahoo Finance loaded")
        assert self.returns_df is not None
        logger.info(
            f"Using the following ETFs for optimization: {self.returns_df.columns}",
        )
        mean_returns = self.returns_df.mean().to_numpy()
        assert np.isfinite(mean_returns).all()
        covar_matrix = self.returns_df.cov().to_numpy()
        assert np.isfinite(covar_matrix).all()
        individual_volatility = np.sqrt(np.diag(covar_matrix))
        num_days_per_year = len(self.returns_df) / self.num_years

        efficient_frontier = calc_eff_front(mean_returns, covar_matrix, logger)
        write_to_log("Calculated efficient frontier")
        zero_vol = sorted(
            zip(individual_volatility, mean_returns, self.returns_df.columns),
            key=lambda x: x[0],
        )[0]
        risk_free_rate = zero_vol[1]
        annualized_risk_free_rate = zero_vol[1] * num_days_per_year
        annualized_min_volatility = zero_vol[0] * np.sqrt(num_days_per_year)
        logger.info(
            f"Using {annualized_risk_free_rate:.2f}% as the annualized risk-free "
            f"rate (sigma: {annualized_min_volatility:.2f}%, sym: {zero_vol[2]})",
        )
        best_output = sorted(
            zip(efficient_frontier["rets"], efficient_frontier["vols"]),
            key=lambda x: (x[0] - risk_free_rate) / x[1],
            reverse=True,
        )[0]
        weights, mu, sigma = find_min_var_portfolio(
            mean_returns,
            covar_matrix,
            r_min=best_output[0] * 0.99,
        )
        logger.info(f"Best Portfolio: mu: {mu:.2f}%, sigma: {sigma:.2f}%")

        weight_map = zip(self.returns_df.columns, weights)
        self.portfolio = Portfolio(
            weight_map=dict(weight_map),
            exp_ret=mean_returns,
            cov=covar_matrix,
            risk_free_rate=annualized_risk_free_rate,
            num_days_per_year=num_days_per_year,
        )
        logger.info(f"Mean returns: {mean_returns}")
        logger.info(f"Num days per year: {num_days_per_year}")
        write_to_log("Finished optimization")
