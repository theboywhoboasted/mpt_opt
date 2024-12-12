import base64
from io import BytesIO
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Response, make_response, render_template

from backend.yf_utils import YFError, get_yf_return_series
from portfolio import Portfolio

MIN_INV_PCT = 10


class PlotPortfolio:

    def __init__(
        self,
        portfolio: Portfolio,
        start_date: str,
        end_date: str,
        sip_amount: float,
        sip_frequency_days: int,
        logger,
    ):
        self.portfolio = portfolio
        self.start_date = start_date
        self.end_date = end_date
        self.sip_amount = sip_amount
        self.sip_frequency_days = sip_frequency_days
        self.logger = logger

    def populate_price_returns(self):
        return_series = {}
        for tickr in self.portfolio.weight_map.keys():
            try:
                return_series[tickr] = get_yf_return_series(
                    tickr,
                    self.start_date,
                    self.end_date,
                )
                self.logger.info(f"Retrieved return series for {tickr}")
            except YFError:
                self.return_series = None
                return
        return_df = pd.DataFrame(return_series)
        return_df = return_df.fillna(0)
        portfolio_return_series = pd.Series(0, index=return_df.index)
        for tickr, weight in self.portfolio.weight_map.items():
            portfolio_return_series += return_df[tickr] * weight
        self.logger.info(f"Portfolio return series: {portfolio_return_series.shape}")
        self.return_series = portfolio_return_series

    def get_portfolio_value_series(self):
        assert self.return_series is not None
        portfolio_df = pd.DataFrame(index=self.return_series.index)
        portfolio_df["new_amount_invested"] = pd.Series(0, index=portfolio_df.index)
        portfolio_df["portfolio_value"] = pd.Series(0, index=portfolio_df.index)
        timestamp = pd.Timestamp(self.start_date + " 00:00")
        last_timestamp = pd.Timestamp(self.end_date + " 00:00")
        investment_made = False
        while timestamp <= last_timestamp:
            inv_date = min([x for x in self.return_series.index if x >= timestamp])
            self.logger.info(f"Processing date: {inv_date}")
            portfolio_df.loc[inv_date, "new_amount_invested"] = self.sip_amount
            return_series = np.where(
                portfolio_df.index <= inv_date,
                0,
                self.return_series / 100,
            )
            cum_return = return_series.cumsum()
            portfolio_df["portfolio_value"] += self.sip_amount * np.where(
                portfolio_df.index <= inv_date, 0, np.exp(cum_return)
            )
            if not investment_made:
                self.price_series = portfolio_df.copy()
                self.logger.info(
                    f"Set up price series w/o SIP: {self.price_series.shape}"
                )
                investment_made = True
            timestamp += pd.Timedelta(days=self.sip_frequency_days)
        self.price_series_sip = portfolio_df
        self.price_series["cum_amount_invested"] = self.price_series[
            "new_amount_invested"
        ].cumsum()
        self.price_series_sip["cum_amount_invested"] = self.price_series_sip[
            "new_amount_invested"
        ].cumsum()
        self.min_inv_made = (
            self.price_series_sip["cum_amount_invested"]
            > self.price_series_sip["cum_amount_invested"].max() * MIN_INV_PCT / 100
        )
        self.min_inv_made_date = self.min_inv_made[self.min_inv_made].index[0]
        self.logger.info(f"Set up price series w/ SIP: {self.price_series_sip.shape}")

    def plot(self):
        self.populate_price_returns()
        self.get_portfolio_value_series()

        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(20, 20))
        for ax, df, title in zip(
            axes,
            [self.price_series, self.price_series_sip],
            ["Portfolio Value with One-Time-Investment", "Portfolio Value with SIP"],
        ):
            ax.plot(
                df.index,
                df["portfolio_value"],
                color="blue",
                marker=".",
                label="Portfolio Value",
            )
            ax.plot(
                df.index,
                df["cum_amount_invested"],
                color="red",
                linestyle="--",
                linewidth=0.5,
                label="Cumulative Investment Made",
            )
            ax.set_title(title)
            ax.set_xlabel("Date")
            ax.set_ylabel("Value")
            ax.grid()

        sip_dates = self.price_series_sip[
            self.price_series_sip["new_amount_invested"] > 0
        ].index
        for date in sip_dates[:-1]:
            axes[1].axvline(x=date, color="green", linestyle="--", linewidth=0.5)
        # last SIP date sepaartely to attach label
        # assigning label to each date blows up the legend
        axes[1].axvline(
            x=sip_dates[-1],
            color="green",
            linestyle="--",
            linewidth=0.5,
            label="SIP Date",
        )
        axes[1].axvline(
            x=self.min_inv_made_date,
            color="red",
            linestyle="-",
            linewidth=1.0,
            label=f"{MIN_INV_PCT}% of total amount invested",
        )

        axes[0].legend()
        axes[1].legend()

        img = BytesIO()
        plt.savefig(img, format="png", bbox_inches="tight")
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()
        self.logger.info("Plotted portfolio value")
        return plot_url

    def description(self):
        html_text = '<div class="output">'
        html_text += "<h2>Portfolio Description</h2>\n"

        html_text += "<table class='table-metrics'>\n"
        html_text += f"<tr><td>Start Date</td><td>{self.start_date}</td></tr>\n"
        html_text += f"<tr><td>End Date</td><td>{self.end_date}</td></tr>\n"
        html_text += f"<tr><td>SIP Amount</td><td>${self.sip_amount}</td></tr>\n"
        html_text += (
            f"<tr><td>SIP Frequency</td><td>Every {self.sip_frequency_days} days"
        )
        html_text += "</td></tr>\n"
        html_text += "</table>\n"

        html_text += (
            "<table class='table-metrics'><tr><th>Component</th><th>Weight</th>"
        )
        html_text += "<th>Invested Amount</th></tr>\n"

        sorted_weights = sorted(
            self.portfolio.weight_map.items(), key=lambda x: x[1], reverse=True
        )
        for etf, weight in sorted_weights:
            html_text += f"<tr><td>{etf}</td><td>{weight:.2%}</td>"
            html_text += f"<td>${weight * self.sip_amount:.2f}</td></tr>\n"
        html_text += "</table>\n"
        html_text += "<hr>"

        html_text += "<h2>Portfolio Metrics</h2>\n"

        def max_drawdown(series):
            cummax = series.cummax()
            dd = (cummax - series) / cummax
            return max(0.0, dd.max())

        num_years = (
            pd.Timestamp(self.end_date) - pd.Timestamp(self.start_date)
        ) / pd.Timedelta(days=365)
        # one-time investment
        cum_return = (
            self.price_series["portfolio_value"].iloc[-1]
            / self.price_series["cum_amount_invested"].iloc[-1]
            - 1
        )
        annualized_return = (1 + cum_return) ** (1 / num_years) - 1
        mdd = max_drawdown(self.price_series["portfolio_value"])
        max_pf_value = self.price_series["portfolio_value"].max()
        html_text += "<h3>One-Time-Investment</h3>\n"
        html_text += "<table class='table-metrics'>\n"
        html_text += f"<tr><td>Cumulative Return</td><td>{cum_return:.2%}</td></tr>\n"
        html_text += (
            f"<tr><td>Annualized Return</td><td>{annualized_return:.2%}</td></tr>\n"
        )
        html_text += (
            f"<tr><td>Peak Portfolio Value</td><td>${max_pf_value:,.2f}</td></tr>\n"
        )
        html_text += f"<tr><td>Max Drawdown from Peak</td><td>{mdd:.2%}</td></tr>\n"
        html_text += "</table>\n"

        # SIP
        html_text += "<h3>SIP</h3>\n"
        html_text += "<table class='table-metrics'>\n"
        mdd = max_drawdown(self.price_series_sip["portfolio_value"])
        max_pf_value = self.price_series_sip["portfolio_value"].max()
        roi = (
            self.price_series_sip[self.min_inv_made]["portfolio_value"]
            / self.price_series_sip[self.min_inv_made]["cum_amount_invested"].shift()
            - 1
        )
        html_text += (
            f"<tr><td>Total Return over Investment</td><td>{roi.iloc[-1]:.2%}</td>"
        )
        html_text += "</tr>\n"
        html_text += (
            f"<tr><td>Peak Portfolio Value</td><td>${max_pf_value:,.2f}</td></tr>\n"
        )
        html_text += (
            f"<tr><td>Max Drawdown%-age from Peak</td><td>{mdd:.2%}</td></tr>\n"
        )
        html_text += (
            f"<tr><td>Highest %-PNL on Investment*</td><td>{roi.max():.2%}</td></tr>\n"
        )
        html_text += (
            f"<tr><td>Lowest %-PNL on Investment*</td><td>{roi.min():.2%}</td></tr>\n"
        )
        html_text += "</table>\n"
        html_text += (
            f"<p>* %-PNL on investment is computed after at least {MIN_INV_PCT}%"
        )
        html_text += (
            " of the total investment is made to avoid inconsequential outliers."
        )
        html_text += "</p>\n"
        html_text += "</div>"

        return html_text


