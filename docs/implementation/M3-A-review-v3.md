# M3-A v3 review — bounded R3b follow-up

Date: 2026-10-16. Decision: **R3a's original reproductions are fixed; one related
fallback error still blocks M3-A acceptance.** Preserve the successful changes.
No M3-B or later work is assigned.

## Verified evidence

The reviewer validated complete v3 provenance, current source equality, identity
`135042432c062d28493c36fd901526c839dfff83e847ed7315066149efccf2b6`,
and artifact SHA-256
`fcc72089fd5356c483b58dad7e7c625c92c718340f42ae01878e0a56d7e0942f`.
The catalog remains
`aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.
Accepted M0–M2 and M3-A v1/v2 evidence bytes are unchanged.

Independent required imports, configured real preflight (all five construction
checks and rendering), and `git diff --check` passed. Preflight output is at
`/tmp/bricksmith-m3a-review-preflight-v3.json`. The worker reports 236 full-suite
tests passed in 683.662 seconds. The reviewer started independent full discovery
and terminated it after reproducing R3b; the partial run is not a pass. Its log
is `/tmp/bricksmith-m3a-review-tests-v3.log`.

The change to the competing-writer test correctly retries the actual losing
operation instead of assuming which thread wins. The accepted staged-attempt
stale-base limitation remains unchanged.

## R3b — distinguish unpublished attempts from historical observations (P2)

Location: `intent_ledger.ledger_read`, issue snapshot fallback and selection of
`latest_status_assertion`.

Reproduced through ordinary APIs with a temporary workspace and synthetic unit
validator (no filesystem corruption or physics claim):

1. Commit an open issue in an upgraded tiny workspace.
2. Propose a `ledger_update_issue` setting it to resolved, but do not commit it.
3. Through operator intake, record that staged operation as a repair attempt,
   using its base as `observed_revision_id`. This ledger commit succeeds.
4. Read the ledger. The actual issue is still open, but the staged operation is
   inserted into `observations` as `historical_unverified_claim`, and is selected
   as `latest_status_assertion` with null status/revision. The valid committed
   open observation has been displaced by a known unpublished attempt.

Cause: `committed_operation_snapshot` returns `None` for several distinct cases.
The fallback treats the presence of any issue-update operation type as historical
observation evidence and then selects the last list entry as current attribution.
An operation can also update a different issue while carrying this issue unchanged.
That is not an observation of this issue either.

- [ ] Distinguish verified observation, known non-observation/unpublished attempt,
  genuinely unverified legacy observation, and missing/corrupt evidence. A failed
  snapshot lookup alone must not invent legacy observation provenance. Preserve
  explicit unknown/error handling for genuinely unavailable historical evidence.
- [ ] Candidate, blocked, discarded, failed, or aborted operations remain in repair
  history with their correct outcomes. They cannot become published issue-status
  observations merely because their intent includes an issue-update operation.
  A committed update to another issue is also not an observation of this issue.
- [ ] Derive latest status attribution from the selected sealed issue's actual
  observation revision and verified issue-specific source, not the last attempted
  operation or arbitrary fallback entry. Do not silently substitute older evidence
  for missing/corrupt latest evidence. Retain creation provenance and historical
  snapshots. No sealed revision rewrites or second mutable history store.
- [ ] Add tests for the exact staged-update reproduction, subsequent discard, and
  a committed operation updating a different issue then referenced as a repair of
  this one. Confirm current and historical reads retain the correct latest status
  assertion, while repair outcomes remain visible. Keep the original R3a tests.
  Assert the invariant for both ordinary issue updates and checker-policy issues;
  legacy unknown attribution must stay explicitly unknown.
- [ ] Remove the duplicate assignment of `claim_provenance.observations` while
  editing this same projection. Avoid unrelated refactoring.
- [ ] Run focused tests, final full discovery, imports, configured real preflight,
  and `git diff --check`. Update completion/read-contract docs as needed. Preserve
  all evidence and export a fresh M3-A v4 provenance artifact after final edits;
  validate complete/source/catalog identity. Send REVIEWER the evidence and stop.

M3-A/full M3 review gates stay open. No M3-B, provider calls, benchmark, downloads,
library mutation, commits, pushes, or cleanup. Previously accepted corrections
and transaction semantics stay intact.
