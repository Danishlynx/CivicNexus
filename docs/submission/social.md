# Social posts

## LinkedIn (primary)

If you have ever applied for a building permit, you know the shape of it. You send a form and a floor plan, then you wait weeks. Usually the answer was already sitting in the municipal code. Somebody just had to read it.

So I built CivicNexus for Google's All Things Agentic Hackathon: a fleet of AI agents that does the reading, and a hard stop where a person does the deciding.

An application arrives by email. Attachments get screened, OCR'd by Cloud Vision, and screened again as plain text before any model sees them. Four agents on Vertex AI Agent Engine triage it, retrieve the relevant code, and draft a determination that has to quote the statute word for word. A verifier checks every quote byte for byte against the committed corpus. Measured end to end: about 62 seconds from email to a cited recommendation waiting for a human.

Then it stops. Only a named human can issue a permit, and issuing writes a one-time record naming who signed it. The permit cannot exist without that record.

The part I did not expect: I tested it with a screenshot where the hostile instructions existed only as pixels, nowhere in the file's bytes. It was transcribed, caught, and quarantined before any model was called and before anyone asked me.

One more thing. Its accuracy is 75% against my own 85% target. That gate is red, it is public, and I never moved the line. Publishing it is what got the underlying bug found.

Live console, code, and the four-minute demo are in the comments.

#AllThingsAgenticHackathon

---

## X / Twitter (276 characters)

Built CivicNexus: AI agents that read municipal code and draft permit decisions with verbatim citations, byte-verified. Email to human gate in 62s.

They can't sign. Only a named human can, and it's enforced in the data layer.

https://youtu.be/8mWPskk6QUo

#AllThingsAgenticHackathon

---

## First comment (LinkedIn, post links here)

Demo: https://youtu.be/8mWPskk6QUo
Live console (read-only): https://civicnexus-console-wrhx6s33dq-uc.a.run.app
Code and every archived eval run: https://github.com/Danishlynx/CivicNexus
