"""
Utilities for Markowitz Optimization

.. author:: Marek Ozana
.. date:: 2024-03

src: https://github.com/MarekOzana/streamlit_markowitz/blob/main/src/optimization.py

"""

import traceback
import typing

import numpy as np
import scipy.optimize as sco


@typing.no_type_check
def find_min_var_portfolio(
    exp_rets: np.ndarray,
    cov: np.ndarray,
    r_min: float = 0,
    w_max: float = 1,
):
    """Find portfolio with minimum variance given constraint return
    Solve the following optimization problem
        min: w.T*COV*w
        subjto: w.T * r_ann >= r_min
                sum(w) = 1
                0 <= w[i] <= w_max for every i
    Parameters
    ==========
        exp_rets: annualized expected returns
        cov: covariance matrix
        r_min: minimum portfolio return (constraint)
        w_max: maximum individual weight (constraint)
    Returns
    =======
        (w, r_opt, vol_opt)
        w: portfolio weights
        r_opt: return of optimal portfolio
        vol_opt: volatility of optimal portfolio
    """

    def calc_var(w, cov) -> np.float64:
        """Calculate portfolio Variance"""
        variance = np.dot(w.T, np.dot(cov, w))
        assert variance > -1e-9
        return max(variance, 0.0)

    n_assets = len(exp_rets)
    constraints = [
        # sum(w_i) = 1
        {"type": "eq", "fun": lambda x: np.sum(x) - 1},
        # sum(r_i * w_i >= r_min)
        {"type": "ineq", "fun": lambda x: np.dot(x.T, exp_rets) - r_min},
    ]
    bounds = tuple((0, w_max) for asset in range(n_assets))  # sequence of (min,max)

    pos_rets = [np.sqrt(max(ret, 0.0)) for ret in exp_rets]
    opts = sco.minimize(
        # Objective Function
        fun=calc_var,
        # Initial guess
        x0=[x / sum(pos_rets) for x in pos_rets],
        # Extra Arguments to objective function
        args=(cov,),
        method="SLSQP",
        options={"maxiter": 500},
        bounds=bounds,
        constraints=constraints,
        tol=1e-6,
    )
    w = opts["x"]
    r_opt = np.dot(w, exp_rets)
    vol_opt = np.sqrt(calc_var(w, cov))
    return w, r_opt, vol_opt


def calc_eff_front(
    exp_rets: np.ndarray, cov: np.ndarray, logger, min_ret: float, max_ret: float
) -> dict[str, list]:
    """Calculate effective frontier

    Iteratively find optimal portfolio for list of minimum returns

    Parameters
    ----------
        exp_rets: annualized expected returns
        cov: covariance matrix

    Returns
    -------
        frnt: dict("ret":list(float), "vol":list(float))
        Dictionary with points on the efficient frontier
    """
    N_STEPS: int = 25
    frnt: dict[str, list] = {"rets": list(), "vols": list(), "sharpe": list()}
    for r_min in np.linspace(min_ret, max_ret, N_STEPS):
        try:
            _, ret, vol = find_min_var_portfolio(
                exp_rets=exp_rets, cov=cov, r_min=r_min
            )
            if ret >= r_min:
                logger.info(f"r_min: {r_min:.3f}%, ret: {ret:.3f}%, vol: {vol:.2f}%")
                frnt["vols"].append(vol)
                frnt["rets"].append(ret)
                frnt["sharpe"].append(ret / vol)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Error in optimization for r_min: {r_min:.3f}%: {e}")
            logger.error(traceback.format_exc())
    return frnt
