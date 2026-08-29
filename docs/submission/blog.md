# We shipped a failing grade on our own public page

### What building a governed agent fleet for municipal permits taught us about honesty as an engineering practice

*I created this piece of content for the purposes of entering this hackathon.*

---

If you open our project's evaluation page right now, the first number you see is
red. Decision accuracy: **75%**. The gate is 85%. It says **FAIL**, in the
table, on a public URL, with every failing case named by id.

We could have deleted that page, or moved the threshold to 70% — four seconds
of work, and nobody would ever have known. We did neither, and that turned out
to be the most useful engineering decision we made.

## The thing we built

CivicNexus runs municipal permit casework end to end with a fleet of AI agents.
A person wants to convert their garage into a small bakery. They email the city
a half-filled form and a crooked phone photo of a floor plan. Today that file
enters a queue of inbox hops and waits — often through weeks or months of
backlog — for an answer the municipal code already determines.

The clerk who eventually decides isn't slow. The clerk is a message bus: they
check completeness, route the file to zoning and fire and public works in
sequence, relay every question to the applicant, and re-read the whole thing
each time a reply lands. Their day is reading and routing. It is almost never
deciding.

So we gave the reading to machines. Attachments are screened before any model
sees them, transcribed by a deterministic OCR engine, then screened again as
plain text. A coordinator agent triages the case and fans out to specialist
reviewers. Every determination must quote the municipal code verbatim, and a
verifier checks those quotes byte-for-byte against the committed corpus text.
Then the case **stops**, and only a named human can approve, deny, issue, or
close it — enforced not by a UI convention but by a write-once approval record
that the data store itself checks inside its transition guard. A permit
literally cannot exist without a row naming who signed it.

The pitch is one sentence: **autonomy everywhere except the signature.**

Measured on the deployed system, an application with a floor-plan attachment
went from arrival to a verifier-passed, code-cited recommendation sitting at
the human gate in about **62 seconds**.

## The red gate we refused to hide

We built a benchmark of twenty verified permit cases, and its accuracy gate was
set at 85% in the architecture spec — before any run had produced a score. Then,
run after run, the system measured 80%, 70%, 80%, 65%, 70% — and two of those
numbers came from *the same configuration on the same day*. At temperature zero.
In a file whose own comment reads "a legal reviewer must be deterministic:
identical facts, identical ruling."

It wasn't.

The pull toward making that number go away is strong. Average the runs. Report
the best one. Retire the two cases that keep flipping. Change 85 to 70 and call
it "calibrated to observed performance."

We had a rule written down before any of this: *never lower a threshold to pass
a gate; fix the system, or write the failure down honestly.* So the red number
stayed on the public page for weeks while we worked. Every visitor could see we
were failing our own bar.

That turned out to matter, because a number you can't hide is a number you have
to explain.

## The freeze-eve defect hunt

The day before our internal freeze we added something unglamorous:
artifact-level failure recording. Not a metric — just the ability to open one
failing case and read what the pipeline did to it.

The bug fell out in about twenty minutes. The intake agent's instruction still
enumerated exactly **one** permit type, left over from the first week of the
build. Any application outside that one type silently missed a configuration
lookup. The verifier's legality check then failed *every* outcome for those
cases — and, worse, wrote a misleading critique that corrupted the retry,
measurably flipping one correct finding into a wrong one.

Weeks of "the model is being weird" was a stale list in a prompt.

We fixed it. The twelve-case continuous-integration subset went **12/12, three
consecutive times**. That gate is green now.

And the honest boundary of that fix showed up in the same run: the eight harder
held-out cases measured 3 of 8. So the headline stayed red at 75%, but the
failure had moved somewhere much more interesting — out of "our plumbing is
broken" and into a clean, symmetric taxonomy of model judgment. Over-asking:
requesting more information when the stated facts already decide the case.
Over-deciding: denying when a decision-critical fact is genuinely absent. Five
cases, each named, each reproducible.

## Measuring our way to the truth

With a real taxonomy in hand we ran two experiments, both with the pass/fail
rule pinned *before* the run so the result couldn't be read backwards.

**Experiment one: a bigger model at the decision step.** A statute-level study
predicted exactly two of the five misses were model-fixable. Both converted.
And the bigger model scored **exactly the same 15 of 20** — it regressed a case
that had always been solid and failed another on output format, while dropping
citation groundedness below its gate and running about 50% slower. Measured
conclusion: model tier is not our constraint — a finding we could only earn by
predicting first and running second.

**Experiment two: take the decision away from the model entirely.** We encoded
fourteen statute sections as eighty-two explicit elements and let code compose
the outcome from a fact sheet the model extracted. Offline it passed 20 of 20,
including every case that had ever wobbled. Live, it measured **11 of 20** and
was reverted under the threshold we'd pinned in advance. The rules were right;
the extraction over-engaged sections that didn't apply, whose absent elements
then drove a flood of unnecessary information requests.

Both runs are archived. Neither ships. Between them they handed us something
better than a green number: the frontier is **which sections the reading
engages**, not how the decision composes — now written down as the next
problem, with its measurement plan attached.

## Meanwhile, the system defended itself

The part of the demo people react to hardest isn't the permit. It's a drill
email carrying hostile override instructions hidden **only as pixels in a
screenshot** — verifiably absent from the file's bytes.

The image was transcribed by OCR, the resulting text was screened, matched at
high confidence, and the case went straight to quarantine with the bytes held
in a locked bucket, an incident raised, and a single trace id linking all three
audit events.

No model was ever called. No human was ever asked. It was attacked and it
decided alone — and the incident is sitting on the public console for anyone to
look at.

## What a permit office actually gets

Not "AI decides your permit." A permit office gets the reading done in a minute
instead of a month; a determination that quotes the governing section
verbatim, with a machine-checked receipt that the quote is real; a screening
layer that blocked 14 of 15 drill documents before any model saw them; and an
audit trail where every issued permit names the human who signed it.

And a vendor whose evaluation page shows a failing number.

That last one isn't a confession — it's the specification. A system that
decides things about people's property has to be judged by numbers it cannot
edit. Every run behind ours is archived in the repository — the only kind of
claim worth making.

Judge us by re-running us.

---

**Live console (public, read-only):**
https://civicnexus-console-wrhx6s33dq-uc.a.run.app
**Repository:** `<REPO URL>`
**Video (4 min):** `<YOUTUBE URL>`

*Built for Google's All Things Agentic Hackathon, Fortified Enterprise Fleet
track, on Vertex AI Agent Engine with ADK, Gemini, Gemma, Cloud Vision and
Model Armor. All data shown is synthetic; the adversarial fixtures are
synthetic screening-drill inputs that exist solely to validate CivicNexus's own
guardrails.*
