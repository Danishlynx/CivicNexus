# Permits take weeks. The answer is usually already in the code.

*I created this piece of content for the purposes of entering the All Things Agentic Hackathon.*

If you have ever applied for a building permit, you know the shape of it. You send in a form, maybe a scanned PDF and a crooked phone photo of your floor plan, and then you wait. Weeks. Sometimes months.

What bothered me is that the answer is usually already sitting in the municipal code. Somebody just has to read it, apply it to your facts, and write down which section says so.

That turns out to be most of the job. A clerk prints the file, checks it is complete, routes it to each department in turn, relays every question back to the applicant, and re-reads the whole thing every time a reply lands. Reading and routing. Almost never deciding.

So I built CivicNexus: a fleet of agents that does the reading, with a hard stop where a person does the deciding.

## What it does

An application arrives by email. If there are attachments, they are allowlisted, screened as raw bytes, transcribed by Cloud Vision, and screened a second time as plain text, all before any model sees them.

A coordinator agent triages the case and hands it to specialist reviewers. Every determination has to quote the municipal code word for word, and a verifier checks those quotes byte for byte against the committed corpus text. If a quote does not match, the case goes back with a critique and gets one retry. Either way the verifier's report travels with the case, pass or fail.

Then it stops. Only a named human, working through an IAM-gated console, can approve, deny, issue or close a case. Issuing writes a one-time row in Firestore naming who signed it, and the single-writer case store checks for that row inside the state transition itself. A permit cannot exist without a record of who approved it.

On the deployed stack, an application with a floor plan attached went from arriving to sitting at the human gate in about 62 seconds, with a verifier-passed recommendation citing the right section of the code.

## How it is put together

Four agents run on Vertex AI Agent Engine, built with Google's Agent Development Kit. Each one runs as its own service account with a custom least-privilege role, so agent-to-agent access is enforced by IAM rather than by prompt. A deliberate-deny test produced an audited 403, which is the kind of proof I wanted rather than a claim in a README.

Gemini 3.5 Flash does coordination, intake and review. Gemma 4 sits in the verification layer as a second opinion on one narrow question: when the fleet asks for more information instead of deciding, is that request actually warranted? I used a different model family on purpose, because the Flash-based check had measurably rubber-stamped that exact failure. Gemma has its own quirks, and I measured them rather than assuming: it is not deterministic at temperature zero (five identical calls flipped the verdict once), and it accepts a response schema without enforcing it. So the check only fires when two independent calls agree and the quote it produces verifies byte for byte.

Model Armor screens at four points. Cloud Vision does OCR at intake, which matters more than it sounds: OCR is a transcription engine, not a chat model, so text hidden in pixels cannot give it instructions. Firestore is the case store, the write-once inbox queue, the approvals ledger and the agent registry. Pub/Sub carries events, Cloud Tasks handles long timers, Cloud Run hosts the two consoles and the registry, Memory Bank handles recall across multi-week gaps, and everything is Terraform-managed.

There are two consoles, deliberately. The public one is read-only, and its service account holds exactly one Google Cloud role: `datastore.viewer`. It cannot write, cannot spend, cannot publish events, and cannot read a quarantined document, no matter what its code does. The clerk console, where approvals actually happen, is locked to one named person.

## The part I did not expect

I wanted to test whether the screening layer could be fooled by an image. So I built a drill: an email with a screenshot attached, where the hostile override text existed only as pixels. I byte-verified that the words were nowhere in the file.

The system caught it without anyone watching. Cloud Vision transcribed the image, the plain-text screen matched it at high confidence, and the case went from received to quarantined with the bytes locked in a private bucket, an incident opened, and a single trace id linking all three audit events. No model was ever called. No human was asked.

That is the moment the project clicked for me. Not that it drafts a permit decision in a minute, but that when something adversarial arrived mid-run, it decided on its own and contained it.

## The number I did not hide

The system's decision accuracy is 75% against my own 85% target. That gate is red, and it has been red on a public page for weeks. I never lowered the threshold to make it green, and the eval report renders unedited on the live site with every failing case named by id.

Publishing that number is what got it improved. Because the failure was visible, I kept digging, and the night before freeze I found a real bug rather than a model quirk: an instruction inside the intake agent still listed exactly one permit type from an early phase of the build. Anything outside that list missed a config lookup, which made the verifier's legality check fail every possible outcome, and its misleading critique then corrupted the retry. It measurably flipped one correct answer into a wrong one.

After that fix the CI subset went twelve for twelve, three runs in a row. The harder held-out cases still measure three of eight, which tells me exactly where the remaining problem lives: borderline statutory readings where two human reviewers would also disagree.

I also tried two things that did not work, and I am glad I measured them instead of guessing. Swapping in a bigger model at the decision step fixed two cases and broke two others, landing on the same score with worse latency. Rewriting the decision as a deterministic rules engine passed all twenty cases offline and then scored eleven live, because the problem moved upstream into which sections get pulled in. Both runs are archived in the repo. Neither is a claim I make.

## What I would tell someone starting this

Instrument the failures, not the successes. Weeks of "the model is being weird" dissolved the moment I recorded which specific check failed on which case. The bug was a stale list in a prompt, and no amount of prompt tuning would have found it.

Decide what counts as success before you run the experiment. Every measurement in this project had its threshold written down first. That is the only reason I could accept two negative results without arguing myself into a different interpretation.

And put the human in the one place that matters. The fleet does all the reading, all the retrieval, all the drafting, and defends itself when attacked. The only thing it cannot do is sign. For a system that issues government documents, that is not a limitation. It is the design.

## Links

- Live console (read-only, no login): https://civicnexus-console-wrhx6s33dq-uc.a.run.app
- Code, evals and every archived run: https://github.com/Danishlynx/CivicNexus
- Four-minute demo: https://youtu.be/8mWPskk6QUo

Built for the All Things Agentic Hackathon, Fortified Enterprise Fleet track. All data shown is synthetic. The municipal code corpus is one public chapter of the Monrovia, CA code, attributed in the repo.
