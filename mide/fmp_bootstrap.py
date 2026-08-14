"""Bridge a configured Streamlit FMP secret into Walter's provider resolver.

The news provider supports environment and top-level Streamlit secret lookup. Some
Streamlit deployments store service credentials in a named table. This module
normalizes those supported layouts without ever logging or returning the secret.
"""
from __future__ import annotations

import os

FMP_ENV_NAME = "FMP_API_KEY"
FMP_TOP_LEVEL_NAMES = (
    "FMP_API_KEY",
    "FINANCIAL_MODELING_PREP_API_KEY",
    "FMP_API",
    "FMP_KEY",
)
FMP_SECTION_NAMES = ("fmp", "FMP", "financial_modeling_prep", "FinancialModelingPrep")
FMP_SECTION_KEY_NAMES = ("api_key", "API_KEY", "key", "apikey")


def activate_streamlit_fmp_secret() -> bool:
    """Make an existing Streamlit FMP credential visible to NewsService.

    Returns only whether a credential is present. The value is never printed,
    persisted, or included in diagnostics.
    """
    if str(os.getenv(FMP_ENV_NAME, "") or "").strip():
        return True
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return False

    value = ""
    for name in FMP_TOP_LEVEL_NAMES:
        try:
            value = str(secrets.get(name, "") or "").strip()
        except Exception:
            value = ""
        if value:
            break

    if not value:
        for section_name in FMP_SECTION_NAMES:
            try:
                section = secrets.get(section_name, {}) or {}
            except Exception:
                section = {}
            for key_name in FMP_SECTION_KEY_NAMES:
                try:
                    value = str(section.get(key_name, "") or "").strip()
                except Exception:
                    value = ""
                if value:
                    break
            if value:
                break

    if not value:
        return False
    os.environ[FMP_ENV_NAME] = value
    return True
