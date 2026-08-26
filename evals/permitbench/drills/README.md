# Screening-drill fixtures (ADR-006 D8)

Everything in this directory is **synthetic, defensive test content**: drill
fixtures whose only purpose is to verify that CivicNexus's own Model Armor
screening template (`civicnexus-armor`) and pipeline containment behave as
specified. Nothing here targets, probes, or is ever sent to any external
system; fixtures are generated from a separately seeded Faker instance
(`adv-###` id namespace) and carry canary strings per the repo fixture rules.

Composition (the 25 adversarial artifacts, by proof mechanism — ADR-006 D8):

- **15 injection fixtures** — 5 §9.1 variant families × 3 seeds. Denominator
  of the "injection block 15/15" gate, measured at the screening layer with
  per-filter attribution (pi_and_jailbreak / malicious_uri only).
- **4 contradictory + 3 out-of-scope cases** — engine-path cases with pipeline
  expectations (deny / request_info / escalate); double as negative controls
  (armor must NOT flag them). Never counted in the 15/15.
- **3 tool-poisoning cases** — lookalike registry cards exercised only by
  `scripts/drill_tool_poisoning.py` as registry-lifecycle rejections; never
  screened content.

Loader discipline: these fixtures load ONLY through the drills `DrillCase`
schema/loader used by `evals/drill_runner.py`. The measured PermitBench
instruments (`schema.py`, `load_all()`, `cases/`) never see this directory —
`make eval-full` is unaffected by anything here.
