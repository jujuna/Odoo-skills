"""Stop & SubagentStop verification hook for Odoo 19 (dual-protocol: Claude Code + Antigravity).

- Guarded against recursion via `stop_hook_active` (Claude Code) or `continuationActive` (Antigravity).
- Sweeps modified/untracked files across active git repos in custom_addons/
  with odoo_offline_check.py (closes Bash-edit bypass and surfaces errors in Antigravity).
- Checks for leaked scratch test DBs (gec19_t_*, odoo_t_*) on odoo.conf port or default 5432.
- Warns if any modified __manifest__.py changed its 'version' line.
"""
from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_V19_PORT = "5432"

READ_ONLY_AGENTS = {
    "Explore",
    "explore",
    "odoo-explore",
    "odoo-scout",
    "odoo-tracer",
    "odoo-reviewer",
    "odoo-bug-hunter",
    "odoo-verifier",
}


def project_root(payload: dict) -> Path:
    ws = payload.get("workspacePaths")
    if isinstance(ws, list) and ws and isinstance(ws[0], str):
        return Path(ws[0]).resolve()
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        return Path(cwd).resolve()
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return Path(__file__).resolve().parents[2]


def find_git_repos(root: Path) -> list[Path]:
    repos: list[Path] = []
    custom = root / "custom_addons"
    candidates = [custom / "gec_odoo_modules"]
    if custom.is_dir():
        for child in sorted(custom.iterdir()):
            if child.is_dir() and (child / ".git").exists() and child not in candidates:
                candidates.append(child)
    for cand in candidates:
        if cand.is_dir() and (cand / ".git").exists():
            repos.append(cand)
    return repos


def changed_files_in_repo(repo: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []

    files: list[Path] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        if "D" in status:
            continue
        rel = line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        p = repo / rel
        if p.is_file():
            files.append(p)
    return files


def check_version_bumps(repos: list[Path]) -> list[str]:
    warnings: list[str] = []
    for repo in repos:
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), "diff", "--unified=0", "--", "*__manifest__.py"],
                capture_output=True,
                text=True,
                timeout=4,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0 or not proc.stdout:
            continue
        cur_file = ""
        for line in proc.stdout.splitlines():
            if line.startswith("+++ b/"):
                cur_file = line[6:]
            elif line.startswith("+") and not line.startswith("+++") and re.search(r"['\"]version['\"]\s*:", line):
                warnings.append(f"Manifest version modified in {repo.name}/{cur_file} (Hard Rule 12 forbids version bumps unless approved).")
    return warnings


def check_leaked_scratch_dbs(root: Path) -> list[str]:
    psql = shutil.which("psql")
    if not psql:
        return []
    port = DEFAULT_V19_PORT
    conf_path = root / "odoo.conf"
    if conf_path.is_file():
        parser = configparser.ConfigParser()
        try:
            parser.read(conf_path, encoding="utf-8")
            port = parser.get("options", "db_port", fallback=DEFAULT_V19_PORT).strip() or DEFAULT_V19_PORT
        except Exception:
            pass

    cmd = [psql, "-p", port, "-d", "postgres", "-Atc", "SELECT datname FROM pg_database WHERE datname LIKE 'gec19_t_%' OR datname LIKE 'odoo_t_%'"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    leaked = [d.strip() for d in proc.stdout.splitlines() if d.strip()]
    if leaked:
        return [f"Leaked scratch test database(s) on port {port}: {', '.join(leaked)}"]
    return []


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    is_antigravity = "continuationActive" in payload or "terminationReason" in payload or "workspacePaths" in payload

    if payload.get("stop_hook_active") or payload.get("continuationActive"):
        if is_antigravity:
            print("{}")
        sys.exit(0)

    if is_antigravity and payload.get("terminationReason") not in (None, "", "NO_TOOL_CALL"):
        print("{}")
        sys.exit(0)

    root = project_root(payload)
    agent_type = (payload.get("agent_type") or "").strip().rsplit(":", 1)[-1]
    event_name = (payload.get("hook_event_name") or payload.get("hookEventName") or "Stop").strip()

    repos = find_git_repos(root)
    changed: list[Path] = []
    for repo in repos:
        changed.extend(changed_files_in_repo(repo))

    hard_notes: list[str] = []
    advisory_notes: list[str] = []

    if event_name == "SubagentStop" and agent_type in READ_ONLY_AGENTS:
        leaked = check_leaked_scratch_dbs(root)
        if leaked:
            print(json.dumps({"systemMessage": "Subagent check: " + "; ".join(leaked)}))
        sys.exit(0)

    if changed:
        checker = Path(__file__).resolve().parent / "odoo_offline_check.py"
        targets = [str(p) for p in changed[:40] if p.suffix in {".py", ".xml", ".csv", ".po", ".js"}]
        if targets and checker.is_file():
            try:
                proc = subprocess.run(
                    [sys.executable, str(checker), "--files", *targets],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.returncode != 0 and proc.stderr.strip():
                    lines = proc.stderr.strip().splitlines()[:8]
                    hard_notes.append("Modified files failed offline Odoo 19 check:\n" + "\n".join(lines))
            except (OSError, subprocess.TimeoutExpired):
                pass

    advisory_notes.extend(check_version_bumps(repos))
    hard_notes.extend(check_leaked_scratch_dbs(root))

    if is_antigravity:
        if hard_notes:
            print(json.dumps({"decision": "continue", "reason": "\n".join(hard_notes)}))
        else:
            print("{}")
        sys.exit(0)

    all_notes = hard_notes + advisory_notes
    if all_notes:
        print(json.dumps({"systemMessage": "\n".join(all_notes)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
