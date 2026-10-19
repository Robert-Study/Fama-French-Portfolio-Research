"""Methods — canonical scientific Markdown, inspectable priors and model family."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import streamlit as st
try:
    import yaml
except ImportError:
    yaml = None
from ui.v8_shared import SPEC, RES, copy, source_hash

DOC = SPEC / "07_methods.md"
ASSUMPTIONS = RES / "02_assumptions.yaml"
CONTRACTS = RES / "02_product_contracts.json"


@st.cache_data(show_spinner=False)
def _text(path: str, digest: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    # Pass the content digest as a cache key; edits invalidate cached text.
    return _text(str(path), source_hash(path))


def _document() -> str:
    if not DOC.is_file():
        raise FileNotFoundError(DOC)
    return _read(DOC)


def _sections(markdown: str) -> list[tuple[str, str]]:
    # Keep the complete native Markdown, including equations and citations.
    lines = markdown.splitlines(keepends=True)
    starts = [(i, re.sub(r"^#{1,2}\s+", "", line).strip())
              for i, line in enumerate(lines)
              if re.match(r"^#{1,2}\s+", line)]
    if not starts:
        return [(copy("methods.document.title"), markdown)]
    chunks = []
    for number, (start, heading) in enumerate(starts):
        end = starts[number + 1][0] if number + 1 < len(starts) else len(lines)
        chunks.append((heading, "".join(lines[start:end])))
    return chunks


def _source_origin(item: dict) -> str:
    for key in ("evidence_category", "origin", "classification", "source_class", "type"):
        if item.get(key) not in (None, ""):
            return str(item[key])
    return copy("methods.assumptions.type.unverified")


def _assumption_records(data: Any, path: str = "") -> Iterator[dict[str, str]]:
    if isinstance(data, dict):
        # Recognise leaf-value objects; preserve original units and evidence
        # instead of labelling unsupported heuristics 'observed'.
        if "value" in data or "selected_value" in data:
            value = data.get("selected_value", data.get("value"))
            yield {
                copy("methods.assumptions.column.parameter"): path,
                copy("methods.assumptions.column.value"): str(value),
                copy("methods.assumptions.column.unit"): str(data.get("unit", "N/A")),
                copy("methods.assumptions.column.origin"): _source_origin(data),
                copy("methods.assumptions.column.date"): str(
                    data.get("as_of", data.get("effective_date", "N/A"))),
                copy("methods.assumptions.column.sensitivity"): str(
                    data.get("sensitivity", data.get("sensitivity_cases", "N/A"))),
            }
            return
        for key, obj in data.items():
            yield from _assumption_records(obj, f"{path}.{key}" if path else str(key))
    elif isinstance(data, list):
        for pos, obj in enumerate(data):
            yield from _assumption_records(obj, f"{path}[{pos}]")
    else:
        yield {
            copy("methods.assumptions.column.parameter"): path,
            copy("methods.assumptions.column.value"): str(data),
            copy("methods.assumptions.column.unit"): "N/A",
            copy("methods.assumptions.column.origin"):
                copy("methods.assumptions.type.unverified"),
            copy("methods.assumptions.column.date"): "N/A",
            copy("methods.assumptions.column.sensitivity"): "N/A",
        }


def _assumptions() -> None:
    st.subheader(copy("methods.assumptions.title"),
                 help=copy("methods.assumptions.help"))
    try:
        if yaml is not None:
            obj = yaml.safe_load(_read(ASSUMPTIONS))
        else:
            obj = {}
            for line in _read(ASSUMPTIONS).splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    obj[k.strip()] = v.strip().strip('"').strip("'")
        if not isinstance(obj, (dict, list)):
            raise ValueError("Assumptions file must contain a YAML mapping/list")
        register = pd.DataFrame(_assumption_records(obj))
        st.dataframe(register, hide_index=True, use_container_width=True)
    except (OSError, ValueError) as exc:
        st.error(copy("methods.sources.none")); st.code(str(exc))
    with st.expander(copy("methods.sources.instrument"), expanded=False):
        try:
            contracts = json.loads(_read(CONTRACTS))
            if not isinstance(contracts, (dict, list)):
                raise ValueError("Product contracts must be a JSON object or list")
            st.json(contracts, expanded=False)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            st.error(copy("methods.sources.none")); st.code(str(exc))


def _switch(context: dict) -> None:
    st.subheader(copy("methods.model.title"))
    selected = st.radio(copy("methods.model.label"), ("holdings", "etf"),
                        key="v8_method_pending",
                        format_func=lambda k: copy("methods.model." + k),
                        help=copy("app.method.help"), horizontal=True)
    st.caption(copy("methods.model.shared_help"))
    help_key = ("methods.model.holdings_help" if selected == "holdings"
                else "methods.model.etf_help")
    st.write(copy(help_key))
    change = selected != st.session_state["v8_method"]
    if change:
        st.warning(copy("methods.model.change_warning"))
    if st.button(copy("methods.model.change"), disabled=not change):
        prior = st.session_state["v8_method"]
        try:
            # Preflight alternate model; never set selector if artefact absent.
            alternative = context["load_model"](context["release"]["release_id"], selected)
            if getattr(getattr(alternative, "metadata", None), "method", None) != selected:
                raise ValueError("Alternate release model-family mismatch")
            if len(alternative.asset_ids) != len(context["tickers"]):
                raise ValueError("Alternate universe has incompatible asset mapping")
        except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
            st.error(copy("app.method.unavailable")); st.code(str(exc))
            st.session_state["v8_method"] = prior
        else:
            # q_bps, sleeve mask and saved comparison sets remain unchanged.
            st.session_state["v8_method"] = selected
            st.success(copy("app.method.switch_success")); st.rerun()


def _diagnostics(context: dict) -> None:
    st.subheader(copy("methods.diagnostics.title"),
                 help=copy("methods.diagnostics.help"))
    manifest = context["release"]
    pairs = {
        "release": manifest.get("release_id"),
        "snapshot": manifest.get("as_of"),
        "family": st.session_state["v8_method"],
        "code_hash": manifest.get("code_hash"),
        "data_hash": manifest.get("data_hash"),
        "instrument_count": len(context["tickers"]),
        "mapped_count": manifest.get("mapped_securities"),
        "company_count": manifest.get("mapped_companies"),
        "coverage": manifest.get("economic_exposure_coverage"),
        "covariance": manifest.get("covariance_validation"),
        "frontier": manifest.get("frontier_certification"),
        "projections": manifest.get("projection_validation"),
    }
    records = []
    for key, value in pairs.items():
        records.append({"Field": copy("methods.diagnostics." + key),
                        "Result": value if value is not None
                        else copy("methods.diagnostics.missing")})
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    with st.expander(copy("methods.sources.release")):
        st.json({"release_id": manifest.get("release_id"),
                 "methods_sha256": source_hash(DOC),
                 "interface_copy_sha256": source_hash(SPEC / "07_interface_copy.md"),
                 "assumptions_sha256": (source_hash(ASSUMPTIONS)
                                         if ASSUMPTIONS.is_file() else None),
                 "contracts_sha256": (source_hash(CONTRACTS)
                                       if CONTRACTS.is_file() else None)})


def _reader() -> None:
    st.subheader(copy("methods.document.title"),
                 help=copy("methods.document.help"))
    document = _document()
    sections = _sections(document)
    # Select actual chapter contents; no nonfunctional external hash links.
    chosen = st.selectbox(copy("methods.section.scope"),
                          list(range(len(sections))),
                          format_func=lambda i: sections[i][0],
                          key="v8_methods_section")
    st.markdown(sections[chosen][1])
    with st.expander(copy("methods.document.title")):
        st.markdown(document)


def render(context: dict) -> None:
    st.title(copy("methods.title")); st.write(copy("methods.subtitle"))
    _switch(context)
    _assumptions()
    try:
        _diagnostics(context)
        _reader()
    except (OSError, ValueError, KeyError) as exc:
        st.error(copy("app.error.invalid_data")); st.code(str(exc))
    st.subheader(copy("methods.contact.title"))
    st.write(copy("methods.contact.intro"))
    st.write(copy("methods.contact.email"))
    st.caption(copy("methods.contact.disclaimer"))
