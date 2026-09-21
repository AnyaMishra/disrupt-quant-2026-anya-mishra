# Disrupt Quant 2026 — Sector-Neutral Carry

**Anya Mishra**

A dollar-neutral, sector-neutral long/short book that ranks assets on `carry_score`
within their own sector, weights them by inverse realized volatility, and scales the
whole book to a 6% ex-ante annualised volatility target.

| | Sessions | Ann. return | Ann. vol | Sharpe | Max DD | Calmar | Ann. turnover | Constraint adj. days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Development | 910 | 8.57% | 6.08% | 1.38 | −3.46% | 2.48 | 24.0× | 0 |
| Public validation | 132 | −0.78% | 6.25% | −0.09 | −5.06% | −0.15 | 27.6× | 0 |

The strategy was frozen before validation was run, validation was run once, and
nothing has been changed since. See `research_note.pdf` §6 for the diagnostics on
that result — in short, it sits ≈1.1 standard errors below the development estimate,
the signal went quiet rather than inverting, and five of six sectors were positive.

## Reproduction

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python starter/backtester.py                                  # development
python starter/backtester.py --split validation               # public validation
python starter/backtester.py --cost-multiplier 1.5            # cost stress
python starter/backtester.py --cost-multiplier 2.0

python validate_submission.py                                 # structure check
```

Results are written to `results/<split>/` as `daily.csv`, `attribution.csv` and
`metrics.json`. Everything is deterministic: no randomness, no network, no wall-clock
dependence, no state carried between periods beyond a sector lookup rebuilt on the
first call. Measured runtime is **0.03 s per decision** at full history depth, against
a 60 s limit.

### Research scripts

`research/` reproduces every number quoted in the note. These are **not** loaded at
evaluation time; only `strategy.py` is.

| Script | Produces |
|---|---|
| `01_signal_scan.py` | Rank-IC scan of all 18 features against three forward-return definitions |
| `02_stability_and_economics.py` | Yearly IC stability, quintile spreads, monotonicity, macro timing, decay |
| `03_reversal_cost_tests.py` | The four attempts to make 1-day reversal survive costs, all negative |
| `04_carry_construction.py` | Weighting schemes, sector decomposition, smoothing, gross scaling |
| `05_robustness_battery.py` | Newey-West t, permutation test, block bootstrap, risk-proxy checks |
| `06_vol_targeting.py` | Fixed gross vs. volatility targeting |
| `07_validation_diagnostics.py` | Post-validation diagnostics (run once, after freezing) |
| `08_build_research_note.py` | Builds `research_note.pdf` |

Run them from the repository root after at least one backtester run, since scripts
07 and 08 read from `results/`.

## Strategy summary

```
5-day mean of carry_score
  → cross-sectional z-score
  → demean within sector          (all the alpha is here; the sector-average part has none)
  → ÷ realized_vol_20d            (equalise risk, not dollars)
  → normalise to gross 1
  → × min(2.0, 6% / ex-ante vol)  (ex-ante vol from a 60-session sample covariance)
  → clip to ±19%, re-demean
```

Three parameters, none tuned to a peak: the smoothing window sits inside a flat region
(Sharpe 1.30–1.57 for any window from 1 to 90 sessions), and the covariance window and
volatility target are risk settings that move Sharpe by less than 0.02. Parameter
selection used an internal chronological split (fit 2021–2022, check 2023–2024 H1).

Constraints are satisfied by construction rather than by clipping, which matters
because the engine responds to a breach by scaling the entire weight vector down
instead of repairing the offending leg.

## Notable finding

The strongest signal in the dataset is **not** the one being traded. One-day reversal
on `return_1d` has a rank IC of −0.0475 (t = −6.54), roughly double carry's
significance — but its score has day-over-day autocorrelation of −0.04, forcing ~146%
of NAV of turnover per day. Gross alpha of 5.9 bps/day is consumed by 7.1 bps/day of
cost. Because spread dominates impact at $1M NAV, cost is close to linear in trade
size, so shrinking the book cannot rescue it. Tail-only construction, cost-aware
scoring and no-trade bands were all tested and all remained negative net.

Carry is the weaker signal that survives, because its autocorrelation of +0.994 means
it barely trades.

## Repository layout

```
strategy.py          # required entry point — the only file loaded at evaluation
README.md
research_note.pdf    # 2 pages
requirements.txt     # unchanged from the provided pinned set
research/            # research scripts, not loaded at evaluation
results/             # backtester output
data/, starter/, notebooks/   # unmodified challenge files
```

No `src/` or `artifacts/` directory: the strategy fits nothing offline and stores no
parameters, so there is nothing to serialise. No pickle or joblib files anywhere.

## AI disclosure

```text
AI tools used: Claude (Anthropic), via the Claude chat interface.

AI tools used: Claude (Anthropic), via the Claude chat interface.

How they were used: Extensively. I directed the workflow and made the
judgement calls — scope, which avenue to pursue, freezing before validation
and running it once, and declining to add a sector risk cap after seeing the
Energy loss. Claude generated the exploratory analysis, the feature scan, the
portfolio construction, the statistical tests, strategy.py, and the first
draft of the research note. I reviewed all of it and reproduced the results
via the scripts in research. Any strategical descisions were made and planned
by me, only utilizing Claude as my GitHub and VScode were running into many
unforseen issues which prevented it from working.

I can explain and defend every component of this submission.

Not AI-assisted: the decision to freeze before validation and to run it only
once; the decision not to add a sector risk cap after seeing the Energy loss;
and the final review of every claim and number in the submission.

All results were reproduced by running the scripts in research/ and the
provided backtester. No external code was copied. I am prepared to explain,
modify and defend every component above.
```
