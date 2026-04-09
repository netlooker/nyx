#!/usr/bin/env python3
"""Hybrid Nyx e2e harness for deterministic Sonar -> OpenClaw TUI -> Synapse."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "container" / "docker-compose.yml"
SECRETS_OPENCLAW = ROOT / "secrets" / "openclaw.json5"
SECRETS_QWEN = ROOT / "secrets" / "qwen-settings.json"
WORKSPACE_SYNAPSE_CONFIG = ROOT / "data" / "workspace" / "projects" / "synapse" / "config" / "synapse.toml"
ACTIVE_SYNAPSE_CONFIG = ROOT / "data" / "workspace" / "e2e" / "active-synapse.toml"
EXPECTED_NOTE_FILENAMES = [f"paper-{index:02d}.md" for index in range(1, 6)]
DEFAULT_QUERY = "computer science and AI scientific papers"
DEFAULT_THINKING = "high"


@dataclass(frozen=True)
class RunLayout:
    test_id: str
    session_key: str
    host_root: Path
    host_vault_root: Path
    host_artifacts_dir: Path
    host_db_path: Path
    host_manifest_path: Path
    host_prompt_path: Path
    host_tui_command_path: Path
    host_prepared_bundle_path: Path
    host_bundle_summary_path: Path
    host_sonar_db_path: Path
    host_source_dir: Path
    host_active_synapse_config_path: Path
    container_root: str
    container_vault_root: str
    container_artifacts_dir: str
    container_db_path: str
    container_prepared_bundle_path: str
    container_bundle_summary_path: str
    container_sonar_db_path: str
    container_source_dir: str
    container_active_synapse_config_path: str


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare":
        return command_prepare(args)
    if args.command == "collect-sources":
        return command_collect_sources(args)
    if args.command == "verify":
        return command_verify(args)
    parser.error("missing command")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Nyx e2e harness for the deterministic-Sonar plus OpenClaw/Synapse paper-ingestion scenario."
    )
    subparsers = parser.add_subparsers(dest="command")

    prepare = subparsers.add_parser(
        "prepare",
        help="Create a new isolated e2e run layout, optionally rebuild Nyx, run deterministic Sonar collection, and emit the exact TUI command.",
    )
    prepare.add_argument("--test-id", help="Reuse a specific test id instead of generating one.")
    prepare.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Paper search query stored in the prompt and run manifest. Default: {DEFAULT_QUERY!r}",
    )
    prepare.add_argument(
        "--thinking",
        default=DEFAULT_THINKING,
        help=f"OpenClaw TUI thinking level. Default: {DEFAULT_THINKING!r}",
    )
    prepare.add_argument(
        "--rebuild",
        action="store_true",
        help="Run `just build` and `just up` before preflight validation.",
    )
    prepare.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip runtime checks. Intended only for dry runs while the container is stale.",
    )
    prepare.add_argument(
        "--skip-source-collection",
        action="store_true",
        help="Skip deterministic Sonar collection. Intended only for debugging or rerunning only the TUI/Synapse phase.",
    )

    collect_sources = subparsers.add_parser(
        "collect-sources",
        help="Run the deterministic, model-agnostic Sonar collection phase for an existing test id.",
    )
    collect_sources.add_argument("--test-id", required=True, help="Existing test id to populate with Sonar artifacts.")
    collect_sources.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Paper search query stored in the source manifest. Default: {DEFAULT_QUERY!r}",
    )

    verify = subparsers.add_parser(
        "verify",
        help="Verify a completed e2e run, persist artifacts, and emit a summary report.",
    )
    verify.add_argument("--test-id", required=True, help="The test id created during `prepare`.")
    verify.add_argument(
        "--session-id",
        help="Optional explicit OpenClaw session id. When omitted, the verifier locates it from the session store.",
    )

    return parser


def command_prepare(args: argparse.Namespace) -> int:
    layout = build_layout(args.test_id)
    ensure_layout_dirs(layout)

    if args.rebuild:
        run(["just", "build"])
        run(["just", "up"])

    manifest = {
        "test_id": layout.test_id,
        "created_at": utc_now_iso(),
        "query": args.query,
        "thinking": args.thinking,
        "session_key": layout.session_key,
        "paths": {
            "host_root": str(layout.host_root),
            "host_vault_root": str(layout.host_vault_root),
            "host_artifacts_dir": str(layout.host_artifacts_dir),
            "host_db_path": str(layout.host_db_path),
            "host_sonar_db_path": str(layout.host_sonar_db_path),
            "host_prompt_path": str(layout.host_prompt_path),
            "host_tui_command_path": str(layout.host_tui_command_path),
            "host_prepared_bundle_path": str(layout.host_prepared_bundle_path),
            "host_bundle_summary_path": str(layout.host_bundle_summary_path),
            "host_source_dir": str(layout.host_source_dir),
            "host_active_synapse_config_path": str(layout.host_active_synapse_config_path),
            "container_root": layout.container_root,
            "container_vault_root": layout.container_vault_root,
            "container_artifacts_dir": layout.container_artifacts_dir,
            "container_db_path": layout.container_db_path,
            "container_sonar_db_path": layout.container_sonar_db_path,
            "container_prepared_bundle_path": layout.container_prepared_bundle_path,
            "container_bundle_summary_path": layout.container_bundle_summary_path,
            "container_source_dir": layout.container_source_dir,
            "container_active_synapse_config_path": layout.container_active_synapse_config_path,
        },
    }

    preflight = None
    if not args.skip_preflight:
        preflight = collect_prepare_preflight(layout)
        manifest["preflight"] = preflight

    if preflight is not None:
        write_json(layout.host_artifacts_dir / "preflight.json", preflight)
        if not preflight["ok"]:
            print_summary(
                f"Prepared {layout.test_id}, but preflight failed. See {layout.host_artifacts_dir / 'preflight.json'}",
                error=True,
            )
            return 1

    if not args.skip_source_collection:
        prepared_bundle = collect_sources_for_layout(layout, args.query)
        manifest["source_collection"] = {
            "completed_at": utc_now_iso(),
            "selected_count": int(prepared_bundle.get("selected_count", len(prepared_bundle.get("sources", [])))),
            "bundle_path": str(layout.host_prepared_bundle_path),
        }
    if layout.host_prepared_bundle_path.exists():
        write_prepared_source_bundle(layout)
    write_active_synapse_config(layout)

    prompt_text = render_prompt(layout, args.query)
    write_text(layout.host_prompt_path, prompt_text)
    write_text(layout.host_tui_command_path, render_tui_command(layout, args.thinking))
    os.chmod(layout.host_tui_command_path, 0o755)
    write_json(layout.host_manifest_path, manifest)

    summary_lines = [
        f"Prepared {layout.test_id}",
        f"Prompt: {layout.host_prompt_path}",
        f"TUI command: {layout.host_tui_command_path}",
        f"Manifest: {layout.host_manifest_path}",
    ]
    if not args.skip_source_collection:
        summary_lines.extend(
            [
                f"Prepared bundle: {layout.host_prepared_bundle_path}",
                f"Prepared bundle summary: {layout.host_bundle_summary_path}",
                f"Prepared source files: {layout.host_source_dir}",
                f"Active Synapse config: {layout.host_active_synapse_config_path}",
            ]
        )
    print_summary("\n".join(summary_lines))
    return 0


def command_collect_sources(args: argparse.Namespace) -> int:
    layout = build_layout(args.test_id)
    ensure_layout_dirs(layout)
    collect_sources_for_layout(layout, args.query)
    write_prepared_source_bundle(layout)
    write_active_synapse_config(layout)
    print_summary(f"Collected deterministic Sonar sources for {layout.test_id}: {layout.host_prepared_bundle_path}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    layout = build_layout(args.test_id)
    manifest = read_json(layout.host_manifest_path)

    checks: list[dict[str, Any]] = []
    checks.extend(collect_prepare_preflight(layout)["checks"])

    session_store = read_json(ROOT / "data" / "agents" / "main" / "sessions" / "sessions.json")
    session_record = locate_session_record(session_store, layout.session_key, explicit_session_id=args.session_id)
    if session_record is None and args.session_id:
        session_path = ROOT / "data" / "agents" / "main" / "sessions" / f"{args.session_id}.jsonl"
        if session_path.exists():
            session_record = {
                "sessionId": args.session_id,
                "key": layout.session_key,
                "source": "explicit-session-id",
            }
    if session_record is None:
        checks.append(check_result("session_exists", False, detail=f"No session found for {layout.session_key}"))
        return finalize_verification(layout, manifest, checks, {}, [])

    checks.append(
        check_result(
            "session_exists",
            True,
            detail=f"sessionId={session_record['sessionId']} key={session_record['key']}",
        )
    )
    session_path = ROOT / "data" / "agents" / "main" / "sessions" / f"{session_record['sessionId']}.jsonl"
    events = parse_jsonl(session_path)
    tool_events = extract_tool_events(events)
    assistant_texts = extract_assistant_texts(events)
    final_answer = assistant_texts[-1] if assistant_texts else ""

    note_info = inspect_notes(layout, manifest["query"])
    checks.extend(note_info["checks"])

    db_info = inspect_synapse_db(layout)
    checks.extend(db_info["checks"])

    source_info = inspect_prepared_bundle(layout, manifest["query"])
    checks.extend(source_info["checks"])

    transcript_info = inspect_transcript(layout, tool_events, final_answer, note_info["notes"], manifest)
    checks.extend(transcript_info["checks"])

    artifacts = {
        "session": session_record,
        "session_path": str(session_path),
        "note_paths": [note["path"] for note in note_info["notes"]],
        "selected_sources": [
            {
                "file": note["file_name"],
                "title": note["title"],
                "source_url": note["source_url"],
                "published": note["published"],
                "authors": note["authors"],
            }
            for note in note_info["notes"]
        ],
        "tool_events": tool_events,
        "db": db_info["db"],
        "prepared_bundle": source_info["bundle"],
    }
    write_json(layout.host_artifacts_dir / "session.json", session_record)
    write_json(layout.host_artifacts_dir / "selected_sources.json", artifacts["selected_sources"])
    write_json(layout.host_artifacts_dir / "note_paths.json", artifacts["note_paths"])
    write_json(layout.host_artifacts_dir / "tool_events.json", tool_events)
    write_text(layout.host_artifacts_dir / "final_answer.md", final_answer + ("\n" if final_answer else ""))
    write_json(layout.host_artifacts_dir / "db_summary.json", db_info["db"])
    write_json(layout.host_artifacts_dir / "prepared_source_bundle_copy.json", source_info["bundle"])
    write_json(
        layout.host_artifacts_dir / "sonar_shortlist.json",
        source_info["bundle"].get("sources", []),
    )

    return finalize_verification(layout, manifest, checks, artifacts, note_info["notes"])


def finalize_verification(
    layout: RunLayout,
    manifest: dict[str, Any],
    checks: list[dict[str, Any]],
    artifacts: dict[str, Any],
    notes: list[dict[str, Any]],
) -> int:
    failed = [check for check in checks if not check["ok"]]
    summary = {
        "test_id": layout.test_id,
        "generated_at": utc_now_iso(),
        "status": "passed" if not failed else "failed",
        "first_failure": failed[0]["name"] if failed else None,
        "paths": manifest["paths"],
        "selected_papers": [
            {
                "file": note["file_name"],
                "title": note["title"],
                "source_url": note["source_url"],
            }
            for note in notes
        ],
        "checks": checks,
        "artifacts": artifacts,
    }
    write_json(layout.host_artifacts_dir / "summary.json", summary)
    write_text(layout.host_artifacts_dir / "summary.md", render_summary_markdown(summary))

    if failed:
        print_summary(
            f"Verification failed for {layout.test_id}. Summary: {layout.host_artifacts_dir / 'summary.md'}",
            error=True,
        )
        return 1

    print_summary(f"Verification passed for {layout.test_id}. Summary: {layout.host_artifacts_dir / 'summary.md'}")
    return 0


def build_layout(test_id: str | None) -> RunLayout:
    prefix = "e2e-sonar-synapse-"
    if test_id is None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        test_id = f"{prefix}{stamp}"
    session_key = test_id if test_id.startswith(prefix) else f"{prefix}{test_id}"
    host_root = ROOT / "data" / "workspace" / "e2e" / test_id
    host_vault_root = host_root / "ingestion_vault"
    host_artifacts_dir = host_root / "artifacts"
    host_db_path = host_root / "synapse.sqlite"
    host_sonar_db_path = host_root / "sonar.sqlite"
    host_source_dir = host_artifacts_dir / "sources"
    container_root = f"/data/workspace/e2e/{test_id}"
    return RunLayout(
        test_id=test_id,
        session_key=session_key,
        host_root=host_root,
        host_vault_root=host_vault_root,
        host_artifacts_dir=host_artifacts_dir,
        host_db_path=host_db_path,
        host_manifest_path=host_root / "manifest.json",
        host_prompt_path=host_artifacts_dir / "prompt.txt",
        host_tui_command_path=host_artifacts_dir / "openclaw-tui-command.sh",
        host_prepared_bundle_path=host_artifacts_dir / "prepared_source_bundle.json",
        host_bundle_summary_path=host_artifacts_dir / "prepared_sources_bundle.md",
        host_sonar_db_path=host_sonar_db_path,
        host_source_dir=host_source_dir,
        host_active_synapse_config_path=ACTIVE_SYNAPSE_CONFIG,
        container_root=container_root,
        container_vault_root=f"{container_root}/ingestion_vault",
        container_artifacts_dir=f"{container_root}/artifacts",
        container_db_path=f"{container_root}/synapse.sqlite",
        container_prepared_bundle_path=f"{container_root}/artifacts/prepared_source_bundle.json",
        container_bundle_summary_path=f"{container_root}/artifacts/prepared_sources_bundle.md",
        container_sonar_db_path=f"{container_root}/sonar.sqlite",
        container_source_dir=f"{container_root}/artifacts/sources",
        container_active_synapse_config_path="/data/workspace/e2e/active-synapse.toml",
    )


def ensure_layout_dirs(layout: RunLayout) -> None:
    layout.host_root.mkdir(parents=True, exist_ok=True)
    layout.host_vault_root.mkdir(parents=True, exist_ok=True)
    layout.host_artifacts_dir.mkdir(parents=True, exist_ok=True)
    layout.host_source_dir.mkdir(parents=True, exist_ok=True)
    layout.host_active_synapse_config_path.parent.mkdir(parents=True, exist_ok=True)


def write_active_synapse_config(layout: RunLayout) -> None:
    source_text = WORKSPACE_SYNAPSE_CONFIG.read_text(encoding="utf-8")
    updated = re.sub(
        r'(?m)^root = ".*"$',
        f'root = "{layout.container_vault_root}"',
        source_text,
        count=1,
    )
    updated = re.sub(
        r'(?m)^path = ".*"$',
        f'path = "{layout.container_db_path}"',
        updated,
        count=1,
    )
    if updated == source_text:
        raise RuntimeError("Failed to rewrite Synapse active config for the e2e workspace")
    write_text(layout.host_active_synapse_config_path, updated)


def collect_sources_for_layout(layout: RunLayout, query: str) -> dict[str, Any]:
    collector_path = layout.host_artifacts_dir / "collect_sources.py"
    write_text(collector_path, render_sonar_collection_script(layout, query))
    result = run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "nyx",
            "sh",
            "-lc",
            f"SONAR_DB={shlex.quote(layout.container_sonar_db_path)} /nix-env/bin/sonar-python {shlex.quote(str(Path(layout.container_artifacts_dir) / 'collect_sources.py'))}",
        ],
        check=False,
    )
    write_text(layout.host_artifacts_dir / "source_collection.log", (result.stdout or "") + (result.stderr or ""))
    if result.returncode != 0:
        raise RuntimeError(
            f"Deterministic Sonar collection failed for {layout.test_id}: {(result.stderr or result.stdout).strip()}"
        )
    return read_json(layout.host_prepared_bundle_path)


def write_prepared_source_bundle(layout: RunLayout) -> None:
    bundle = read_json(layout.host_prepared_bundle_path)
    lines = [
        "# Prepared Sources Bundle",
        "",
        f"TEST_ID: {layout.test_id}",
        f"QUERY: {bundle.get('query', DEFAULT_QUERY)}",
        f"BUNDLE_ID: {bundle.get('bundle_id', '')}",
        f"BUNDLE_PATH: {bundle.get('bundle_path', '')}",
        "",
        "Read this bundle as the single prepared input set for the TUI phase.",
        "Do not substitute different papers.",
        "",
    ]

    for index, payload in enumerate(bundle.get("sources", []), start=1):
        lines.extend(
            [
                f"## Paper {index}: paper-{index:02d}.md",
                f"SOURCE_ID: {payload.get('source_id', '')}",
                f"ORIGIN_URL: {payload.get('origin_url', '')}",
                f"SOURCE_URL: {payload.get('url', '')}",
                f"DIRECT_PAPER_URL: {payload.get('direct_paper_url', '')}",
                f"TITLE: {payload.get('title', '')}",
                f"AUTHORS: {'; '.join(payload.get('authors', []))}",
                f"PUBLISHED: {payload.get('published', '')}",
                f"SOURCE_TYPE: {payload.get('source_type', '')}",
                f"EXTRACTION_STATUS: {payload.get('extraction_status', '')}",
                f"EXTRACTION_METHOD: {payload.get('extraction_method', '')}",
                f"FULL_TEXT_PATH: {payload.get('full_text_path', '')}",
                f"SELECTION_REASON: {payload.get('selection_reason', '')}",
                "",
                "### Summary",
                str(payload.get("summary", "")).strip(),
                "",
                "### Abstract",
                str(payload.get("abstract", "")).strip(),
                "",
                "### Extracted Text",
                str(payload.get("full_text", "")).strip(),
                "",
            ]
        )

    write_text(layout.host_bundle_summary_path, "\n".join(lines).rstrip() + "\n")


def render_sonar_collection_script(layout: RunLayout, query: str) -> str:
    payload = {
        "test_id": layout.test_id,
        "query": query,
        "db_path": layout.container_sonar_db_path,
        "prepared_bundle_path": layout.container_prepared_bundle_path,
        "artifacts_dir": layout.container_artifacts_dir,
        "source_dir": layout.container_source_dir,
    }
    payload_json = json.dumps(payload)
    return f"""#!/nix-env/bin/sonar-python
