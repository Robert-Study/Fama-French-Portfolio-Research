"""Portable V8 input contracts. Keep pickle classes outside executable scripts."""
from dataclasses import dataclass, field
from datetime import date

import numpy as np


@dataclass(frozen=True)
class MarketSnapshot:
    """Dated, calibrated GBP moments; does not imply either route was calibrated."""

    as_of_date: str
    tickers: tuple[str, ...]
    cash_index: int
    cov_ann: np.ndarray
    mu_arith_ann: np.ndarray
    mu_log_ann: np.ndarray
    param_uncertainty: tuple[np.ndarray, np.ndarray]
    sleeve_masks: np.ndarray
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        date.fromisoformat(self.as_of_date)
        if (not isinstance(self.tickers, tuple) or len(self.tickers) != 68
                or any(not isinstance(t, str) or not t.strip() for t in self.tickers)
                or len(set(self.tickers)) != 68):
            raise ValueError("tickers must be a tuple of 68 unique nonempty strings")
        if type(self.cash_index) is not int or not 0 <= self.cash_index < 68:
            raise ValueError("cash_index must be an integer in [0, 67]")
        for name in ("mu_arith_ann", "mu_log_ann"):
            self._array(getattr(self, name), (68,), np.float64, name)
        if np.max(np.abs(self.mu_arith_ann)) >= 1:
            raise ValueError("mu_arith_ann must satisfy max(abs(mu)) < 1")
        self._psd(self.cov_ann, "cov_ann")
        if (np.any(self.cov_ann[self.cash_index, :] != 0.0)
                or np.any(self.cov_ann[:, self.cash_index] != 0.0)):
            raise ValueError("cash covariance row and column must be exactly zero")
        expected = self.mu_arith_ann - 0.5 * np.diag(self.cov_ann)
        if not np.array_equal(self.mu_log_ann, expected):
            raise ValueError("mu_log_ann must equal mu_arith_ann - 0.5 * diag(cov_ann)")
        if not isinstance(self.param_uncertainty, tuple) or len(self.param_uncertainty) != 2:
            raise ValueError("param_uncertainty must be a (C_mat, U_mat) tuple")
        for matrix, name in zip(self.param_uncertainty, ("C_mat", "U_mat")):
            self._psd(matrix, name)
        self._array(self.sleeve_masks, (64, 68), np.bool_, "sleeve_masks")
        singleton = self.sleeve_masks[[1, 2, 4, 8, 16, 32]]
        if not np.all(singleton.sum(axis=0) == 1):
            raise ValueError("Each instrument must belong to exactly one sleeve")
        bits = (np.arange(64)[:, None] & (1 << np.arange(6))) != 0
        expected_masks = (bits.astype(int) @ singleton.astype(int)) != 0
        if not np.array_equal(self.sleeve_masks, expected_masks):
            raise ValueError("sleeve_masks must follow the six-bit union contract")
        for name in ("cov_ann", "mu_arith_ann", "mu_log_ann", "sleeve_masks"):
            object.__setattr__(self, name, self._freeze(getattr(self, name)))
        object.__setattr__(self, "param_uncertainty",
                           tuple(self._freeze(x) for x in self.param_uncertainty))

    @staticmethod
    def _array(value, shape, dtype, name):
        if (not isinstance(value, np.ndarray) or value.shape != shape
                or value.dtype != dtype or not np.isfinite(value).all()):
            raise ValueError(f"{name} must be finite {dtype} with shape {shape}")

    @classmethod
    def _psd(cls, value, name):
        cls._array(value, (68, 68), np.float64, name)
        if not np.array_equal(value, value.T):
            raise ValueError(f"{name} must be exactly symmetric")
        # Permit only floating-point eigensolver roundoff; do not repair bad data.
        tolerance = 100 * np.finfo(np.float64).eps * max(1., np.linalg.norm(value, 2))
        if np.linalg.eigvalsh(value).min() < -tolerance:
            raise ValueError(f"{name} must be PSD")

    @staticmethod
    def _freeze(value):
        result = value.copy()
        result.flags.writeable = False
        return result
