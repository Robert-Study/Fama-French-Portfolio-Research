"""Hermetic release-builder smoke/contract tests; does not mock a passed production build."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/build_v8_release.py'
spec = importlib.util.spec_from_file_location('v8_release_builder', SOURCE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def _fixture(tmp_path, monkeypatch, *, bad_certificate=False):
    m = 68
    tickers = tuple(f'ETF{i:02d}' for i in range(m))
    snapshot = SimpleNamespace(as_of_date='2026-10-18', tickers=tickers)
    path = tmp_path / 'snapshot.joblib'
    joblib.dump(snapshot, path)
    ref_path = tmp_path / 'refs.json'
    ref_path.write_text(json.dumps({s: {tickers[i]:10000} for i,s in enumerate(builder.REFERENCES)}))
    masks = np.zeros((64,m), dtype=bool)
    for k in range(64):
        masks[k] = np.array([bool((k >> (i % 6)) & 1) for i in range(m)])
    sigma = np.eye(m)*0.001
    sigma[-1,:] = 0
    sigma[:,-1] = 0

    def prepare_model(snapshot, method):
        return SimpleNamespace(
            metadata=SimpleNamespace(method=method, canonical_tickers=tickers,cash_index=m-1),
            mu_arith_ann=np.full(m,0.04),mu_log_ann=np.full(m,0.039),
            cov_ann=sigma,param_uncertainty=(np.zeros((m,m)),np.zeros((m,m))),
            sleeve_masks=masks)

    def compute_miqp_frontier(model, n_points, mask_id):
        active = np.where(model.sleeve_masks[mask_id])[0]
        q = np.zeros((n_points, m), dtype=np.int64)
        q[:,active[0]] = 10000
        cert = np.full(n_points, not bad_certificate, dtype=bool)
        return {'q_bps':q, 'certified':cert,'gap':np.full(n_points,0.00004)}

    def accumulating_wealth_moments(w0, mu_log, cov_log, n_periods):
        n=float(n_periods)
        e=np.exp(n*mu_log+0.5*n*np.diag(cov_log))
        we=w0*e
        return float(we.sum()), max(0.,float(we @ np.expm1(n*cov_log) @ we))

    def lognormal_wealth_quantiles(mean,variance,horizon,c,u,confidence_levels):
        v2=math.log1p(variance/mean**2)
        lv=math.sqrt(v2+horizon*c+horizon*horizon*u)
        med=math.log(mean)-.5*v2
        return [math.exp(med+z*lv) for z in (-.8416212335729143,0.,1.)]

    pkg=types.ModuleType('portfolio')
    pkg.__path__=[]
    modules={'portfolio':pkg,
       'portfolio.model':types.ModuleType('portfolio.model'),
       'portfolio.optimise_miqp':types.ModuleType('portfolio.optimise_miqp'),
       'portfolio.wealth':types.ModuleType('portfolio.wealth')}
    modules['portfolio.model'].prepare_model=prepare_model
    modules['portfolio.optimise_miqp'].compute_miqp_frontier=compute_miqp_frontier
    modules['portfolio.wealth'].accumulating_wealth_moments=accumulating_wealth_moments
    modules['portfolio.wealth'].lognormal_wealth_quantiles=lognormal_wealth_quantiles
    for key, module in modules.items():
        monkeypatch.setitem(sys.modules,key,module)
    return path,ref_path


def test_release_smoke_hashes_and_masks(tmp_path,monkeypatch):
    snap, refs=_fixture(tmp_path,monkeypatch)
    out=tmp_path/'release'
    assert builder.main(['--snapshot',str(snap),'--references',str(refs),'--out',str(out),
                         '--masks','0,1,3','--n-points','3','--horizons','1,3']) == 0
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['production_complete'] is False
    assert len(manifest['tickers'])==68
    assert set(manifest['references'])==set(builder.REFERENCES)
    assert len(manifest['sha256'])==2*(1+3+3+1)
    for rel, digest in manifest['sha256'].items():
        assert hashlib.sha256((out/rel).read_bytes()).hexdigest() == digest
    for method in ('holdings','etf'):
        with np.load(out/f'frontiers/{method}/00.npz') as data:
            assert not data['certified'].any()
            assert np.isnan(data['gap']).all()
            assert data['q_bps'].shape==(3,68)
        with np.load(out/f'frontiers/{method}/03.npz') as data:
            assert data['certified'].all()
            assert (data['q_bps'].sum(axis=1)==10000).all()
        with np.load(out/f'wealth/{method}/03.npz') as data:
            assert data['moments'].shape==(3,2,5)
            assert np.isfinite(data['moments']).all()
        with np.load(out/f'wealth/{method}/references.npz') as data:
            assert data['moments'].shape==(6,2,5)


def test_release_rejects_uncertified_and_publishes_nothing(tmp_path,monkeypatch):
    snap,refs=_fixture(tmp_path,monkeypatch,bad_certificate=True)
    out=tmp_path/'release'
    with pytest.raises(builder.ReleaseContractError,match='uncertified'):
        builder.main(['--snapshot',str(snap),'--references',str(refs),'--out',str(out),
                      '--masks','1','--n-points','3','--horizons','1'])
    assert not out.exists()


def test_missing_snapshot_fails_closed(tmp_path):
    with pytest.raises(builder.ReleaseContractError,match='Missing trusted release input'):
        builder.main(['--snapshot',str(tmp_path/'does-not-exist.joblib'),
                      '--references',str(tmp_path/'refs.json'), '--out',str(tmp_path/'release'),
                      '--masks','1','--n-points','3','--horizons','1'])


def test_requires_solver_mask_selector():
    def unsafe_frontier(model,n_points):
        return {}
    with pytest.raises(builder.ReleaseContractError,match='mask selector'):
        builder._solve_frontier(unsafe_frontier, SimpleNamespace(sleeve_masks=np.ones((64,68),bool)),
                                1,3,method='etf',m=68)


def test_integer_budget_gate():
    raw={'q_bps':np.full((3,2),5000.,dtype=float),'certified':np.ones(3,bool),'gap':np.zeros(3)}
    with pytest.raises(builder.ReleaseContractError,match='integer basis points'):
        builder._extract_frontier(raw,2,3,method='holdings',mask=1)
