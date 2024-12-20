import dataclasses
import html
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

EPS = 1e-6


@dataclasses.dataclass
class Asset(object):
    symbol: str
    exp_ret: float
    std_dev: float


class Portfolio(object):
    def __init__(
        self,
        weight_map: Dict,
        exp_ret: Optional[np.ndarray] = None,
        cov: Optional[np.ndarray] = None,
        risk_free_asset: Optional[Asset] = None,
        num_days_per_year: float = 250.0,
        min_weight: float = 0.001,
    ):
        assert abs(sum(weight_map.values()) - 1.0) < EPS
        self.weight_map = weight_map
        self.exp_ret = exp_ret
        self.cov = cov
        self.risk_free_asset = risk_free_asset
        self.num_days_per_year = num_days_per_year
        self.min_weight = min_weight

    @classmethod
    def from_string(cls, s: str) -> Tuple["Portfolio", str]:
        weight_map: Dict[str, float] = {}
        err = ""
        for line in s.strip().split("|"):
            if line:
                etf, weight = line.split(":")
                if etf in weight_map:
                    err = f"Duplicate ETF weights for: {etf}. Using the sum."
                    weight_map[etf] += float(weight)
                else:
                    weight_map[etf] = float(weight)
        sum_weights = sum(weight_map.values())
        if abs(sum_weights - 1.0) > EPS:
            factor = 1.0 / sum_weights
            err = (
                f"The sum of weights provided is not 1.0: {sum_weights:.2f}.\n"
                f"Normalizing the weights by a factor of {factor:.2f}."
            )
            weight_map = {k: v * factor for k, v in weight_map.items()}
        return cls(weight_map), err

    def to_string(self) -> str:
        return "|".join(
            [f"{k}:{v}" for k, v in self.weight_map.items() if v > self.min_weight]
        )

    def get_corr_html(self) -> str:
        html_text = ""
        if self.cov is not None:
            html_text += "<h2>Correlation of Portfolio Components</h2>\n"
            html_text += "<table class='table-metrics'><tr><th></th>\n"
            for etf, weight in self.weight_map.items():
                if weight > self.min_weight:
                    html_text += f"<th>{etf}</th>\n"
            html_text += "</tr>"
            for idx, (etf1, w1) in enumerate(self.weight_map.items()):
                if w1 >= self.min_weight:
                    html_text += f"<tr><th>{etf1}</th>\n"
                    for idy, (_, w2) in enumerate(self.weight_map.items()):
                        if w2 >= self.min_weight:
                            sigma = self.cov[idx, idy] / np.sqrt(
                                self.cov[idx, idx] * self.cov[idy, idy],
                            )
                            html_text += f"<td>{sigma:.2f}</td>\n"
                    html_text += "</tr>\n"
            html_text += "</table>\n"
        return html_text

    def get_pnl_sharpe_html(self, portfolio_return, portfolio_variance) -> str:
        html_text = "<h2>Portfolio Metrics</h2>\n"
        html_text += "<table  class='table-metrics'>"
        html_text += f"<tr><td>Return</td><td>{portfolio_return:.2f}%</td></tr>\n"
        html_text += f"<tr><td>Variance</td><td>{portfolio_variance:.2f}%</td></tr>\n"
        portfolio_volatility = np.sqrt(portfolio_variance)
        html_text += (
            f"<tr><td>Volatility</td><td>{portfolio_volatility:.2f}%</td></tr>\n"
        )
        if self.risk_free_asset is not None:
            sharpe_ratio = (
                portfolio_return - self.risk_free_asset.exp_ret
            ) / portfolio_volatility
            html_text += "<tr><td>Risk-free Asset</td>"
            html_text += f"<td>{self.risk_free_asset.symbol}%</td></tr>\n"
            html_text += "<tr><td>Risk-free Rate</td>"
            html_text += f"<td>{self.risk_free_asset.exp_ret:.2f}%</td></tr>\n"
            html_text += "<tr><td>Sharpe Ratio</td>"
            html_text += f"<td>{sharpe_ratio:.2f}</td></tr>\n"
        html_text += "</table>\n"
        return html_text

    def to_html(self) -> str:
        html_text = "<div class='output'>\n"
        html_text += "<h2>Portfolio Components</h2>\n"
        html_text += "<p>Components are sorted in order of traded volume</p>\n"
        w = np.array(list(self.weight_map.values()))
        portfolio_return = None
        portfolio_variance = None
        sum_weights: float = 0.0
        if self.exp_ret is None or self.cov is None:
            html_text += "<table class='table-metrics'>"
            html_text += "<tr><th>Component</th><th>Weight</th></tr>\n"
            for etf, weight in self.weight_map.items():
                if weight > self.min_weight:
                    html_text += f"<tr><td>{etf}</td><td>{weight:.2%}</td></tr>\n"
                    sum_weights += weight
        else:
            portfolio_return = np.dot(w, self.exp_ret) * self.num_days_per_year
            portfolio_variance = (
                np.dot(w.T, np.dot(self.cov, w)) * self.num_days_per_year
            )
            component_contributions = w * np.dot(self.cov, w) * self.num_days_per_year
            html_text += "<table class='table-metrics'>"
            html_text += "<tr><th>Component</th><th>Weight</th>\n"
            html_text += "<th>Return</th><th>Volatility</th>"
            html_text += "<th>Contribution to Return</th>"
            html_text += "<th>Contribution to Variance</th>"
            html_text += "</tr>\n"
            sum_mcr: float = 0.0
            sum_mcv: float = 0.0
            for idx, ((etf, weight), mcv) in enumerate(
                zip(self.weight_map.items(), component_contributions)
            ):
                if weight > self.min_weight:
                    html_text += f"<tr><td>{etf}</td><td>{weight:.2%}</td>\n"
                    html_text += (
                        f"<td>{self.exp_ret[idx] * self.num_days_per_year:.2f}%</td>\n"
                    )
                    sigma = np.sqrt(self.cov[idx, idx] * self.num_days_per_year)
                    html_text += f"<td>{sigma:.2f}%</td>\n"
                    mcr = weight * self.exp_ret[idx] * self.num_days_per_year
                    html_text += f"<td>{mcr:.2f}%</td><td>{mcv:.2f}%</td></tr>\n"
                    sum_mcr += mcr
                    sum_mcv += mcv
                    sum_weights += weight
            html_text += f"<tr><th>Portfolio</th><th>{sum_weights:.2%}</th>"
            html_text += "<th></th><th></th>"
            html_text += f"<th>{sum_mcr:.2f}%</th><th>{sum_mcv:.2f}%</th></tr>\n"
        html_text += "</table>"
        if abs(sum_weights - 1.0) > 0.01:
            html_text += f"<p>Sum of weights is not 1.0: {sum_weights:.2%}</p>\n"
            html_text += "<p>It is likely due to dropping of too many components"
            html_text += f" with low weights (less than {self.min_weight:.2%}).</p>\n"
        html_text += self.get_corr_html()
        if (self.exp_ret is not None) and (self.cov is not None):
            html_text += self.get_pnl_sharpe_html(portfolio_return, portfolio_variance)

        # actions
        portfolio_str = html.escape(self.to_string())
        start_date = (pd.Timestamp.now("UTC") - pd.Timedelta(days=2000)).strftime(
            "%Y-%m-%d"
        )
        end_date = (pd.Timestamp.now("UTC") - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        plot_link = f"/plot.html?portfolio={portfolio_str}"
        plot_link += f"&start_date={start_date}"
        plot_link += f"&end_date={end_date}"
        plot_link += "&sip_amount=500"
        plot_link += "&sip_frequency_days=15"
        html_text += "<div class='form-container'>"
        new_tab = "target='_blank' rel='noopener noreferrer'"
        html_text += (
            f"<a href='{plot_link}' {new_tab}><button>Plot Portfolio</button></a>"
        )
        html_text += f"<a href='/' {new_tab}><button>Run Optimizer Again</button></a>"
        html_text += "</div>\n"
        return html_text
