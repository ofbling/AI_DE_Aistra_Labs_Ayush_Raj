# Reconciliation to the Legacy Finance Weekly Report

The CFO asked directly: "The weekly Finance report is what we publish
today and what the board sees. Reconcile to it." Divya's caveat, in the
same thread: don't treat it as gospel -- "we have been telling them for
eighteen months that it double counts and that it books sales on the
wrong day."

## What was tried

Reproduced the two specific bugs Divya described, using the real POS
data: grouped by `ingest_date` (the day a file landed) instead of the
true sale date, and did not deduplicate (the collector is documented as
at-least-once, so raw data carries ~2.1% exact duplicate rows). Both are
already fixed in the real pipeline -- `staging.pos_transactions` uses
`business_date` and is deduplicated. This reconstruction deliberately
undoes both, on purpose, to test whether doing so reproduces the
published numbers.

See `sql/reconciliation/legacy_report_reconstruction.sql` and
`sql/reconciliation/legacy_report_comparison.sql`, run via
`scripts/run_reconciliation.py`.

## What was found

Compared all 312 week x channel combinations in the published report
(78 weeks x 4 channels) against the reconstruction:

| Metric | Value |
|---|---|
| Weeks x channels compared | 312 |
| Average absolute % difference | 99.0% |
| Range | -82.9% to +801.6% |
| Correlation (legacy vs. reconstructed gross sales) | **0.005** |

A correlation of 0.005 is statistically indistinguishable from zero. If
the legacy report were genuinely derived from the real feeds -- even
through the exact two bugs it's suspected of having -- the week-to-week
pattern would still track the true underlying sales pattern, just at the
wrong magnitude or on the wrong date. It doesn't. The published figures
and the real sales figures move independently of each other.

**A second, independent piece of evidence, visible by eye in the channel
breakdown:** the direction of the mismatch is consistent within a
channel, not random.
- **GT** is reconstructed *higher* than the legacy figure in all 78 weeks
  (+41.7% to +801.6%), with zero exceptions.
- **ECOM** is reconstructed *lower* than the legacy figure in 76 of 78
  weeks (-1.7% to -82.9%).
- HORECA and MT show no such consistent direction -- they swing both
  ways, week to week.

This has a clean explanation once outlet distribution is factored in: GT
accounts for roughly half of Kestrel's outlets, ECOM for roughly 7%. A
report built from real transactions would show GT's sales consistently
dwarfing ECOM's, roughly in proportion to outlet count. Instead, all four
channels' legacy figures are drawn from the *same* numeric range every
single week, regardless of channel -- which is only consistent with each
channel's weekly figure being an independent random number, not a rollup
of real line items.

## Conclusion

The published figures do not reconcile to the raw feeds, even after
reproducing the specific two bugs the business itself has been
describing for eighteen months. The mismatch isn't a small, consistent,
explainable offset (which is what "double-counted, wrong day" would
predict) -- it's large, inconsistent in size, and uncorrelated with the
real sales pattern entirely. The channel-level bias pattern points at a
specific reason why: the legacy figures don't scale with actual channel
size at all.

This is reported as a finding, not treated as a pipeline defect to fix.
The honest conclusion: `legacy_finance_weekly_report.csv`'s figures do
not appear to be derived from the raw feeds through any transformation
this reconciliation could identify -- including the specific
transformation Divya's team has been describing for eighteen months.
This matches her own framing almost exactly: "nobody has ever proved it
either way because nobody has had the time to go back to the raw feeds."
Going back to the raw feeds is exactly what this reconciliation did, and
the two figures still don't agree -- not approximately, not directionally,
not at all.

**Recommendation:** don't force a match. Publish the pipeline's own
number (`sql/kpis/gross_sales_by_channel.sql` -- correctly deduplicated,
correctly dated) as the source of truth going forward, with this report
as the documented reason it differs from what's been published to the
board. Answers illustrative question 2 directly: yes, it differs, and
here is exactly why, with evidence rather than assertion.
