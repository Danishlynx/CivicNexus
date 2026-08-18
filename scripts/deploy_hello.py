"""Deploy the hello agent to Agent Engine (Agent Runtime) via the Python SDK.

Deploy surface verified against live docs 2026-08-18 (ADR-001 item 5):
``vertexai.Client(...)`` + ``client.agent_engines.create(agent=AdkApp(...),
config={...})``, staging bucket required on the SDK path, tracing via
``AdkApp(enable_tracing=True)``. The exact shape of the *returned* object is
verified on first real deploy; attribute access below is defensive for that
reason.

Not idempotent by nature (create() makes a new instance every run), so a
recorded previous deploy blocks re-runs unless FORCE_NEW_DEPLOY=YES.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

STATE_FILE = Path(".deploy/hello_agent.json")

# Remote runtime must match the locally verified environment (uv.lock pins).
REMOTE_REQUIREMENTS = [
    "google-cloud-aiplatform[agent_engines,adk]==1.164.0",
    "google-adk==2.7.1",
]


def _resource_name(remote: Any) -> str:
    for attr in ("resource_name", "name"):
        value = getattr(remote, attr, None)
        if isinstance(value, str) and value:
            return value
    api_resource = getattr(remote, "api_resource", None)
    value = getattr(api_resource, "name", None)
    if isinstance(value, str) and value:
        return value
    raise AttributeError(f"could not find resource name on {type(remote)!r}; attrs: {dir(remote)}")


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("deploy_hello: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    if STATE_FILE.exists() and os.environ.get("FORCE_NEW_DEPLOY") != "YES":
        recorded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        print(
            f"deploy_hello: already deployed as {recorded.get('resource_name')} "
            f"(per {STATE_FILE}). create() would orphan it and bill a second instance.\n"
            "deploy_hello: set FORCE_NEW_DEPLOY=YES to deploy another, after deleting "
            "the old instance.",
            file=sys.stderr,
        )
        return 1

    import vertexai
    from hello_agent.agent import root_agent
    from vertexai import agent_engines

    # AdkApp reads project/location from the SDK's global config, not from the
    # Client — both must be initialized (observed on first deploy, SDK 1.164.0).
    vertexai.init(project=project, location=region)
    client = vertexai.Client(project=project, location=region)
    app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)

    print(f"deploy_hello: deploying hello_agent to {project}/{region} ...")
    remote = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "civicnexus-hello",
            "description": "Phase 0 walking-skeleton agent",
            "requirements": REMOTE_REQUIREMENTS,
            "staging_bucket": f"gs://{project}-agent-staging",
            "env_vars": {
                "MODEL_ID": os.environ.get("MODEL_ID", "gemini-3.5-flash"),
                # Gemini 3.x models do not serve from the us-central1 regional
                # endpoint on this project (probed 2026-08-18: HTTP 417 for all
                # regional model calls; global OK) — route model inference via
                # the global endpoint. Deployment + data remain us-central1.
                "GOOGLE_CLOUD_LOCATION": "global",
                # ADK tracing: AdkApp(enable_tracing=True) produced no traces on
                # runtime SDK 1.164.0 (verified empirically 2026-08-18); these
                # documented telemetry vars are the working mechanism.
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
            },
        },
    )

    name = _resource_name(remote)
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"resource_name": name, "project": project, "region": region}, indent=2),
        encoding="utf-8",
    )
    print(f"deploy_hello: deployed {name}")
    print(f"deploy_hello: recorded in {STATE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
