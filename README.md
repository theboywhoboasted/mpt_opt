This repo helps you to use historical data to compute a portfolio of ETFs with highest risk-adjusted return.

# Usage
- To launch the webserver, run: `./run_docker.sh`
- Once the server is up, you can access the webpage in a browser at `http://localhost:8080/`

# Dependencies
- The project requires docker which can be installed from https://docs.docker.com/engine/install/
- All other dependencies for running should be managed directly by Docker

# Optimization Algorithm
- We list all the US ETFs in order of recently traded volume (in dollar terms) as our product universe
- To create a subset of N contracts from this universe, we add contracts one by one from the pre-sorted universe. At each step, we check that the newly added product does not have a very high correlation with any existing element of the subset. This cutoff defaults to 99%, but is configurable.
- Once we have N elements in the subset, we attempt to form an optimal portfolio (with least variance) under the following constraints:
  - the sum of weights is 1
  - no weight is greater than 1 or less than 0 [^1]
  - the expected return of the portfolio is at least r_min
- We iterate over different values of r_min to get the efficient frontier [^2]
- From the universe, we choose the element with the lowest variance in returns and call it the risk-free asset. The expect return of this element is referred to as the 'risk-free' return for sharpe computation.
- The portfolio on the efficient frontier with the highest sharpe ratio is returned.

[^1]: We do not allow shorting ETFs but the ETF itself maybe shorting stocks (eg. SQQQ)
[^2]: See https://en.wikipedia.org/wiki/Modern_portfolio_theory

# Known issues
- The current implementation depends heavily on `yfinance` for both ETF metadata and trading data. Unfortunately connecting to Yahoo Finance has been inconsistent over a variety of internet connections and VPN. [^3]

[^3]: See https://github.com/ranaroussi/yfinance/discussions/2081