from __future__ import annotations

import json
import shutil
from pathlib import Path

from sonar.bundles import ARTIFACT_FILENAME
from sonar.service_api import (
    CollectSourcesForTopicRequest,
    HealthRequest,
    collect_sources_for_topic,
    runtime_requirements,
)

CONFIG = json.loads({payload_json!r})
TEST_ID = CONFIG["test_id"]
QUERY = CONFIG["query"]
DB_PATH = CONFIG["db_path"]
PREPARED_BUNDLE_PATH = Path(CONFIG["prepared_bundle_path"])
ARTIFACTS_DIR = Path(CONFIG["artifacts_dir"])
SOURCE_DIR = Path(CONFIG["source_dir"])

SOURCE_DIR.mkdir(parents=True, exist_ok=True)
health = runtime_requirements(HealthRequest(db_path=DB_PATH)).model_dump()
response = collect_sources_for_topic(
    CollectSourcesForTopicRequest(
        topic=QUERY,
        db_path=DB_PATH,
        max_results=5,
        corpus="papers",
        profile="scientific",
        direct_only=False,
        persist=True,
        output_dir=str(ARTIFACTS_DIR),
        include_sidecars=True,
    )
)
bundle = response.bundle.model_dump()
bundle_dir = Path(bundle["bundle_path"])
persisted_manifest = bundle_dir / ARTIFACT_FILENAME
shutil.copyfile(persisted_manifest, PREPARED_BUNDLE_PATH)

