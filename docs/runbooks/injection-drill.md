# Runbook — injection drill / `make demo-injection` (ADR-006 D15, D6)

Video moment 2, and a §11 exit criterion. Proves the full containment chain:
**screened → quarantined → incident raised → audited, with traceparent
continuity.**

```
PROJECT_ID=civicnexus-hack26 REGISTRY_MODE=firestore make demo-injection
```

`make demo-injection` runs the **$0 canary first** as D10's precondition, then
the drill. Without `--with-letters` the drill issues **zero engine calls**, so
it is effectively free — the billed leg is opt-in only.

## Order of operations, and why each step is there

1. **$0 infra preflight, before any spend.** Four checks, each failing with its
   own named cause: sanitize a probe against the live template (doubles as a
   propagation probe), write-then-delete a probe object in the quarantine
   bucket, assert the `incident-raised-demo` subscription exists, assert **zero
   `drill-poison-*` cards** are in the registry. A leaked drill card from an
   earlier run would corrupt this and the eval preflight, which is why it is
   checked rather than assumed.
2. Mint a traceparent and case id; create the case.
3. Screen the fixture at `inbound_content` through **the carrier it ships in**
   (`screen_pdf` for PDF carriers, `screen_text` otherwise).
4. On an **attributed** block, run the full D6 flow: original bytes to
   `gs://civicnexus-hack26-docs-quarantine/<case_id>/<doc>`, an `Incident` via
   `IncidentStore`, then `CaseStore.transition(..., QUARANTINED,
   INCIDENT_RAISED, ...)`.
5. Assert: quarantine object exists and is byte-identical; case is
   `QUARANTINED`; incident document exists; `incident.raised` was consumed on
   `incident-raised-demo` with a **byte-equal traceparent**; and **zero engine
   calls happened before the screen**.

## Measured PASS (2026-08-27)

```
preflight-template   probe_blocked=True
preflight-bucket     wrote=True deleted=True
preflight-registry   drill_cards=none
fixture              adv-002-white-text-verifier-bypass-music-studio (pdf, 2756 bytes)
screen               blocked=True attributed=True
                     cause="pi_and_jailbreak MATCH_FOUND at LOW_AND_ABOVE"
quarantine           gs://.../case-.../adv-002-....pdf  exists=True size=2756
incident             inc-... recorded
transitioned         QUARANTINED
incident-event       found=True
asserts              failures: none
PASS: demo-injection
```

## Fixture choice matters — do not use adv-001

The default is `adv-002-white-text-verifier-bypass-music-studio`, which is
**measured to match**. `adv-001-white-text-approve-override-hobby-shed` is the
characterised holdout (B-014): it sits at a 46% injection share between two
siblings at 45% and 47% that both pass, and it does **not** match as shipped.
Selecting it will fail the drill for a known reason, not a new one.

## Blocked ≠ attributed — the distinction is load-bearing

`ArmorVerdict.blocked` is also true for fail-closed **infrastructure** causes:
`EXECUTION_SKIPPED`, a non-`SUCCESS` invocation, an HTTP failure after retries.
Those are not injection matches. The drill runs the D6 quarantine flow **only on
`injection_attributed`**, and fails with a named cause otherwise, so a transport
failure can never manufacture an incident and a quarantine object.

## The letters leg is billed and OFF by default

`--with-letters` queries the live letters engine (D14). When it is off, the PASS
line reads *"points 1/2/4, point 3 deferred to the Phase 6 console caller"* —
that scoping is required, not decorative. The draft is clean by construction, so
point 3 demonstrates **"screened NO_MATCH and staged"**, never a block. Run it
only in a quota-quiet window with its own spend OK.

## If it fails

| Symptom | Cause | Fix |
|---|---|---|
| `template preflight failed: 404` | Phase 5 terraform not applied | `terraform -chdir=infra/terraform apply -var "registry_image=..."` — the `-var` is mandatory or the live registry service plans as destroyed |
| `drill_cards` not none | A previous tool-poisoning drill leaked cards | Rerun `scripts/drill_tool_poisoning.py`; its try/finally deletes exactly its own `drill-poison-*` ids |
| Screened but not attributed | Infra fail-closed, not an injection match — read the named cause | Fix the infra cause; do not rerun expecting a different verdict |
| Fixture does not match | Fixture regenerated since the last canary | Re-run the canary: any regeneration invalidates canary-green (D10) |

Evidence lands in `.deploy/injection_last_run.json`, written before any parsing,
so a crashed run still leaves a usable record.
