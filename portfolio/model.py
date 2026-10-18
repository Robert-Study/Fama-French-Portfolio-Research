"""Portfolio Construction Lab V8: PreparedModel and Canonical Model Preparation.

Authoritative implementation of Stage 04 Mathematical Specification (Section 1).
Provides immutable PreparedModel dataclass, ModelSpecificationError, and prepare_model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence
import numpy as np
import scipy.sparse as sp


class ModelSpecificationError(ValueError):
    """Raised when model inputs or outputs violate structural, dimensional, or numerical invariants."""


@dataclass(frozen=True)
class PreparedModel:
    """Canonical immutable prepared model contract for Portfolio Construction Lab V8.

    Guarantees positive semi-definiteness, dimensional conformance, and normalized
    currency invariants for downstream multi-horizon propagation and MIQP optimisation.

    Attributes
    ----------
    asset_ids : np.ndarray
        (M,) uint16 strictly monotonic, gap-free canonical index 0, ..., M-1.
    quote_currency : list[str]
        (M,) normalized to 'GBP' for all instruments.
    mu_arith_ann : np.ndarray
        (M,) float64 annualized net arithmetic expected total return vector in GBP.
    mu_log_ann : np.ndarray
        (M,) float64 annualized net geometric drift vector in GBP.
    cov_ann : np.ndarray
        (M, M) float64 annualized total return covariance matrix in GBP (symmetric, PSD).
    cov_monthly : np.ndarray
        (M, M) float64 monthly covariance matrix satisfying cov_monthly = cov_ann / 12.
    param_uncertainty : tuple[np.ndarray, np.ndarray]
        (C_mat, U_mat) 2 x (M, M) float64 symmetric PSD epistemic uncertainty matrices.
    dist_policy : tuple[np.ndarray, np.ndarray]
        (is_dist, d_yield) (M,) bool distribution flag and (M,) float64 cash payout yield.
    sleeve_masks : np.ndarray
        (64, M) bool reference sleeve binary eligibility matrix.
    holdings_csr : sp.csr_matrix | None, default=None
        (M_eq, N_c) float32/uint16 compressed sparse row holdings matrix.
    cash_idx : int | None, default=None
        Canonical index of the retail brokerage cash asset with exact 0 price volatility.
    metadata : dict[str, Any], default_factory=dict
        Supplemental model metadata, including cash rates and scenario configuration.
    """

    asset_ids: np.ndarray
    quote_currency: list[str]
    mu_arith_ann: np.ndarray
    mu_log_ann: np.ndarray
    cov_ann: np.ndarray
    cov_monthly: np.ndarray
    param_uncertainty: tuple[np.ndarray, np.ndarray]
    dist_policy: tuple[np.ndarray, np.ndarray]
    sleeve_masks: np.ndarray
    holdings_csr: sp.csr_matrix | None = None
    cash_idx: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate all dimensional, structural, and numerical invariants upon creation."""
        # 1. asset_ids validation
        if not isinstance(self.asset_ids, np.ndarray):
            raise ModelSpecificationError("asset_ids must be a numpy ndarray")
        if self.asset_ids.ndim != 1:
            raise ModelSpecificationError("asset_ids must be 1-dimensional with shape (M,)")
        m_count = len(self.asset_ids)
        if m_count == 0:
            raise ModelSpecificationError("asset_ids must not be empty (M >= 1)")
        if self.asset_ids.dtype != np.uint16:
            raise ModelSpecificationError(f"asset_ids dtype must be uint16, got {self.asset_ids.dtype}")
        expected_ids = np.arange(m_count, dtype=np.uint16)
        if not np.array_equal(self.asset_ids, expected_ids):
            raise ModelSpecificationError(
                "asset_ids must be strictly monotonic, gap-free canonical index 0, 1, ..., M-1"
            )

        # 2. quote_currency validation
        if not isinstance(self.quote_currency, (list, tuple, np.ndarray)):
            raise ModelSpecificationError("quote_currency must be a sequence of strings")
        qc_list = list(self.quote_currency)
        if len(qc_list) != m_count:
            raise ModelSpecificationError(
                f"quote_currency length ({len(qc_list)}) does not match asset count ({m_count})"
            )
        for idx, qc in enumerate(qc_list):
            if not isinstance(qc, str):
                raise ModelSpecificationError(f"quote_currency[{idx}] must be a string, got {type(qc)}")
            if qc != "GBP":
                raise ModelSpecificationError(
                    f"All instruments in quote_currency must be normalized to 'GBP', got {qc!r} at index {idx}"
                )
        object.__setattr__(self, "quote_currency", qc_list)

        # 3. mu_arith_ann validation
        if not isinstance(self.mu_arith_ann, np.ndarray):
            raise ModelSpecificationError("mu_arith_ann must be a numpy ndarray")
        if self.mu_arith_ann.shape != (m_count,):
            raise ModelSpecificationError(
                f"mu_arith_ann shape must be ({m_count},), got {self.mu_arith_ann.shape}"
            )
        if self.mu_arith_ann.dtype != np.float64:
            raise ModelSpecificationError(f"mu_arith_ann dtype must be float64, got {self.mu_arith_ann.dtype}")
        if not np.all(np.isfinite(self.mu_arith_ann)):
            raise ModelSpecificationError("mu_arith_ann must contain only finite numbers")
        if not np.all(np.abs(self.mu_arith_ann) < 1.0):
            raise ModelSpecificationError(
                "mu_arith_ann must satisfy ||mu||_inf < 1.0 (annualized return bounds)"
            )

        # 4. mu_log_ann validation
        if not isinstance(self.mu_log_ann, np.ndarray):
            raise ModelSpecificationError("mu_log_ann must be a numpy ndarray")
        if self.mu_log_ann.shape != (m_count,):
            raise ModelSpecificationError(
                f"mu_log_ann shape must be ({m_count},), got {self.mu_log_ann.shape}"
            )
        if self.mu_log_ann.dtype != np.float64:
            raise ModelSpecificationError(f"mu_log_ann dtype must be float64, got {self.mu_log_ann.dtype}")
        if not np.all(np.isfinite(self.mu_log_ann)):
            raise ModelSpecificationError("mu_log_ann must contain only finite numbers")

        # 5. cov_ann validation (Symmetry & Spectral PSD Gate)
        if not isinstance(self.cov_ann, np.ndarray):
            raise ModelSpecificationError("cov_ann must be a numpy ndarray")
        if self.cov_ann.shape != (m_count, m_count):
            raise ModelSpecificationError(
                f"cov_ann shape must be ({m_count}, {m_count}), got {self.cov_ann.shape}"
            )
        if self.cov_ann.dtype != np.float64:
            raise ModelSpecificationError(f"cov_ann dtype must be float64, got {self.cov_ann.dtype}")
        if not np.all(np.isfinite(self.cov_ann)):
            raise ModelSpecificationError("cov_ann must contain only finite numbers")

        max_asym = float(np.max(np.abs(self.cov_ann - self.cov_ann.T)))
        if max_asym > 1e-12:
            raise ModelSpecificationError(
                f"cov_ann is not symmetric: max |cov_ann - cov_ann.T| = {max_asym:.6e} > 1e-12"
            )
        cov_sym = 0.5 * (self.cov_ann + self.cov_ann.T)

        eigvals, eigvecs = np.linalg.eigh(cov_sym)
        min_eig = float(eigvals[0])
        if min_eig < -1e-12:
            raise ModelSpecificationError(
                f"Fatal non-positive semi-definite covariance matrix: minimum eigenvalue {min_eig:.6e} < -1e-12"
            )

        clipped_cov = False
        if min_eig < 0.0:
            # Spectral clipping projection onto positive semi-definite cone: V max(Lambda, 0) V^T
            clipped_eigvals = np.maximum(eigvals, 0.0)
            cov_sym = eigvecs @ np.diag(clipped_eigvals) @ eigvecs.T
            cov_sym = 0.5 * (cov_sym + cov_sym.T)
            clipped_cov = True

        # 6. cov_monthly validation
        if not isinstance(self.cov_monthly, np.ndarray):
            raise ModelSpecificationError("cov_monthly must be a numpy ndarray")
        if self.cov_monthly.shape != (m_count, m_count):
            raise ModelSpecificationError(
                f"cov_monthly shape must be ({m_count}, {m_count}), got {self.cov_monthly.shape}"
            )
        if self.cov_monthly.dtype != np.float64:
            raise ModelSpecificationError(f"cov_monthly dtype must be float64, got {self.cov_monthly.dtype}")
        if not np.all(np.isfinite(self.cov_monthly)):
            raise ModelSpecificationError("cov_monthly must contain only finite numbers")

        if clipped_cov:
            cov_monthly_scaled = cov_sym / 12.0
        else:
            if not np.allclose(self.cov_monthly, cov_sym / 12.0, atol=1e-12):
                raise ModelSpecificationError(
                    "cov_monthly must satisfy cov_monthly = cov_ann / 12 within 1e-12 tolerance"
                )
            cov_monthly_scaled = 0.5 * (self.cov_monthly + self.cov_monthly.T)

        # 7. param_uncertainty validation
        if not isinstance(self.param_uncertainty, tuple) or len(self.param_uncertainty) != 2:
            raise ModelSpecificationError("param_uncertainty must be a 2-tuple of (C_mat, U_mat)")

        c_mat, u_mat = self.param_uncertainty
        c_proj = self._validate_and_project_psd_matrix(c_mat, "param_uncertainty[0] (C_mat)", m_count)
        u_proj = self._validate_and_project_psd_matrix(u_mat, "param_uncertainty[1] (U_mat)", m_count)

        # 8. dist_policy validation
        if not isinstance(self.dist_policy, tuple) or len(self.dist_policy) != 2:
            raise ModelSpecificationError("dist_policy must be a 2-tuple of (is_dist, d_yield)")
        is_dist, d_yield = self.dist_policy
        if not isinstance(is_dist, np.ndarray) or is_dist.shape != (m_count,) or is_dist.dtype not in (bool, np.bool_):
            raise ModelSpecificationError(f"dist_policy[0] (is_dist) must be shape ({m_count},) bool ndarray")
        if not isinstance(d_yield, np.ndarray) or d_yield.shape != (m_count,) or d_yield.dtype != np.float64:
            raise ModelSpecificationError(f"dist_policy[1] (d_yield) must be shape ({m_count},) float64 ndarray")
        if not np.all(np.isfinite(d_yield)):
            raise ModelSpecificationError("dist_policy[1] (d_yield) must contain only finite numbers")
        if np.any(d_yield < 0.0) or np.any(d_yield >= 1.0):
            raise ModelSpecificationError("Dividend yields in dist_policy must be in [0, 1)")
        if np.any(~is_dist & (d_yield != 0.0)):
            raise ModelSpecificationError("Non-distributing assets (is_dist=False) must have d_yield == 0.0")

        # 9. sleeve_masks validation
        if not isinstance(self.sleeve_masks, np.ndarray):
            raise ModelSpecificationError("sleeve_masks must be a numpy ndarray")
        if self.sleeve_masks.shape != (64, m_count):
            raise ModelSpecificationError(
                f"sleeve_masks must have shape (64, {m_count}), got {self.sleeve_masks.shape}"
            )
        if self.sleeve_masks.dtype not in (bool, np.bool_):
            raise ModelSpecificationError(f"sleeve_masks dtype must be bool, got {self.sleeve_masks.dtype}")

        # 10. holdings_csr validation
        if self.holdings_csr is not None:
            if not sp.issparse(self.holdings_csr):
                raise ModelSpecificationError("holdings_csr must be a scipy sparse matrix")
            if not isinstance(self.holdings_csr, (sp.csr_matrix, sp.csr_array)):
                raise ModelSpecificationError("holdings_csr must be in CSR format")
            if self.holdings_csr.ndim != 2:
                raise ModelSpecificationError("holdings_csr must be 2-dimensional")
            m_eq, _ = self.holdings_csr.shape
            if m_eq > m_count:
                raise ModelSpecificationError(
                    f"holdings_csr row count ({m_eq}) cannot exceed universe size ({m_count})"
                )
            if self.holdings_csr.data.dtype != np.float32:
                raise ModelSpecificationError(
                    f"holdings_csr values must have dtype float32, got {self.holdings_csr.data.dtype}"
                )

        # 11. Cash Anchor Consistency Gate
        eff_cash_idx = self.cash_idx
        if eff_cash_idx is None and isinstance(self.metadata, dict):
            eff_cash_idx = self.metadata.get("cash_idx")

        if eff_cash_idx is not None:
            if not (0 <= eff_cash_idx < m_count):
                raise ModelSpecificationError(
                    f"cash_idx {eff_cash_idx} out of bounds for universe of size {m_count}"
                )
            if not np.all(cov_sym[eff_cash_idx, :] == 0.0):
                raise ModelSpecificationError(
                    f"Cash anchor at index {eff_cash_idx} must have exact 0 price volatility "
                    f"(cov_ann[{eff_cash_idx}, :] == 0)"
                )

        # 12. Immutability: Store detached, read-only copies of buffers
        clean_asset_ids = self.asset_ids.copy()
        clean_asset_ids.flags.writeable = False
        object.__setattr__(self, "asset_ids", clean_asset_ids)

        clean_mu_arith = self.mu_arith_ann.copy()
        clean_mu_arith.flags.writeable = False
        object.__setattr__(self, "mu_arith_ann", clean_mu_arith)

        clean_mu_log = self.mu_log_ann.copy()
        clean_mu_log.flags.writeable = False
        object.__setattr__(self, "mu_log_ann", clean_mu_log)

        cov_sym.flags.writeable = False
        object.__setattr__(self, "cov_ann", cov_sym)

        cov_monthly_scaled.flags.writeable = False
        object.__setattr__(self, "cov_monthly", cov_monthly_scaled)

        c_proj.flags.writeable = False
        u_proj.flags.writeable = False
        object.__setattr__(self, "param_uncertainty", (c_proj, u_proj))

        clean_is_dist = is_dist.copy()
        clean_is_dist.flags.writeable = False
        clean_d_yield = d_yield.copy()
        clean_d_yield.flags.writeable = False
        object.__setattr__(self, "dist_policy", (clean_is_dist, clean_d_yield))

        clean_sleeve_masks = self.sleeve_masks.copy()
        clean_sleeve_masks.flags.writeable = False
        object.__setattr__(self, "sleeve_masks", clean_sleeve_masks)

    @staticmethod
    def _validate_and_project_psd_matrix(mat: np.ndarray, name: str, m_count: int) -> np.ndarray:
        """Validate matrix symmetry and spectral positive semi-definiteness with clipping."""
        if not isinstance(mat, np.ndarray):
            raise ModelSpecificationError(f"{name} must be a numpy ndarray")
        if mat.shape != (m_count, m_count):
            raise ModelSpecificationError(f"{name} shape must be ({m_count}, {m_count}), got {mat.shape}")
        if mat.dtype != np.float64:
            raise ModelSpecificationError(f"{name} dtype must be float64, got {mat.dtype}")
        if not np.all(np.isfinite(mat)):
            raise ModelSpecificationError(f"{name} must contain only finite numbers")

        asym = float(np.max(np.abs(mat - mat.T)))
        if asym > 1e-12:
            raise ModelSpecificationError(
                f"{name} is not symmetric: max |M - M.T| = {asym:.6e} > 1e-12"
            )
        sym = 0.5 * (mat + mat.T)

        evals, evecs = np.linalg.eigh(sym)
        min_ev = float(evals[0])
        if min_ev < -1e-12:
            raise ModelSpecificationError(
                f"{name} has fatal structural negative eigenvalue: {min_ev:.6e} < -1e-12"
            )
        if min_ev < 0.0:
            clipped_evals = np.maximum(evals, 0.0)
            sym = evecs @ np.diag(clipped_evals) @ evecs.T
            sym = 0.5 * (sym + sym.T)
        return sym

    @property
    def num_assets(self) -> int:
        """Return canonical asset universe size M."""
        return len(self.asset_ids)

    @property
    def M(self) -> int:
        """Return canonical asset universe size M."""
        return len(self.asset_ids)


