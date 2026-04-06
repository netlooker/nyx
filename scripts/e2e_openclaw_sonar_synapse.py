#!/usr/bin/env python3
"""Hybrid Nyx e2e harness for OpenClaw TUI -> Sonar -> Synapse."""

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
    container_root: str
    container_vault_root: str
    container_artifacts_dir: str
    container_db_path: str


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare":
        return command_prepare(args)
    if args.command == "verify":
        return command_verify(args)
    parser.error("missing command")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Nyx e2e harness for the OpenClaw Sonar/Synapse paper-ingestion scenario."
    )
    subparsers = parser.add_subparsers(dest="command")

    prepare = subparsers.add_parser(
        "prepare",
        help="Create a new isolated e2e run layout, optionally rebuild Nyx, and emit the exact TUI command.",
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

    prompt_text = render_prompt(layout, args.query)
    write_text(layout.host_prompt_path, prompt_text)
    write_text(layout.host_tui_command_path, render_tui_command(layout, args.thinking))
    os.chmod(layout.host_tui_command_path, 0o755)

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
            "host_prompt_path": str(layout.host_prompt_path),
            "host_tui_command_path": str(layout.host_tui_command_path),
            "container_root": layout.container_root,
            "container_vault_root": layout.container_vault_root,
            "container_artifacts_dir": layout.container_artifacts_dir,
            "container_db_path": layout.container_db_path,
        },
    }

    preflight = None
    if not args.skip_preflight:
        preflight = collect_prepare_preflight(layout)
        manifest["preflight"] = preflight
    write_json(layout.host_manifest_path, manifest)

    if preflight is not None:
        write_json(layout.host_artifacts_dir / "preflight.json", preflight)
        if not preflight["ok"]:
            print_summary(
                f"Prepared {layout.test_id}, but preflight failed. See {layout.host_artifacts_dir / 'preflight.json'}",
                error=True,
            )
            return 1

    print_summary(
        "\n".join(
            [
                f"Prepared {layout.test_id}",
                f"Prompt: {layout.host_prompt_path}",
                f"TUI command: {layout.host_tui_command_path}",
                f"Manifest: {layout.host_manifest_path}",
            ]
        )
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    layout = build_layout(args.test_id)
    manifest = read_json(layout.host_manifest_path)

    checks: list[dict[str, Any]] = []
    checks.extend(collect_prepare_preflight(layout)["checks"])

    session_store = read_json(ROOT / "data" / "agents" / "main" / "sessions" / "sessions.json")
    session_record = locate_session_record(session_store, layout.session_key, explicit_session_id=args.session_id)
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
    }
    write_json(layout.host_artifacts_dir / "session.json", session_record)
    write_json(layout.host_artifacts_dir / "selected_sources.json", artifacts["selected_sources"])
    write_json(layout.host_artifacts_dir / "note_paths.json", artifacts["note_paths"])
    write_json(layout.host_artifacts_dir / "tool_events.json", tool_events)
    write_text(layout.host_artifacts_dir / "final_answer.md", final_answer + ("\n" if final_answer else ""))
    write_json(layout.host_artifacts_dir / "db_summary.json", db_info["db"])
    write_json(
        layout.host_artifacts_dir / "sonar_shortlist.json",
        [event for event in tool_events if event["name"] == "sonar__sonar_search"],
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
        container_root=container_root,
        container_vault_root=f"{container_root}/ingestion_vault",
        container_artifacts_dir=f"{container_root}/artifacts",
        container_db_path=f"{container_root}/synapse.sqlite",
    )


def ensure_layout_dirs(layout: RunLayout) -> None:
    layout.host_root.mkdir(parents=True, exist_ok=True)
    layout.host_vault_root.mkdir(parents=True, exist_ok=True)
    layout.host_artifacts_dir.mkdir(parents=True, exist_ok=True)


