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
)
from waitress import serve

from cache.utils import populate_all_caches
from web.optimizer import (
    CORR,
    NUM_CONTRACTS,
    NUM_YEARS,
    TaskDB,
    TaskState,
    format_error,
    format_log,
    render_optimizer,
)
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
        return make_response(render_template("cookies.html", redir_page="index.html"))

    if request.method == "POST":
        args = request.form
    else:
        args = None
    return render_optimizer(args, app_logger)


@app.route("/task/<task_id>")
def task(task_id) -> Response:
    app_logger = yf.utils.get_yf_logger()
    app_logger.info("Loading task ID: %s", task_id)
    task_state = TaskDB.get_state(task_id)
    cookie_dict = {
        "num_contracts": request.cookies.get("num_contracts", NUM_CONTRACTS),
        "corr": request.cookies.get("correlation_cutoff", CORR),
        "num_years": request.cookies.get("num_years", NUM_YEARS),
        "submitted": True,
    }
    log_output = format_log(TaskDB.get("log", task_id))
    if task_state == TaskState.NOT_FOUND:
        not_found = format_error(f"Task not found: {task_id}")
        rsp = make_response(
            render_template(
                "optimizer.html",
                in_progress=False,
                error_output=not_found,
                **cookie_dict,
            ),
        )
    elif task_state == TaskState.FAILURE:
        failure = TaskDB.get("error", task_id)
        assert failure is not None
        rsp = make_response(
            render_template(
                "optimizer.html",
                in_progress=False,
                log_output=log_output,
                error_output=failure,
                **cookie_dict,
            ),
        )
    elif task_state == TaskState.SUCCESS:
        portfolio_output = TaskDB.get("result", task_id)
        rsp = make_response(
            render_template(
                "optimizer.html",
                in_progress=False,
                log_output=log_output,
                portfolio_output=portfolio_output,
                **cookie_dict,
            ),
        )
    else:
        rsp = make_response(
            render_template(
                "optimizer.html",
                in_progress=True,
                log_output=log_output,
                **cookie_dict,
            ),
        )
    return rsp


@app.route("/plot", methods=["GET"])
@app.route("/plot.html", methods=["GET"])
def plot() -> Response:
    app_logger = yf.utils.get_yf_logger()
    if not are_cookies_allowed():
        return make_response(render_template("cookies.html", redir_page="plot.html"))
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
        logger.setLevel(logging.ERROR)
        debug = False

    populate_all_caches(logger)

    # this port needs to be exposed in the Dockerfile
    port = int(os.getenv("PORT", "8080"))
    serve(app, host="0.0.0.0", port=port)