def prepare_model(
    snapshot: Any,
    method: str = "holdings",
    config: dict[str, Any] | None = None,
) -> PreparedModel:
    """Canonical model preparation entry-point contract.

    Parameters
    ----------
    snapshot : Any
        Point-in-time cross-sectionally aligned market, fundamental, and reference data bundle.
    method : {"holdings", "etf"}, default="holdings"
        Estimation route:
        - "holdings": Bottom-up Company-Characteristics Route (Section 2).
        - "etf": Top-down ETF-Return Route (Section 3).
    config : dict[str, Any] | None, default=None
        Configuration dictionary overriding production defaults.

    Returns
    -------
    PreparedModel
        Immutable, structurally identical prepared model instance.

    Raises
    ------
    ModelSpecificationError
        If method is invalid or prepared outputs violate structural invariants.
    """
    if method not in ("holdings", "etf"):
        raise ModelSpecificationError(f"Invalid preparation method: {method!r}. Must be 'holdings' or 'etf'.")

    if method == "holdings":
        return _prepare_holdings_route(snapshot, config)
    else:
        return _prepare_etf_route(snapshot, config)


def _prepare_holdings_route(snapshot: Any, config: dict[str, Any] | None = None) -> PreparedModel:
    """Route stub for Company-Characteristics bottom-up calibration."""
    if isinstance(snapshot, PreparedModel):
        return snapshot
    if isinstance(snapshot, dict) and "asset_ids" in snapshot:
        return PreparedModel(**snapshot)
    raise NotImplementedError(
        "Company-Characteristics Route (method='holdings') is scheduled for implementation in portfolio.holdings_model"
    )


def _prepare_etf_route(snapshot: Any, config: dict[str, Any] | None = None) -> PreparedModel:
    """Route stub for ETF-Return top-down calibration."""
    if isinstance(snapshot, PreparedModel):
        return snapshot
    if isinstance(snapshot, dict) and "asset_ids" in snapshot:
        return PreparedModel(**snapshot)
    raise NotImplementedError(
        "ETF-Return Route (method='etf') is scheduled for implementation in portfolio.model"
    )


__all__ = ["ModelSpecificationError", "PreparedModel", "prepare_model"]
