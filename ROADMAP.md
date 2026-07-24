# Signal Scout — Roadmap

Status legend: [shipped] done in this release · [next] highest priority · [later] valuable but not blocking.

## Shipped in the Cory-ready release

- [shipped] Automated digests: the backend now sends on its own (in-process `DigestScheduler`), with interval-based cadence (daily / every 3 days / weekly) that never double-sends within a window. Cory does not have to trigger anything.
- [shipped] Digest tab shows the real, rotating "up next" list subscribers receive (approved + contactable, verified-tier backfill), advancing past everyone already featured — no more static top-8.
- [shipped] Pipeline reliability: exhausted recipes re-scan after their cadence window, one recipe can't drain a provider's shared daily budget, and skipped runs report a clear reason instead of silent zeros.
- [shipped] Operator controls (recipe approve/run, digest send/generate) are gated behind `ADMIN_SECRET`; the public UI is safe to share.
- [shipped] Browser-tab favicon and product metadata.

## Next

- [next] Feedback-driven ranking: fold subscriber 👍/👎 (`feedback_votes`) back into scoring so the digest learns what Cory trusts. Today votes are stored but unused by `backend/scoring/`.
- [next] Exa result-quality tuning: once `EXA_API_KEY` is live, review admitted Exa candidates and tighten `_exa_tier` / confidence gates so semantic-web leads match the bar of PDL/Coresignal discoveries.
- [next] Decommission the redundant Railway `digest-cron` service now that in-process scheduling is idempotent (or keep it purely as a backstop and document that choice). Confirm no duplicate sends.
- [next] Provider budget visibility: surface per-provider remaining daily/monthly credits and a low-budget warning in the Pipeline cost dashboard, plus an alert before a scheduled run silently skips on `budget_exhausted`.

## Later

- [later] Subscriber preferences page: let subscribers change cadence and signal interests via a signed link (backend already stores `preferences` and cadence).
- [later] Richer warm-intro paths: expand `graph_edges` coverage and the "orbit / intro" context so more digest entries include an actionable intro route.
- [later] Digest send observability: persist per-send receipts/failures (Resend message ids are already captured) and show a delivery log in the Digest tab.
- [later] Horizontal-scale readiness: move the in-memory rate limiter (`backend/api/routes.py`) and schedulers to shared storage / a single leader if the API ever runs more than one instance.
- [later] Concentration insights in the digest: use the existing concentration detector to flag overrepresented schools/regions directly in Cory's digest.
