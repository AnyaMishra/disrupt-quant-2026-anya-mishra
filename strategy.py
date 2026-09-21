"""Sector-neutral carry, risk-weighted and volatility-targeted.

Hypothesis
----------
`carry_score` is a slowly varying asset characteristic. Within a sector,
assets with a higher characteristic earn a higher subsequent return than
their peers. The premium is a compensation-for-holding effect, not a
price-history effect: it is absent in the sector-average component of the
signal and grows with the forecast horizon rather than decaying.

Construction
------------
smoothed carry -> cross-sectional z -> demean within sector ->
divide by realized 20d volatility -> normalise to gross 1 ->
scale to a 6% ex-ante annualised volatility target.

The book is dollar-neutral and sector-neutral by construction, so the
engine's net-exposure and sector-net limits are satisfied without clipping.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CARRY_SMOOTH = 5        # sessions; flat across 3-40, see research note
COV_WINDOW = 60         # sessions used for the ex-ante covariance
VOL_TARGET = 0.06       # annualised
MAX_GROSS = 2.0
MIN_GROSS = 0.25
MAX_WEIGHT = 0.19       # engine clips at 0.20; stay inside it
LOOKBACK = 120          # sessions of history actually needed

_SECTORS: dict = {}


def _recent(history, current_date, n_sessions):
    dates = history["date"].drop_duplicates().sort_values()
    cutoff = dates.iloc[-n_sessions] if len(dates) > n_sessions else dates.iloc[0]
    return history.loc[history["date"].between(cutoff, current_date)]


def generate_positions(history, current_date):
    window = _recent(history, current_date, LOOKBACK)
    if window.empty:
        return {}

    if not _SECTORS:
        _SECTORS.update(window.groupby("asset_id")["sector"].first().to_dict())

    carry = window.pivot(index="date", columns="asset_id", values="carry_score")
    carry = carry.rolling(CARRY_SMOOTH, min_periods=1).mean().iloc[-1]

    latest = window.loc[window["date"] == current_date].set_index("asset_id")
    if latest.empty or carry.isna().all():
        return {}
    carry = carry.reindex(latest.index).astype(float)
    if carry.notna().sum() < 4:
        return {}

    spread = carry.std()
    if not np.isfinite(spread) or spread < 1e-12:
        return {}
    score = (carry - carry.mean()) / spread

    # Remove the sector-average component: it carries no alpha and only
    # consumes the 50% sector-net budget.
    sectors = pd.Series({a: _SECTORS.get(a, "?") for a in score.index})
    score = score - score.groupby(sectors).transform("mean")

    asset_vol = latest["realized_vol_20d"].astype(float).clip(lower=1e-3)
    score = (score / asset_vol).fillna(0.0)

    gross = score.abs().sum()
    if not np.isfinite(gross) or gross < 1e-12:
        return {}
    weights = score / gross

    weights = weights * _vol_scalar(window, weights)
    weights = weights.clip(-MAX_WEIGHT, MAX_WEIGHT)
    weights = weights - weights.mean()   # restore exact dollar neutrality

    return {a: float(w) for a, w in weights.items() if np.isfinite(w) and abs(w) > 1e-6}


def _vol_scalar(window, weights):
    """Leverage that puts the book at VOL_TARGET using a sample covariance."""
    closes = window.pivot(index="date", columns="asset_id", values="close")
    returns = closes.pct_change().tail(COV_WINDOW).dropna(how="all")
    if len(returns) < 20:
        return 1.0
    cov = returns.reindex(columns=weights.index).cov().to_numpy()
    w = weights.to_numpy(float)
    variance = float(w @ np.nan_to_num(cov) @ w)
    if not np.isfinite(variance) or variance <= 0:
        return 1.0
    ex_ante = np.sqrt(variance * 252.0)
    return float(np.clip(VOL_TARGET / ex_ante, MIN_GROSS, MAX_GROSS))
