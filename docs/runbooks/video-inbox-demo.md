# Video-day runbook — the live inbox-to-permit loop

The 90-second beat: a real email starts the loop on camera; the console shows
the fleet working; a named human closes the case at the gate.

## One-time setup (before recording day)

1. Gmail app password: Google Account -> Security -> 2-Step Verification ->
   App passwords. Keep it OUT of files; it is typed into the terminal only.
2. Rehearse once end to end (billed - one engine intake + review, needs the
   standing spend OK). Time the fleet-review leg with a stopwatch; the shot
   list needs the real number.

## Terminal (start BEFORE recording; leave visible in the take)

```powershell
$env:PROJECT_ID='civicnexus-hack26'
$env:INBOX_EMAIL='<your gmail address>'
$env:INBOX_APP_PASSWORD='<app password>'   # typed, never saved
uv run python scripts/inbox_watcher.py --consume --watch-gmail --i-accept-billing
```

## Browser (the other half of the split screen)

Clerk console via the IAM proxy (separate terminal, started before recording):

```powershell
gcloud run services proxy civicnexus-console-clerk --region us-central1 --project civicnexus-hack26
```

Open the localhost URL it prints. The queue and case pages update themselves -
do not press F5 on camera.

## The take

1. Gmail compose (clean browser profile - no third-party branding on screen):
   send the prepared application in `data/fixtures/video_demo_email.txt`
   TO YOUR OWN ADDRESS with subject starting "Permit application".
2. Within ~10s the terminal logs "email queued" then "intake agent parsing".
3. The case appears in the queue by itself (RECEIVED -> TRIAGED); narrate the
   masthead pipeline while fleet review streams (~1-4 min measured at
   rehearsal - cut to the GCP consoles here: Cloud Run, Agent Engine, Trace;
   that footage is REQUIRED by the rules anyway).
4. The determination card lands with the verbatim citation + verified tag;
   the case pulses at the Human gate.
5. Click Approve -> Issue permit -> Close. Show the approvals row naming you
   (Firestore console or the case record).

## Fallback (network flake mid-take - B-003 history)

The clerk console's "New application" form feeds the SAME inbox queue: paste
the email body into the form and the loop continues identically minus the
Gmail hop. The watcher picks it up on the next 5s poll.

## Reset between rehearsals

Fixture cases created by rehearsals are ordinary cases; close or leave them -
but NEVER touch the pinned video-evidence cases
(`case-5ea037e64ef8`, `case-c50219ca5166`).
