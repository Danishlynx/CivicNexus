"""Deploy any fleet agent to Agent Engine under its own service account.

Generalizes the caseflow deploy: CLI source-build (the tracing-capable path,
ADR-001 item 9) plus per-agent identity via `.agent_engine_config.json`
(ADR-003 decision 2). After deploy the bound SA is VERIFIED against the spec;
if the CLI validator dropped it (spike: client validators can lag the
platform), the script PATCHes `spec.service_account` via raw REST and
re-verifies — deploys never silently run under the default service agent.

Usage:
  uv run python scripts/deploy_agent.py --agent-dir agents/safety/src/safety_agent \
      --display-name civicnexus-safety --service-account sa-safety \
      [--needs-corpus] [--state-file .deploy/safety_agent.json]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CORPUS_DISPLAY_NAME = "civicnexus-municipal-code"


def _resolve_corpus(project: str, region: str) -> str:
    import agentplatform

    client = agentplatform.Client(project=project, location=region)
    for corpus in client.rag.list_corpora().rag_corpora or []:
        if corpus.display_name == CORPUS_DISPLAY_NAME and corpus.name:
            return str(corpus.name)
    raise SystemExit(f"deploy_agent: corpus {CORPUS_DISPLAY_NAME!r} not found")


def _rest(project_number_path: str, region: str, method: str, body: Any = None) -> Any:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default()
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{project_number_path}"
    response = session.request(method, url, json=body)  # type: ignore[no-untyped-call]
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-dir", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--service-account", required=True, help="short SA name, e.g. sa-safety")
    parser.add_argument("--needs-corpus", action="store_true")
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()

    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("deploy_agent: PROJECT_ID env var is required", file=sys.stderr)
        return 1
    agent_dir = Path(args.agent_dir)
    sa_email = f"{args.service_account}@{project}.iam.gserviceaccount.com"
    state_file = Path(args.state_file)

    env_lines = [f"MODEL_ID={os.environ.get('MODEL_ID', 'gemini-3.5-flash')}\n"]
    if args.needs_corpus:
        env_lines.append(f"CORPUS_NAME={_resolve_corpus(project, region)}\n")
        env_lines.append(f"RAG_LOCATION={region}\n")
    if os.environ.get("REGISTRY_URL"):
        env_lines.append(f"REGISTRY_URL={os.environ['REGISTRY_URL']}\n")
    if os.environ.get("REGISTRY_MODE"):  # B-007 interim: firestore read path
        env_lines.append(f"REGISTRY_MODE={os.environ['REGISTRY_MODE']}\n")
    (agent_dir / ".env").write_text("".join(env_lines), encoding="utf-8")
    (agent_dir / ".agent_engine_config.json").write_text(
        json.dumps({"service_account": sa_email}, indent=2), encoding="utf-8"
    )

    cmd = [
        "uv",
        "run",
        "adk",
        "deploy",
        "agent_engine",
        f"--project={project}",
        f"--region={region}",
        f"--display_name={args.display_name}",
        "--otel_to_cloud",
    ]
    if state_file.exists():
        engine = json.loads(state_file.read_text(encoding="utf-8-sig"))["resource_name"]
        cmd.append(f"--agent_engine_id={engine.rsplit('/', 1)[-1]}")
        print(f"deploy_agent: updating {engine}")
    cmd.append(str(agent_dir))

    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=900)
    sys.stdout.write(completed.stdout[-2000:])
    sys.stderr.write(completed.stderr[-2000:])
    if completed.returncode != 0:
        print("deploy_agent: CLI deploy failed", file=sys.stderr)
        return 1
    names = re.findall(
        r"projects/[\w-]+/locations/[\w-]+/reasoningEngines/\d+",
        completed.stdout + completed.stderr,
    )
    if not names:
        print("deploy_agent: could not parse resource name", file=sys.stderr)
        return 1
    resource = names[-1]
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(
        json.dumps({"resource_name": resource, "project": project, "region": region}, indent=2),
        encoding="utf-8",
    )

    # Verify the identity actually bound; never run silently as the default SA.
    spec = _rest(resource, region, "GET")
    bound = spec.get("spec", {}).get("serviceAccount", "")
    if bound != sa_email:
        print(f"deploy_agent: SA not bound by CLI (got {bound!r}); patching via REST")
        _rest(
            f"{resource}?updateMask=spec.service_account",
            region,
            "PATCH",
            {"spec": {"serviceAccount": sa_email}},
        )
        spec = _rest(resource, region, "GET")
        bound = spec.get("spec", {}).get("serviceAccount", "")
        if bound != sa_email:
            print(f"deploy_agent: FAILED to bind {sa_email}; spec has {bound!r}", file=sys.stderr)
            return 1
    print(f"deploy_agent: {resource} running as {bound}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