for index, source in enumerate(bundle.get("sources", []), start=1):
    source_json_path = SOURCE_DIR / f"source_{{index:02d}}.json"
    source_txt_path = SOURCE_DIR / f"source_{{index:02d}}.txt"
    source_json_path.write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")

    full_text_path = source.get("full_text_path")
    full_text = source.get("full_text") or ""
    if full_text_path:
        shutil.copyfile(full_text_path, source_txt_path)
    else:
        source_txt_path.write_text(full_text + ("\\n" if full_text else ""), encoding="utf-8")

if bundle.get("selected_count", len(bundle.get("sources", []))) < 5:
    raise SystemExit(f"Need 5 prepared paper sources, found {{bundle.get('selected_count', len(bundle.get('sources', [])))}}")

print(
    json.dumps(
        {{
            "status": "ok",
            "selected_count": bundle.get("selected_count", len(bundle.get("sources", []))),
            "prepared_bundle_path": str(PREPARED_BUNDLE_PATH),
            "bundle_id": bundle.get("bundle_id"),
            "bundle_dir": str(bundle_dir),
        }},
        ensure_ascii=False,
    )
)
"""


def render_prompt(layout: RunLayout, query: str) -> str:
    filenames = "\n".join(f"- {name}" for name in EXPECTED_NOTE_FILENAMES)
    return f"""You are running the Nyx e2e ingestion scenario.

