import logging
import os

import yfinance as yf
from flask import (
    Flask,
    Response,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from web.optimizer import CORR, NUM_CONTRACTS, NUM_YEARS, ResultsDB, render_optimizer
from web.plot import plot_portfolio

app = Flask(__name__)


def are_cookies_allowed():
    cookies_allowed = request.cookies.get("cookies_allowed", "F")
    return cookies_allowed == "T"


@app.route("/cookies.html", methods=["POST", "GET"])
def ask_for_cookies():
    if request.method == "POST" and "allow" in request.form:
        redir_page = request.form.get("redir_page", "index.html")
        response = make_response(redirect(redir_page))
        response.set_cookie("cookies_allowed", "T")
        return response
    response = make_response(render_template("cookies.html", redir_page="index.html"))
    return response


@app.route("/", methods=["GET", "POST"])
@app.route("/index.html", methods=["GET", "POST"])
@app.route("/optimizer.html", methods=["GET", "POST"])
def index() -> Response:
    # Set up logging
    app_logger = yf.utils.get_yf_logger()

    # check for cookies
    if not are_cookies_allowed():
        return render_template("cookies.html", redir_page="index.html")

    if request.method == "POST":
        args = request.form
    else:
        args = None
    return render_optimizer(args, app_logger)


@app.route("/loading/<task_id>")
def loading(task_id) -> Response:
    app_logger = yf.utils.get_yf_logger()
    app_logger.info("Loading task ID: %d", task_id)
    if ResultsDB.contains(task_id):
        app_logger.info("Redirecting to result for task ID: %d", task_id)
        return redirect(url_for("result", task_id=task_id))
    rsp = make_response(
        render_template(
            "optimizer.html",
            submitted=True,
            in_progress=True,
            portfolio_output="",
            num_contracts=request.cookies.get("num_contracts", NUM_CONTRACTS),
            corr=request.cookies.get("correlation_cutoff", CORR),
            num_years=request.cookies.get("num_years", NUM_YEARS),
        ),
    )
    return rsp


@app.route("/result/<task_id>")
def result(task_id) -> Response:
    app_logger = yf.utils.get_yf_logger()
    app_logger.info("Result task ID: %d", task_id)
    if ResultsDB.contains(task_id):
        optimizer = ResultsDB.get(task_id)
        portfolio_output = optimizer.portfolio.to_html()
        rsp = make_response(
            render_template(
                "optimizer.html",
                submitted=True,
                in_progress=False,
                portfolio_output=portfolio_output,
                num_contracts=request.cookies.get("num_contracts", NUM_CONTRACTS),
                corr=request.cookies.get("correlation_cutoff", CORR),
                num_years=request.cookies.get("num_years", NUM_YEARS),
            ),
        )
        return rsp
    else:
        return redirect(url_for("loading", task_id=task_id))


@app.route("/plot", methods=["GET"])
@app.route("/plot.html", methods=["GET"])
def plot() -> Response:
    app_logger = yf.utils.get_yf_logger()
    if not are_cookies_allowed():
        return render_template("cookies.html", redir_page="plot.html")
    if request.method == "GET":
        args = request.args
    else:
        args = None
    return plot_portfolio(args, request.cookies, app_logger)


if __name__ == "__main__":
    logging.raiseExceptions = True
    logging.basicConfig(level=logging.INFO)
    logger = yf.utils.get_yf_logger()
    if os.getenv("DEV_MODE", "False").lower() == "true":
        logger.setLevel(logging.INFO)
        debug = True
    else:
        logger.setLevel(logging.CRITICAL)
        debug = False

    # this port needs to be exposed in the Dockerfile
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=debug)
