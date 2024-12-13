from enum import Enum
from threading import Thread
from typing import Dict, Optional

from flask import Response, make_response, redirect, render_template, url_for

from backend.etf import ETFOptimizer
from backend.yf_utils import YFDataQualityError, YFDownloadError

NUM_CONTRACTS = 100
CORR = 0.99
NUM_YEARS = 5


class TaskState(Enum):
    NOT_FOUND = "NOT_FOUND"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class TaskDB(object):
    task_data: Dict[str, Dict[str, str]] = {
        "error": {},
        "result": {},
        "log": {},
    }

    @classmethod
    def get(cls, key: str, task_id: str) -> Optional[str]:
        return cls.task_data[key].get(task_id)

    @classmethod
    def put(cls, key: str, task_id: str, result) -> None:
        cls.task_data[key][task_id] = result

    @classmethod
    def contains(cls, key: str, task_id: str) -> bool:
        return task_id in cls.task_data[key]

    @classmethod
    def get_state(cls, task_id: str):
        if task_id not in cls.task_data["log"]:
            return TaskState.NOT_FOUND
        if task_id in cls.task_data["result"]:
            return TaskState.SUCCESS
        if task_id in cls.task_data["error"]:
            return TaskState.FAILURE
        return TaskState.IN_PROGRESS


def run_etf_optimizer(task_id, optimizer: ETFOptimizer, logger):
    TaskDB.put("log", task_id, "")
    try:
        optimizer.run_optimizer(task_id, logger)
        assert optimizer.portfolio is not None
        TaskDB.put("result", task_id, optimizer.portfolio.to_html())
        logger.info(f"Stored results for task ID {task_id}")
    except (YFDownloadError, YFDataQualityError) as e:
        # Errors related to yahoo finance data so safe to expose
        TaskDB.put(
            "error",
            task_id,
            format_error(str(e)),
        )
        logger.error(f"Error for task ID {task_id}: {e}")
    except Exception as e:
        TaskDB.put(
            "error",
            task_id,
            format_error(f"Unexpected error in running task ID {task_id}"),
        )
        logger.error(f"Unexpected error for task ID {task_id}: {e}")


def format_log(log_output: Optional[str]) -> str:
    if (log_output is None) or (log_output == ""):
        return ""
    html_text = "<div class='code-box'>Progress Logs:<br>"
    html_text += log_output.strip().replace("\n", "<br>")
    html_text += "</div>\n"
    return html_text


def format_error(error_output: str) -> str:
    html_text = f"<div class='code-box'>{error_output}</div>"
    html_text += "<div class='form-container'>"
    new_tab = "target='_blank' rel='noopener noreferrer'"
    html_text += f"<a href='/' {new_tab}><button>Run Optimizer Again</button></a>"
    html_text += "</div>\n"
    return html_text


def render_optimizer(args: Optional[Dict], logger) -> Response:
    if args is not None:
        logger.info(f"Received args: {args}")
        if args["universe"] == "etf_vol":
            try:
                optimizer = ETFOptimizer(
                    args["currency"],
                    int(args["num_contracts"]),
                    float(args["correlation_cutoff"]),
                    float(args["num_years"]),
                )
                task_id = optimizer.now.strftime("%Y%m%d_%H%M%S_%f")
                thread = Thread(
                    target=run_etf_optimizer,
                    args=(task_id, optimizer, logger),
                )
                logger.info(f"Starting optimizer thread {task_id}")
                thread.start()
                rsp = make_response(redirect(url_for("task", task_id=task_id)))
                rsp.set_cookie("task_id", task_id)
                rsp.set_cookie("currency", args["currency"])
                rsp.set_cookie("num_contracts", args["num_contracts"])
                rsp.set_cookie("correlation_cutoff", args["correlation_cutoff"])
                rsp.set_cookie("num_years", args["num_years"])
                return rsp
            except ValueError as e:
                logger.error(e)
                # need a better alternative to just ignore bad input
                return make_response(
                    render_template(
                        "optimizer.html",
                        submitted=False,
                        in_progress=False,
                        portfolio_output="",
                        num_contracts=NUM_CONTRACTS,
                        corr=CORR,
                        num_years=NUM_YEARS,
                    ),
                )
        else:
            raise NotImplementedError(f"Universe {args['universe']} not implemented")
    else:
        return make_response(
            render_template(
                "optimizer.html",
                submitted=False,
                in_progress=False,
                portfolio_output="",
                num_contracts=NUM_CONTRACTS,
                corr=CORR,
                num_years=NUM_YEARS,
            ),
        )