def render_prompt(layout: RunLayout, query: str) -> str:
    filenames = "\n".join(f"- {name}" for name in EXPECTED_NOTE_FILENAMES)
    return f"""You are running the Nyx e2e ingestion scenario.

Obey these constraints exactly:
- Use Sonar first.
- Find exactly 5 unique scientific papers relevant to this query: "{query}".
- Reject blogs, docs, news, landing pages without paper metadata, and duplicates.
- Do not use any existing notes or indexes outside this test run.
- Do not read from /data/workspace/vault, /data/workspace/ingestion_vault, or any old Synapse DB.

This run is identified by:
- TEST_ID: {layout.test_id}
- SESSION_KEY: {layout.session_key}

Use only these dedicated paths:
- Ingestion vault: {layout.container_vault_root}
- Synapse DB: {layout.container_db_path}
- Artifacts dir: {layout.container_artifacts_dir}

Required tool flow:
1. Call sonar_health.
2. Use sonar_search to find candidate papers.
3. Use sonar_fetch on finalists.
4. Use sonar_extract on the 5 selected papers.
5. Call synapse_health with vault_root={layout.container_vault_root} and db_path={layout.container_db_path}.
6. Write exactly 5 markdown notes into {layout.container_vault_root} with these exact filenames:
{filenames}
7. Run synapse_index with vault_root={layout.container_vault_root} and db_path={layout.container_db_path}.
8. Run synapse_search with mode="hybrid" and db_path={layout.container_db_path}.
9. Optional: synapse_discover with db_path={layout.container_db_path} and threshold between 0.20 and 0.40.
10. Produce a final grounded answer only from the 5 ingested notes.

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
            f'docker compose -f {compose_file} exec -it nyx openclaw tui --session {session_key} --thinking {thinking_arg} --message "$(cat {prompt_path})"',
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
    checks.append(check_container_command("sonar_mcp_available", "sonar-mcp"))
    checks.append(check_container_command("synapse_mcp_available", "synapse-mcp"))
    checks.append(check_container_file("build_info_present", "/app/build-info.json"))
    checks.append(check_host_path_writable("e2e_root_writable", layout.host_root))
    checks.append(check_host_path_writable("e2e_vault_writable", layout.host_vault_root))
    checks.append(check_host_path_writable("e2e_db_parent_writable", layout.host_db_path.parent))

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
        "sonar__sonar_health",
        "sonar__sonar_search",
        "sonar__sonar_fetch",
        "sonar__sonar_extract",
        "synapse__synapse_health",
        "synapse__synapse_index",
        "synapse__synapse_search",
    ]
    for tool_name in required_tools:
        checks.append(
            check_result(
                f"{tool_name}_called",
                bool(by_name.get(tool_name)),
                detail=f"calls={len(by_name.get(tool_name, []))}",
            )
        )

    checks.append(
        check_result(
            "sonar_extract_called_at_least_five_times",
            len(by_name.get("sonar__sonar_extract", [])) >= 5,
            detail=f"calls={len(by_name.get('sonar__sonar_extract', []))}",
        )
    )

    synapse_health_args = [event["arguments"] for event in by_name.get("synapse__synapse_health", [])]
    checks.append(
        check_result(
            "synapse_health_uses_dedicated_paths",
            any(
                args.get("vault_root") == manifest["paths"]["container_vault_root"]
                and args.get("db_path") == manifest["paths"]["container_db_path"]
                for args in synapse_health_args
            ),
            detail=json.dumps(synapse_health_args),
        )
    )

    synapse_index_args = [event["arguments"] for event in by_name.get("synapse__synapse_index", [])]
    checks.append(
        check_result(
            "synapse_index_uses_dedicated_paths",
            any(
                args.get("vault_root") == manifest["paths"]["container_vault_root"]
                and args.get("db_path") == manifest["paths"]["container_db_path"]
                for args in synapse_index_args
            ),
            detail=json.dumps(synapse_index_args),
        )
    )

    synapse_search_args = [event["arguments"] for event in by_name.get("synapse__synapse_search", [])]
    checks.append(
        check_result(
            "synapse_search_uses_hybrid_dedicated_db",
            any(
                args.get("db_path") == manifest["paths"]["container_db_path"]
                and args.get("mode") == "hybrid"
                for args in synapse_search_args
            ),
            detail=json.dumps(synapse_search_args),
        )
    )

    search_result_text = "\n".join(event["result_text"] for event in by_name.get("synapse__synapse_search", []))
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
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "nyx", "sh", "-lc", f"command -v {shlex.quote(command_name)}"],
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