def plot_portfolio(args: Optional[dict], cookies: Dict, logger) -> Response:
    start = (pd.Timestamp.now("UTC") - pd.Timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    end = (pd.Timestamp.now("UTC") - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    default_vals = {
        "portfolio": cookies.get("portfolio", "VTI:0.5|VXUS:0.3|BND:0.1|BNDX:0.1"),
        "start_date": cookies.get("start_date", start),
        "end_date": cookies.get("end_date", end),
        "sip_amount": cookies.get("sip_amount", "1000"),
        "sip_frequency_days": cookies.get("sip_frequency_days", "30"),
        "min_inv": MIN_INV_PCT,
    }
    try:
        if (args is not None) and (len(args.keys()) > 0):
            portfolio, err = Portfolio.from_string(args["portfolio"])
            if err:
                default_vals["error"] = err
            plotter = PlotPortfolio(
                portfolio,
                args["start_date"],
                args["end_date"],
                float(args["sip_amount"]),
                int(args["sip_frequency_days"]),
                logger,
            )
            plot_url = plotter.plot()
            desc = plotter.description()
            for key, val in args.items():
                default_vals[key] = val
            rsp = make_response(
                render_template(
                    "plot.html",
                    plotted=True,
                    plot_url=plot_url,
                    description=desc,
                    **default_vals,
                ),
            )
            logger.info("Plotted portfolio")
            for key, val in args.items():
                rsp.set_cookie(key, val)
            return rsp
    except Exception as e:
        return make_response(
            render_template("plot.html", plotted=False, error=str(e), **default_vals),
        )
    return make_response(
        render_template("plot.html", plotted=False, **default_vals),
    )
