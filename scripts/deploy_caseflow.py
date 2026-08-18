"""Deploy the caseflow app via the ADK CLI (the tracing-capable path, ADR-001 item 9).

Resolves the corpus resource name, writes the agent-dir .env the CLI folds into
the runtime env, then creates or updates the Agent Engine instance in place.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path("agents/caseflow/src/caseflow_agent")
STATE_FILE = Path(".deploy/caseflow_agent.json")
CORPUS_DISPLAY_NAME = "civicnexus-municipal-code"


def _resolve_corpus(project: str, region: str) -> str:
    import agentplatform

    client = agentplatform.Client(project=project, location=region)
    listing = client.rag.list_corpora()
    for corpus in listing.rag_corpora or []:
        if corpus.display_name == CORPUS_DISPLAY_NAME and corpus.name:
            return str(corpus.name)
    raise SystemExit(f"deploy_caseflow: corpus {CORPUS_DISPLAY_NAME!r} not found - run seed_corpus")


def main() -> int:
    project = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    if not project:
        print("deploy_caseflow: PROJECT_ID env var is required", file=sys.stderr)
        return 1

    corpus_name = _resolve_corpus(project, region)
    (AGENT_DIR / ".env").write_text(
        f"CORPUS_NAME={corpus_name}\n"
        f"MODEL_ID={os.environ.get('MODEL_ID', 'gemini-3.5-flash')}\n"
        f"RAG_LOCATION={region}\n",
        encoding="utf-8",
    )
    print(f"deploy_caseflow: corpus={corpus_name}")

    cmd = [
        "uv",
        "run",
        "adk",
        "deploy",
        "agent_engine",
        f"--project={project}",
        f"--region={region}",
        "--display_name=civicnexus-caseflow",
        "--otel_to_cloud",
    ]
    if STATE_FILE.exists():
        engine_id = json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))["resource_name"]
        cmd.append(f"--agent_engine_id={engine_id.rsplit('/', 1)[-1]}")
        print(f"deploy_caseflow: updating {engine_id}")
    cmd.append(str(AGENT_DIR))

    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=900)
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        print("deploy_caseflow: CLI deploy failed", file=sys.stderr)
        return 1

    names = re.findall(
        r"projects/[\w-]+/locations/[\w-]+/reasoningEngines/\d+",
        completed.stdout + completed.stderr,
    )
    if not names:
        print("deploy_caseflow: could not parse resource name from CLI output", file=sys.stderr)
        return 1
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"resource_name": names[-1], "project": project, "region": region}, indent=2),
        encoding="utf-8",
    )
    print(f"deploy_caseflow: deployed {names[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
