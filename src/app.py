from flask import Flask, request, render_template, make_response
import logging
import os
import yfinance as yf

app = Flask(__name__)


@app.route("/", methods=["GET"])
@app.route("/index.html", methods=["GET"])
def index():
    print("Request received!")
    return render_template("index.html")


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
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=debug)
