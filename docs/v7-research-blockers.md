# Remaining blockers — 14 October 2026

This research delivery is complete as a dated evidence handoff, **not completion of every requested data gate or of the application**. No new production admission, FF5 regression, company diversity calculation or leveraged simulation was performed.

| Gate | What changed | Remaining precise input/action |
|---|---|---|
| Historical GBP RF | 7,523 BoE SONIA observations acquired and supplied under database reuse terms | Monthly compounding, holiday/boundary validation and official compounded-index reconciliation still need execution |
| 26 iShares histories | Actual NAV and fund-growth arrays acquired; 52 series audited for dates, positive values and month presence | Net total-return reconciliation, splits/distributions, exact currency and complete-month calendars; EMVL July–November 2018 growth gap; IWFS strategy transition |
| Vanguard benchmarks and seven other classes | All selected product pages accessible, identities/current fees and export controls investigated | Full maximum-range actual NAV exports; distributions for seven income classes. Published download counts are not acquired observations |
| XS2D fixed reference | Exact class/index/factsheet identified | Full actual daily NAV, current binding financing/reset rules and compatible underlying/funding/FX; no silent replacement |
| Other equities | SPDR, Invesco, JPM and WisdomTree official routes investigated | Complete actual files and executed regional/mixed FF5 calibration; not mock betas |
| Bonds | iShares dated yield/duration fields retained; Vanguard and SPDR fields located | Real versus nominal yield basis, credit/default assumption, spread duration, hedge cost and convexity where available. Curve roll-down cannot be inferred from a single duration/YTM |
| Futures commodities | Separate swap/collateral legal structures and fee components identified | Current exact index version/roll policy/collateral remuneration, full actual history, cost reconciliation; no gold substitution |
| Daily leverage | Four exact candidates reviewed at source-route level; 3QQQ intraday threshold and 3LUS swap-rate field identified | Binding complete contracts, native funding spread/reference, actual overlap and reset-path data. LQQ attempted prospectus failed PDF validation. Exclude unreliable daily-close forecasts explicitly |
| Holdings | Public iShares metadata and SPDR daily XLSX link identified | Full dated economic holdings, identifier mapping, recursive funds and >=95% company coverage. No fund-position count masquerading as diversity |
| Savings | Charter dated quote retained; three official alternatives retrieved | Refresh terms before use; alternatives not fully audited for every eligibility/no-linked-account condition |
| Trading 212 | Original public catalogue references preserved | Account-specific eligibility not checked; standalone bank deposit is explicitly outside T212 |
| Dashboard failure | No evidence collected that a source gap caused a runtime failure | Coding agent must use hosted traceback and runtime/cache versions |

## Scientific limits that additional scraping will not remove

FF5 is an estimated explanatory model, not a guarantee of future premiums. Regional proxies do not fully span country, sector or currency exposures. Index changes and fund mergers require regime/provenance treatment. A neutral commodity premium is an assumption. Intraday leverage events cannot be reconstructed reliably from daily closes alone. Incomplete company mapping cannot support a precise diversity headline. Longer horizons reduce sampling variability of average returns under a chosen process but do not remove uncertainty about that process.

## Practical next coding task

Integrate the verified iShares HTML acquisition and supplied SONIA observations, reconcile actual net monthly GBP returns, execute chronological FF5 fits for the eligible selected equity classes, and acquire the exact Vanguard benchmark exports. Preserve the fixed references and show explicit unavailable forecast fields where a gate remains unresolved. Include the ledger, source hashes, data dates, formulas, calibration outputs and exclusions in the app's ZIP export. Render the calibration memo's Introduction/Methods/Conclusion as the scientific methods page, with implementation status separate from methodological proposals.
