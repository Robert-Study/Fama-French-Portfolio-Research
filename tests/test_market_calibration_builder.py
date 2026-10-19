"""Economic accounting and end-to-end calibration contract regressions."""
import json

import numpy as np
import pytest

from scripts import build_market_calibration as calibration
from scripts import build_market_snapshot as serializer
from portfolio.model import PreparedModel, prepare_model


@pytest.fixture
def payload():
    return calibration.build_calibration(serializer.DEFAULT_FIXTURES)


def test_all_instruments_and_uncertainty_contract(payload):
    assert payload == calibration.build_calibration(serializer.DEFAULT_FIXTURES)
    assert payload['tickers'] == serializer.build_catalogue(serializer.DEFAULT_FIXTURES).ticker.tolist()
    assert len(payload['mu_monthly']) == 68
    cov = np.asarray(payload['cov_monthly'], dtype=np.float64)
    assert cov.shape == (68, 68)
    np.testing.assert_array_equal(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() >= -1e-12
    assert np.count_nonzero(cov[0]) == np.count_nonzero(cov[:, 0]) == 0
    np.testing.assert_allclose(payload['C_mat'], cov * 12 / 60, rtol=1e-14, atol=0)
    np.testing.assert_allclose(payload['U_mat'], 1e-4 * np.diag(np.diag(cov * 12)), rtol=1e-14, atol=0)
    assert payload['calibration_status'] == 'assumption_based'


def test_cash_bond_and_commodity_accounting(payload):
    mu = dict(zip(payload['tickers'], np.asarray(payload['mu_monthly']) * 12))
    assert (1 + mu['T212_GBP_CASH'] / 12) ** 12 == pytest.approx(1.038)
    assert mu['IGLT'] == pytest.approx(.0513 - .0007)
    assert mu['SLXX'] == pytest.approx(.0611 - .002 - .002)
    assert mu['INXG'] == pytest.approx(.0187 + .02 - .001)
    assert mu['ITPG'] == pytest.approx(.0281 + .02 + .047 - .0482 - .001 - .0012)
    assert mu['SGLN'] == pytest.approx(.02 - .0012)
    assert mu['CMOP'] == pytest.approx(.0482 - .0019 - .0015)
    assert mu['COPA'] == pytest.approx(.0482 - .0049 - .0045)
    assert mu['IWFV'] - mu['SWDA'] == pytest.approx(.005 - (.0025 - .002))


def test_leverage_cost_and_fx_once(payload):
    audit = payload['calibration_details']['instruments']
    qqq = audit['3QQQ']
    assert qqq['net_arith_ann'] == pytest.approx(
        3 * qqq['gross_underlying_ann'] - 2 * (.0483 + .02) * 365 / 360
        - .0075 - 3 * .002)
    factors = payload['calibration_details']['factor_names']
    loadings = np.array(payload['calibration_details']['annual_factor_loadings'])
    indices = {t: i for i, t in enumerate(payload['tickers'])}
    assert loadings[indices['3QQQ'], factors.index('fx')] == loadings[indices['EQQQ'], factors.index('fx')]
    assert loadings[indices['3QQQ'], factors.index('equity')] == 3 * loadings[indices['EQQQ'], factors.index('equity')]


@pytest.mark.parametrize('method', ['holdings', 'etf'])
def test_real_snapshot_to_release_model(payload, tmp_path, method):
    path = tmp_path / 'calibration.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    snapshot = serializer.build_snapshot(serializer.DEFAULT_FIXTURES, path)
    model = prepare_model(snapshot, method=method)
    assert isinstance(model, PreparedModel)
    assert model.metadata['canonical_tickers'] == snapshot.tickers
    assert model.metadata['method'] == method
    assert model.metadata['cash_index'] == model.cash_idx == 0
    assert model.metadata['calibration_method'] == 'etf'
    assert model.metadata['calibration_status'] == 'assumption_based'
    assert model.metadata['preparation'] == 'supplied_snapshot_moments'
    np.testing.assert_array_equal(model.cov_ann, snapshot.cov_ann)
    np.testing.assert_allclose(model.cov_monthly, payload['cov_monthly'], atol=1e-16)
    np.testing.assert_array_equal(model.mu_arith_ann, snapshot.mu_arith_ann)
    assert not model.cov_ann.flags.writeable
    from scripts.build_v8_release import _model_validation
    assert _model_validation(model, method, snapshot.tickers) == 68


def test_builder_validates_and_preserves_existing_output(tmp_path):
    out = tmp_path / 'calibration.json'
    assert calibration.main(['--out', str(out)]) == 0
    original = out.read_bytes()
    assert calibration.main(['--out', str(out)]) == 2
    assert out.read_bytes() == original