This run already completed a deterministic, model-agnostic Sonar collection phase.
Your job is the smaller second phase only: consume the prepared Sonar bundle, write the 5 markdown notes, index them with Synapse, search the dedicated DB, and produce grounded insights.

Obey these constraints exactly:
- Do not call any `sonar_*` tools in this phase unless the prepared bundle is missing or unreadable.
- Do not search the open web yourself.
- Use only the prepared bundle and source JSON/text files listed below.
- Do not use any existing notes or indexes outside this test run.
- Do not read from /data/workspace/vault, /data/workspace/ingestion_vault, or any old Synapse DB.
- For Synapse, prefer only the pathless workspace tools with `workspace="current"`.
- Do not call the raw-path Synapse tools (`synapse_health`, `synapse_index`, `synapse_search`) or the `*_simple` wrappers in this run.
- Use native tool calls only. Never emit pseudo-tool syntax, XML, HTML, code fences, or text such as `<tool_call>...</tool_call>`.

This run is identified by:
- TEST_ID: {layout.test_id}
- SESSION_KEY: {layout.session_key}

Use only these dedicated paths:
- Ingestion vault: {layout.container_vault_root}
- Synapse DB: {layout.container_db_path}
- Artifacts dir: {layout.container_artifacts_dir}
- Prepared bundle: {layout.container_prepared_bundle_path}
- Bundle summary: {layout.container_bundle_summary_path}
- Source files dir: {layout.container_source_dir}
- Active Synapse config: {layout.container_active_synapse_config_path}

