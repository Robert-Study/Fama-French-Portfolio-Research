from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from scipy.optimize import linprog


TOL = 1e-6


@dataclass
class Frontier:
    weights: np.ndarray
    returns: np.ndarray
    volatilities: np.ndarray
    targets: np.ndarray
    solvers: list[str]
    max_violation: float


def efficient_frontier(mean, covariance, cap=1.0, points=101, exposure=None, limits=None):
    """Solve monthly mean/variance portfolios. Returns and volatilities stay monthly."""
    mu = np.asarray(mean, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    n = len(mu)
    upper = np.broadcast_to(np.asarray(cap, dtype=float), (n,)).copy()
    if n == 0 or n > 50 or cov.shape != (n, n):
        raise ValueError("Choose between 1 and 50 funds with a matching covariance matrix.")
    if not all(np.isfinite(x).all() for x in (mu, cov, upper)):
        raise ValueError("The optimiser received non-finite inputs.")
    if (upper <= 0).any() or (upper > 1).any() or upper.sum() < 1 - 1e-12:
        raise ValueError("The fund limit is infeasible: available weights cannot sum to 100%.")
    if not np.allclose(cov, cov.T, atol=1e-12, rtol=1e-8):
        raise ValueError("Covariance must be symmetric.")
    cov = (cov + cov.T) / 2
    if np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError("Covariance is not positive semidefinite.")
    if not isinstance(points, int) or not 2 <= points <= 201:
        raise ValueError("Use between 2 and 201 frontier points.")
    a = np.zeros((0, n)) if exposure is None else np.atleast_2d(np.asarray(exposure, float))
    b = np.zeros(0) if limits is None else np.atleast_1d(np.asarray(limits, float))
    if a.shape != (len(b), n) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Exposure limits have inconsistent dimensions or missing values.")

    # Annual scaling improves solver conditioning; it does not change the optimum.
    annual_mu, annual_cov = 12 * mu, 12 * cov
    endpoint = linprog(-annual_mu, A_ub=a if len(b) else None,
                       b_ub=b if len(b) else None, A_eq=np.ones((1, n)),
                       b_eq=[1.0], bounds=list(zip(np.zeros(n), upper)), method="highs")
    if not endpoint.success:
        raise ValueError("No portfolio satisfies these limits. Relax a limit or add funds.")

    w = cp.Variable(n)
    target = cp.Parameter()
    constraints = [cp.sum(w) == 1, w >= 0, w <= upper, annual_mu @ w >= target]
    if len(b):
        constraints.append(a @ w <= b)
    problem = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(annual_cov))), constraints)

    def solve(required):
        target.value = required
        for solver in ("OSQP", "CLARABEL"):
            try:
                options = dict(eps_abs=1e-9, eps_rel=1e-9, max_iter=50000,
                               polishing=True) if solver == "OSQP" else {}
                problem.solve(solver=solver, warm_start=True, **options)
            except cp.error.SolverError:
                continue
            if problem.status != cp.OPTIMAL or w.value is None:
                continue
            raw = np.asarray(w.value).reshape(-1)
            if not np.isfinite(raw).all() or raw.min() < -TOL:
                continue
            cleaned = np.maximum(raw, 0)
            cleaned /= cleaned.sum()
            violation = max(abs(cleaned.sum() - 1), float(np.max(cleaned - upper)),
                            float(required - annual_mu @ cleaned), 0.0)
            if len(b):
                violation = max(violation, float(np.max(a @ cleaned - b)))
            if violation <= TOL:
                return cleaned, solver, violation
        raise ValueError("The solver could not verify a portfolio at this target. Try less restrictive limits.")

    minimum, first_solver, first_error = solve(float(annual_mu.min()) - 1)
    start, end = float(annual_mu @ minimum), float(annual_mu @ endpoint.x)
    targets = np.array([start]) if end - start <= 1e-8 else np.linspace(start, end, points)
    weights, solvers, errors = [minimum], [first_solver], [first_error]
    for required in targets[1:]:
        result, solver, error = solve(float(required))
        weights.append(result)
        solvers.append(solver)
        errors.append(error)
    weights = np.asarray(weights)
    variance = np.einsum("ij,jk,ik->i", weights, cov, weights)
    return Frontier(weights, weights @ mu, np.sqrt(np.maximum(variance, 0)),
                    targets / 12, solvers, max(errors))
