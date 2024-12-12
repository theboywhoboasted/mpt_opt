from threading import Thread
from typing import Any, Dict, Optional

from flask import Response, make_response, redirect, render_template, url_for

from backend.etf import ETFOptimizer

NUM_CONTRACTS = 100
CORR = 0.99
NUM_YEARS = 5


class ResultsDB(object):
    results: Dict[str, Any] = dict()

    @classmethod
    def get(cls, task_id: str):
        return cls.results.get(task_id)

    @classmethod
    def put(cls, task_id: str, result):
        cls.results[task_id] = result

    @classmethod
    def contains(cls, task_id):
        return task_id in cls.results


def run_etf_optimizer(task_id, optimizer, logger):
    optimizer.run_optimizer(logger)
    ResultsDB.put(task_id, optimizer)
    logger.info(f"Stored results for task ID {task_id}: {ResultsDB.contains(task_id)}")


def render_optimizer(args: Optional[Dict], logger) -> Response:
    if args is not None:
        logger.info(f"Received args: {args}")
        if args["universe"] == "etf_vol":
            try:
                optimizer = ETFOptimizer(
                    args["currency"],
                    int(args["num_contracts"]),
                    float(args["correlation_cutoff"]),
                    int(args["num_years"]),
                )
                task_id = optimizer.now.strftime("%Y%m%d_%H%M%S_%f")
                thread = Thread(
                    target=run_etf_optimizer,
                    args=(task_id, optimizer, logger),
                )
                logger.info(f"Starting optimizer thread {task_id}")
                thread.start()
                rsp = make_response(redirect(url_for("loading", task_id=task_id)))
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