Required tool flow:
1. Read the prepared bundle JSON at {layout.container_prepared_bundle_path}.
2. Read the bundle summary at {layout.container_bundle_summary_path}.
3. Read the per-source JSON/text files under {layout.container_source_dir} when you need source-level detail.
4. Run synapse_health_for_workspace with workspace="current" to confirm the run-scoped workspace is active.
5. Write exactly 5 markdown notes into {layout.container_vault_root} with these exact filenames:
{filenames}
6. Run synapse_index_for_workspace with workspace="current".
7. Run synapse_search_for_workspace with workspace="current" and mode="hybrid".
8. Optional: synapse_discover with db_path={layout.container_db_path} and threshold between 0.20 and 0.40.
9. Produce a final grounded answer only from the 5 ingested notes.

Exact tool argument examples:
- synapse_health_for_workspace(workspace="current")
- synapse_index_for_workspace(workspace="current")
- synapse_search_for_workspace(query="cross-paper insights about AI and computer science", workspace="current", mode="hybrid")

Prepared-source rule:
- Trust the prepared Sonar bundle as the fixed input set for this phase.
- Prefer the canonical bundle JSON and persisted sidecars over transcript memory.
- Use the bundle's `abstract`, `summary`, `full_text`, and provenance fields when writing notes.
- Do not replace the selected papers with different ones.
- If a source file is missing, fail clearly instead of improvising a replacement.

Each note must use this exact schema:
TEST_ID: {layout.test_id}
QUERY: {query}
SOURCE_URL: <paper URL>
TITLE: <paper title>
AUTHORS: <author one>; <author two>; <author three>
PUBLISHED: <ISO timestamp or date>
RETRIEVED_AT: <ISO timestamp>

# <paper title>

## Abstract
<paper abstract>

## Extract
<the evidence extracted from Sonar that justified the note>

## Why Selected
<why this paper belongs in the final 5>

Final response format:
## Selected Papers
1. <title> [paper-01.md]
2. <title> [paper-02.md]
3. <title> [paper-03.md]
4. <title> [paper-04.md]
5. <title> [paper-05.md]

## Cross-Paper Insights
1. <insight with one or more [paper-0N.md] citations>
2. <insight with one or more [paper-0N.md] citations>
3. <insight with one or more [paper-0N.md] citations>
4. <optional>
5. <optional>

