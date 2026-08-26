# CivicNexus — product definition

**One line:** Autonomous casework, accountable by design.

**Category:** A governed fleet of AI agents that runs long-lived, compliance-critical document
workflows end to end — demonstrated on municipal building permits.

**Hackathon framing:** Fortified Enterprise Fleet track. The "unlikely hero" is a city permit
clerk. The twist: governance is not a checkbox bolted on at the end — it is the product.

---

## 1. The problem

A building permit is a multi-department decision (zoning, fire/safety, health, public works)
made from messy inputs (scanned PDFs, half-filled forms, photos of floor plans) under written
rules (the municipal code), stretched across weeks of silence while applicants respond.

Today the permit clerk is the human message bus: they print, check completeness, route the
file to each department in sequence, relay every question to the applicant, and re-read
everything each time a reply lands. Median cycle times run to months. Decisions are poorly
documented, which makes appeals and records requests painful. Nobody in this loop is lazy —
the workflow itself is the bottleneck.

### The vignette (use this everywhere)

Maria wants to convert her garage into a small bakery. She emails the city a half-filled form
and a crooked phone photo of a floor plan. Today: three months of inbox hops. With CivicNexus:
the intake agent reads her documents the day they arrive, emails her about the one missing
form, and the coordinator dispatches zoning, safety, and health review agents in parallel.
Each agent checks her application against the actual municipal code and drafts a determination
citing the exact code sections. When Maria replies twelve days later, the system resumes with
full memory. The final decision lands on the clerk's console with the reasoning attached; the
clerk reviews and clicks approve. Days, not months — with receipts.

## 2. What it does (the workflow it handles)

The full lifecycle of a case:

1. **Intake** — parse messy uploaded/emailed documents into a structured application.
2. **Completeness triage** — same-day contact to the applicant for anything missing.
3. **Review planning** — coordinator looks up which department reviews this permit type
   requires by querying the agent registry, then dispatches specialist agents in parallel.
4. **Grounded determinations** — each specialist agent evaluates against the municipal code
   and must cite the exact code sections supporting its conclusion.
5. **Verification** — an automated groundedness gate checks every citation exists and
   actually supports the decision before anything proceeds.
6. **Asynchronous correspondence** — timers and persistent memory carry the case across
   weeks of applicant silence; a reply resumes the case instantly with full context.
7. **Human approval** — anything official or irreversible (denial, issuance, official
   letters) requires a clerk's sign-off in the console.
8. **Issuance and audit** — every decision, agent action, and reasoning chain is recorded
   in an immutable, exportable audit trail.

## 3. What it solves

| Pain today | Outcome with CivicNexus |
|---|---|
| Months of cycle time | Days: parallel review, same-day intake response |
| Opaque decisions | Every determination cites the governing code section, traceable end to end |
| Clerk as router and researcher | Clerk as judge: human touches only where judgment matters |
| Fraud and manipulation risk | All content screened inline for prompt injection and data leakage |
| Context lost across weeks | Durable sessions and long-term memory; nothing is re-read from scratch |
| Audit and records-request pain | Machine-generated, immutable reasoning trail per case |

**End goal in one line:** shrink decision time from months to days while making every decision
*more* auditable than the manual process was — moving the human from coordination to judgment.

## 4. Who it's for

- **Primary user:** the permit clerk / permit technician (operates the console, owns approvals).
- **Beneficiaries:** applicants (speed, transparency), department reviewers (pre-analyzed cases).
- **Buyer:** city administrator / CIO (throughput, compliance posture, audit readiness).

## 5. What it is NOT

- Not a chatbot. Value is measured in completed cases, not conversations.
- Not automated government. No irreversible action ever executes without a named human's
  recorded approval.
- Not a replacement for statutory authority. Agents draft and verify; humans decide.
- Not a general assistant. It is a workflow platform with a narrow, deep wedge.

## 6. How to say it

**Ten seconds:** "Autonomous casework, accountable by design."

**Non-technical (30s):** "You know how a building permit takes months? It's not laziness —
your file sits in five inboxes and one clerk carries it between them by hand. We built a
system where the file walks itself: a team of AI workers reads your application the day it
arrives, checks it against the city's actual rules, gets every department's review in
parallel, and chases missing paperwork — while the human clerk just reviews and approves the
final decision. Months become days, and every decision comes with receipts showing exactly
which rule it was based on."

**Technical (30s):** "A governed multi-agent platform for long-running, compliance-critical
document workflows, demoed on municipal permitting. Specialist ADK agents are published
through a versioned registry with an approval lifecycle and coordinated by a planner with
watchdog and circuit-breaker semantics. All agent-to-agent and agent-to-tool traffic flows
through a policy gateway enforcing per-agent identity, least-privilege access, and inline
Model Armor screening. State persists across weeks via Sessions and Memory Bank. Every
determination must carry RAG citations to the governing code, pass a groundedness verifier
before any side effect, and clear a human approval gate if irreversible — with end-to-end
OpenTelemetry traces and a published eval suite."

**Analogy:** an air-traffic-control tower for AI caseworkers — the registry holds the flight
plans, the gateway is the tower, and nothing lands (no side effect) without clearance.

## 7. Why this generalizes

Permitting is the wedge, not the product. CivicNexus fits any workflow with five properties:
documents arrive messy; written rules must be applied; multiple reviewers must weigh in; the
process has long silent gaps; and the final decision must be defensible to an auditor.
Adjacent domains with the same shape: insurance claims, loan underwriting, grant
administration, prior authorizations, visa and licensing casework.

## 8. Success metrics (north stars)

- Time to first applicant response (target: same day vs. weeks).
- End-to-end cycle time (target: days vs. months).
- Groundedness: % of determinations whose citations exist and entail the decision (target ≥95% first pass).
- Injection block rate on adversarial inputs (target: 100% of the drill corpus).
- Human minutes per case (judgment-only touches).
- Escalation precision: when the system asks a human, it was right to ask.

## 9. Judging alignment (internal note)

- **Innovation & operational utility (40%):** autonomous multi-week casework for an unlikely
  hero, with genuinely multi-agent structure justified by multi-department reality.
- **Architectural discipline (30%):** registry-governed fleet, zero-trust identity, gateway
  policy, verifier + watchdog failure recovery, published evals.
- **Demo & production readiness (30%):** one continuous unedited run hitting three moments —
  live registry hot-add, live prompt-injection block, twelve-day memory resume — plus visible
  Google Cloud proof and reproducible setup.