If a required dependency is unavailable or you cannot find 5 valid papers, stop and report the failure clearly instead of guessing.
"""


def render_tui_command(layout: RunLayout, thinking: str) -> str:
    prompt_path = shlex.quote(str(layout.host_prompt_path))
    session_key = shlex.quote(layout.session_key)
    thinking_arg = shlex.quote(thinking)
    compose_file = shlex.quote(str(COMPOSE_FILE))
    repo_root = shlex.quote(str(ROOT))
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd {repo_root}",
            "# If a prior attempt timed out or switched models mid-run, prepare a new test_id instead of reusing this session.",
            f'docker compose -f {compose_file} exec -it nyx openclaw tui --session {session_key} --thinking {thinking_arg} --timeout-ms 1800000 --message "$(cat {prompt_path})"',
            "",
        ]
    )


def collect_prepare_preflight(layout: RunLayout) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(check_config_contains_servers(SECRETS_OPENCLAW, ["sonar", "synapse"], "openclaw_mcp_config"))
    checks.append(check_config_contains_servers(SECRETS_QWEN, ["sonar", "synapse"], "qwen_mcp_config"))
    checks.append(check_container_running("nyx_container_running", "nyx"))
    checks.append(check_container_running("searxng_container_running", "searxng"))
    checks.append(check_exec_success("gateway_health", ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "openclaw", "health", "--json"]))
    checks.append(check_exec_success("tui_available", ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "openclaw", "tui", "--help"]))
    checks.append(check_container_file("sonar_skill_present", "/app/skills/sonar/SKILL.md"))
    checks.append(check_container_file("synapse_skill_present", "/app/skills/synapse/SKILL.md"))
    checks.append(check_container_file("workspace_sonar_skill_present", "/data/workspace/.agents/skills/sonar/SKILL.md"))
    checks.append(check_container_file("workspace_synapse_skill_present", "/data/workspace/.agents/skills/synapse/SKILL.md"))
    checks.append(check_container_file("sonar_mcp_available", "/nix-env/bin/sonar-mcp"))
    checks.append(check_container_file("synapse_mcp_available", "/nix-env/bin/synapse-mcp"))
    checks.append(check_container_file("build_info_present", "/app/build-info.json"))
    checks.append(check_host_path_writable("e2e_root_writable", layout.host_root))
    checks.append(check_host_path_writable("e2e_vault_writable", layout.host_vault_root))
    checks.append(check_host_path_writable("e2e_db_parent_writable", layout.host_db_path.parent))
    checks.append(check_host_path_writable("e2e_sonar_db_parent_writable", layout.host_sonar_db_path.parent))
    checks.append(check_host_path_writable("e2e_source_dir_writable", layout.host_source_dir))

    build_info = None
    build_info_result = run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "cat", "/app/build-info.json"],
        check=False,
    )
    if build_info_result.returncode == 0:
        try:
            build_info = json.loads(build_info_result.stdout)
        except json.JSONDecodeError:
            build_info = {"raw": build_info_result.stdout}

    return {
        "ok": all(check["ok"] for check in checks),
        "generated_at": utc_now_iso(),
        "build_info": build_info,
        "checks": checks,
    }


def inspect_notes(layout: RunLayout, expected_query: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    files = sorted(path for path in layout.host_vault_root.glob("*.md") if path.is_file())
    note_names = [path.name for path in files]
    checks.append(
        check_result(
            "note_count_exactly_five",
            len(files) == 5,
            detail=f"found={len(files)} files={note_names}",
        )
    )
    checks.append(
        check_result(
            "note_filenames_match_contract",
            note_names == EXPECTED_NOTE_FILENAMES,
            detail=f"found={note_names}",
        )
    )

    notes: list[dict[str, Any]] = []
    for path in files:
        note = parse_note(path)
        notes.append(note)
        checks.append(check_result(f"{path.name}_test_id", note["test_id"] == layout.test_id, detail=note["test_id"]))
        checks.append(check_result(f"{path.name}_query", note["query"] == expected_query, detail=note["query"]))
        checks.append(check_result(f"{path.name}_source_url", bool(note["source_url"]), detail=note["source_url"]))
        checks.append(check_result(f"{path.name}_title", bool(note["title"]), detail=note["title"]))
        checks.append(check_result(f"{path.name}_authors", bool(note["authors"]), detail="; ".join(note["authors"])))
        checks.append(check_result(f"{path.name}_published", bool(note["published"]), detail=note["published"]))
        checks.append(check_result(f"{path.name}_retrieved_at", bool(note["retrieved_at"]), detail=note["retrieved_at"]))
        checks.append(check_result(f"{path.name}_abstract", bool(note["abstract"]), detail=f"chars={len(note['abstract'])}"))
        checks.append(check_result(f"{path.name}_extract", bool(note["extract"]), detail=f"chars={len(note['extract'])}"))
        checks.append(check_result(f"{path.name}_why_selected", bool(note["why_selected"]), detail=f"chars={len(note['why_selected'])}"))

    return {"checks": checks, "notes": notes}


def inspect_prepared_bundle(layout: RunLayout, expected_query: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not layout.host_prepared_bundle_path.exists():
        checks.append(check_result("prepared_bundle_exists", False, detail=str(layout.host_prepared_bundle_path)))
        return {"checks": checks, "bundle": {}}

    bundle = read_json(layout.host_prepared_bundle_path)
    checks.append(check_result("prepared_bundle_exists", True, detail=str(layout.host_prepared_bundle_path)))
    checks.append(check_result("prepared_bundle_query", bundle.get("query") == expected_query, detail=str(bundle.get("query"))))
    checks.append(check_result("prepared_bundle_artifact_type", bundle.get("artifact_type") == "prepared_source_bundle", detail=str(bundle.get("artifact_type"))))
    checks.append(check_result("prepared_bundle_has_bundle_id", bool(bundle.get("bundle_id")), detail=str(bundle.get("bundle_id"))))
    sources = bundle.get("sources", [])
    checks.append(check_result("prepared_bundle_selected_count", len(sources) == 5, detail=f"count={len(sources)}"))

    for index, source in enumerate(sources, start=1):
        json_path = layout.host_source_dir / f"source_{index:02d}.json"
        text_path = layout.host_source_dir / f"source_{index:02d}.txt"
        checks.append(check_result(f"source_{index:02d}_json_exists", json_path.exists(), detail=str(json_path)))
        checks.append(check_result(f"source_{index:02d}_text_exists", text_path.exists(), detail=str(text_path)))
        checks.append(check_result(f"source_{index:02d}_source_id", bool(source.get("source_id")), detail=str(source.get("source_id"))))
        checks.append(check_result(f"source_{index:02d}_title", bool(source.get("title")), detail=str(source.get("title"))))
        checks.append(check_result(f"source_{index:02d}_url", bool(source.get("url")), detail=str(source.get("url"))))
        checks.append(check_result(f"source_{index:02d}_summary_or_abstract", bool(source.get("summary") or source.get("abstract")), detail=f"summary={bool(source.get('summary'))} abstract={bool(source.get('abstract'))}"))
        full_text_path = str(source.get("full_text_path") or "")
        host_full_text_path = ROOT / full_text_path.replace("/data/workspace/", "data/workspace/") if full_text_path.startswith("/data/workspace/") else None
        checks.append(check_result(f"source_{index:02d}_full_text_path", bool(full_text_path), detail=full_text_path))
        checks.append(
            check_result(
                f"source_{index:02d}_full_text_path_exists",
                host_full_text_path is not None and host_full_text_path.exists(),
                detail=str(host_full_text_path) if host_full_text_path is not None else full_text_path,
            )
        )

    return {"checks": checks, "bundle": bundle}


def inspect_synapse_db(layout: RunLayout) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(check_result("synapse_db_exists", layout.host_db_path.exists(), detail=str(layout.host_db_path)))
    if not layout.host_db_path.exists():
        return {"checks": checks, "db": {}}

    conn = sqlite3.connect(layout.host_db_path)
    try:
        conn.row_factory = sqlite3.Row
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks WHERE scope = 'chunk'").fetchone()[0]
        note_chunk_count = conn.execute("SELECT COUNT(*) FROM chunks WHERE scope = 'note'").fetchone()[0]
        doc_paths = [row[0] for row in conn.execute("SELECT path FROM documents ORDER BY path").fetchall()]
    finally:
        conn.close()

    checks.append(check_result("synapse_documents_exactly_five", doc_count == 5, detail=f"count={doc_count}"))
    checks.append(
        check_result(
            "synapse_document_paths_match_notes",
            doc_paths == EXPECTED_NOTE_FILENAMES,
            detail=f"paths={doc_paths}",
        )
    )
    checks.append(check_result("synapse_chunk_rows_exist", chunk_count > 0, detail=f"chunk_count={chunk_count}"))
    checks.append(check_result("synapse_note_chunks_exist", note_chunk_count == 5, detail=f"note_chunks={note_chunk_count}"))

    return {
        "checks": checks,
        "db": {
            "path": str(layout.host_db_path),
            "documents": doc_count,
            "chunk_rows": chunk_count,
            "note_chunk_rows": note_chunk_count,
            "document_paths": doc_paths,
        },
    }


def inspect_transcript(
    layout: RunLayout,
    tool_events: list[dict[str, Any]],
    final_answer: str,
    notes: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    by_name: dict[str, list[dict[str, Any]]] = {}
    for event in tool_events:
        by_name.setdefault(event["name"], []).append(event)

    required_tools = [
        "synapse__synapse_health_for_workspace",
        "synapse__synapse_index_for_workspace",
        "synapse__synapse_search_for_workspace",
    ]
    for tool_name in required_tools:
        checks.append(
            check_result(
                f"{tool_name}_called",
                bool(by_name.get(tool_name)),
                detail=f"calls={len(by_name.get(tool_name, []))}",
            )
        )

    synapse_health_args = [event["arguments"] for event in by_name.get("synapse__synapse_health_for_workspace", [])]
    checks.append(
        check_result(
            "synapse_health_uses_current_workspace",
            any(
                args.get("workspace") == "current"
                for args in synapse_health_args
            ),
            detail=json.dumps(synapse_health_args),
        )
    )

    synapse_index_args = [event["arguments"] for event in by_name.get("synapse__synapse_index_for_workspace", [])]
    checks.append(
        check_result(
            "synapse_index_uses_current_workspace",
            any(
                args.get("workspace") == "current"
                for args in synapse_index_args
            ),
            detail=json.dumps(synapse_index_args),
        )
    )

    synapse_search_args = [event["arguments"] for event in by_name.get("synapse__synapse_search_for_workspace", [])]
    checks.append(
        check_result(
            "synapse_search_uses_current_workspace_hybrid_mode",
            any(
                args.get("workspace") == "current"
                and args.get("mode") == "hybrid"
                and bool(str(args.get("query", "")).strip())
                for args in synapse_search_args
            ),
            detail=json.dumps(synapse_search_args),
        )
    )

    search_result_text = "\n".join(event["result_text"] for event in by_name.get("synapse__synapse_search_for_workspace", []))
    for file_name in EXPECTED_NOTE_FILENAMES:
        checks.append(
            check_result(
                f"synapse_search_mentions_{file_name}",
                file_name in search_result_text,
                detail=f"search result contains {file_name}",
            )
        )

    checks.append(check_result("final_answer_exists", bool(final_answer.strip()), detail=f"chars={len(final_answer)}"))
    selected_count, insight_count = count_final_sections(final_answer)
    checks.append(check_result("final_selected_papers_exactly_five", selected_count == 5, detail=f"count={selected_count}"))
    checks.append(
        check_result(
            "final_cross_paper_insights_between_three_and_five",
            3 <= insight_count <= 5,
            detail=f"count={insight_count}",
        )
    )

    for note in notes:
        cited = note["file_name"] in final_answer or note["source_url"] in final_answer
        checks.append(
            check_result(
                f"final_answer_cites_{note['file_name']}",
                cited,
                detail=note["source_url"],
            )
        )

    return {"checks": checks}


def count_final_sections(text: str) -> tuple[int, int]:
    selected_match = re.search(
        r"(?ms)^## Selected Papers\s*(?P<body>.*?)(?=^## |\Z)",
        text,
    )
    insights_match = re.search(
        r"(?ms)^## Cross-Paper Insights\s*(?P<body>.*?)(?=^## |\Z)",
        text,
    )
    selected_count = count_numbered_items(selected_match.group("body")) if selected_match else 0
    insight_count = count_numbered_items(insights_match.group("body")) if insights_match else 0
    return selected_count, insight_count


def count_numbered_items(body: str) -> int:
    return len(re.findall(r"(?m)^\d+\.\s+", body))


def parse_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            break
        if line.startswith("# "):
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().upper()] = value.strip()

    return {
        "path": str(path),
        "file_name": path.name,
        "test_id": metadata.get("TEST_ID", ""),
        "query": metadata.get("QUERY", ""),
        "source_url": metadata.get("SOURCE_URL", ""),
        "title": metadata.get("TITLE", ""),
        "authors": [item.strip() for item in metadata.get("AUTHORS", "").split(";") if item.strip()],
        "published": metadata.get("PUBLISHED", ""),
        "retrieved_at": metadata.get("RETRIEVED_AT", ""),
        "abstract": extract_section(text, "Abstract"),
        "extract": extract_section(text, "Extract"),
        "why_selected": extract_section(text, "Why Selected"),
    }


def extract_section(text: str, heading: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*(.*?)\s*(?=^## |\Z)", text)
    return match.group(1).strip() if match else ""


def locate_session_record(
    session_store: dict[str, Any],
    session_key: str,
    explicit_session_id: str | None = None,
) -> dict[str, Any] | None:
    sessions = session_store.get("sessions", [])
    if explicit_session_id:
        for session in sessions:
            if session.get("sessionId") == explicit_session_id:
                return session
        return None

    matches = [
        session
        for session in sessions
        if session.get("key") == session_key or session_key in session.get("key", "")
    ]
    if not matches:
        return None
    return max(matches, key=lambda session: session.get("updatedAt", 0))


def extract_tool_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        role = message.get("role")
        content = message.get("content") or []

        if role == "assistant":
            for part in content:
                if part.get("type") != "toolCall":
                    continue
                record = {
                    "id": part["id"],
                    "name": part["name"],
                    "arguments": part.get("arguments", {}),
                    "timestamp": event.get("timestamp"),
                    "result_text": "",
                    "result_json": None,
                }
                calls[part["id"]] = record
                ordered.append(record)
        elif role == "toolResult":
            tool_call_id = message.get("toolCallId")
            record = calls.get(tool_call_id)
            if not record:
                continue
            result_text = "\n".join(
                item.get("text", "")
                for item in content
                if item.get("type") == "text"
            ).strip()
            record["result_text"] = result_text
            record["result_json"] = try_parse_json(result_text)
    return ordered


def extract_assistant_texts(events: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for event in events:
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("role") != "assistant":
            continue
        parts = message.get("content") or []
        text = "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
        if not text:
            continue
        if text.startswith("✅ New session started"):
            continue
        texts.append(text)
    return texts


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def try_parse_json(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def check_config_contains_servers(path: Path, servers: list[str], name: str) -> dict[str, Any]:
    if not path.exists():
        return check_result(name, False, detail=f"missing {path}")
    text = path.read_text(encoding="utf-8")
    ok = all(re.search(rf'["\']{re.escape(server)}["\']\s*:\s*\{{', text) for server in servers)
    return check_result(name, ok, detail=f"servers={servers}")


def check_container_running(name: str, service_name: str) -> dict[str, Any]:
    result = run(["docker", "compose", "-f", str(COMPOSE_FILE), "ps"], check=False)
    detail = result.stdout.strip() or result.stderr.strip()
    ok = result.returncode == 0 and service_name in result.stdout and "Up" in result.stdout
    return check_result(name, ok, detail=detail)


def check_container_file(name: str, path: str) -> dict[str, Any]:
    result = run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "sh", "-lc", f"test -f {shlex.quote(path)}"],
        check=False,
    )
    detail = path if result.returncode == 0 else (result.stderr.strip() or path)
    return check_result(name, result.returncode == 0, detail=detail)


def check_container_command(name: str, command_name: str) -> dict[str, Any]:
    result = run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "sh", "-c", f"command -v {shlex.quote(command_name)}"],
        check=False,
    )
    detail = result.stdout.strip() or result.stderr.strip() or command_name
    return check_result(name, result.returncode == 0, detail=detail)


def check_exec_success(name: str, command: list[str]) -> dict[str, Any]:
    result = run(command, check=False)
    detail = result.stdout.strip() or result.stderr.strip()
    return check_result(name, result.returncode == 0, detail=detail)


def check_host_path_writable(name: str, path: Path) -> dict[str, Any]:
    ok = path.exists() and os.access(path, os.W_OK)
    return check_result(name, ok, detail=str(path))


def check_result(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary['test_id']}",
        "",
        f"- Status: **{summary['status']}**",
        f"- Generated: {summary['generated_at']}",
        f"- First failure: {summary['first_failure'] or 'none'}",
        "",
        "## Selected Papers",
    ]
    selected = summary.get("selected_papers", [])
    if selected:
        for paper in selected:
            lines.append(f"- {paper['file']}: {paper['title']} ({paper['source_url']})")
    else:
        lines.append("- none")
    lines.extend(["", "## Checks"])
    for check in summary.get("checks", []):
        status = "PASS" if check["ok"] else "FAIL"
        detail = f" - {check['detail']}" if check.get("detail") else ""
        lines.append(f"- [{status}] {check['name']}{detail}")
    return "\n".join(lines) + "\n"


def print_summary(message: str, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(message + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
