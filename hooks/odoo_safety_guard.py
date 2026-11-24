"""PreToolUse safety guard for Odoo 19 workspaces (dual-protocol: Claude Code + Antigravity).

Auto-detects stdin payload format:
- Claude Code (snake_case `tool_name` / `tool_input`): outputs `hookSpecificOutput`.
- Antigravity (camelCase `toolCall` / `workspacePaths`): outputs `{"decision": ..., "reason": ...}`.

Enforces core safety rules deterministically (stdlib-only, portable):
- Blocks editing Odoo core (addons/, enterprise/, odoo/) or ~/.odoorc.
- Enforces read-only posture for read-only subagents (`agent_type`).
- Blocks destructive DB/PG/Git/live-bank commands.
- Auto-allows safe read-only psql SELECT queries on the workspace's configured port
  (from odoo.conf if present, otherwise Odoo 19 default port 5432), while blocking or
  prompting on mutating SQL or wrong-port psql calls (e.g. hitting Odoo 20's PG 16 port).
"""
from __future__ import annotations

import configparser
import json
import os
import re
import shlex
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

ALLOWLISTED_SQL_SCRIPTS = {"db_refs.sql"}

ALLOWLISTED_READ_SCRIPTS = {
    "sweep.py",
    "map_rows.py",
    "compact_scan.py",
    "doc_link_check.py",
    "code_inventory.py",
    "dead_names.py",
    "split_check.py",
    "code_map.py",
    "module_inventory.py",
    "odoo_import_check.py",
    "odoo_offline_check.py",
}

SCRATCH_DB_RE = re.compile(r"^(?:gec19_t_|gec20_t_|odoo_t_|test_scratch_)[a-zA-Z0-9_]+$")

MUTATING_SQL_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER|LOCK|CALL|DO|MERGE)\b",
    re.IGNORECASE,
)

LIVE_BANK_RE = re.compile(
    r"bis\.bankonline\.ge|uploadpackagegel|uploadpackagesalary|"
    r"uploadpackagetreasury|uploadsingletransfersbatch",
    re.IGNORECASE,
)

DANGEROUS_PG_RE = re.compile(r"(?:^|[;&|]\s*)(?:pg_upgrade|initdb)\b")
GLOBAL_PGPORT_RE = re.compile(r"\b(?:export\s+PGPORT=|launchctl\s+setenv\s+PGPORT\b)")
ODOORC_WRITE_RE = re.compile(r"(?:>|>>|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b).*\.odoorc\b")
FORCE_PUSH_RE = re.compile(r"\bgit\b.*\bpush\b.*(?:--force(?:-with-lease)?|\s-f\b)")
HARD_RESET_RE = re.compile(r"\bgit\b.*\breset\s+--hard\b")
ODOO_SAVE_RE = re.compile(r"\bodoo-bin\b.*(?:\s-s\b|\s--save\b)")


def emit(decision: str, reason: str, mode: str) -> None:
    if mode == "antigravity":
        out = {"decision": decision}
        if reason:
            out["reason"] = reason
        print(json.dumps(out))
    else:
        if decision:
            claude_decision = "ask" if decision == "force_ask" else decision
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": claude_decision,
                    "permissionDecisionReason": reason,
                }
            }))
    sys.exit(0)


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


def read_odoo_conf(root: Path) -> dict[str, str]:
    conf_path = root / "odoo.conf"
    if not conf_path.is_file():
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(conf_path, encoding="utf-8")
        return dict(parser["options"]) if "options" in parser else {}
    except Exception:
        return {}


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def check_file_tool(raw_path: str, agent_type: str, root: Path, mode: str) -> None:
    if agent_type in READ_ONLY_AGENTS:
        emit("deny", f"Read-only agent '{agent_type}' cannot modify files.", mode)

    if not raw_path:
        emit("allow" if mode == "antigravity" else "", "", mode)

    target = Path(raw_path)
    if not target.is_absolute():
        target = root / target
    resolved = target.resolve()

    home = Path.home().resolve()
    if resolved in {home / ".odoorc", home / ".openerp_serverrc"}:
        emit("deny", "Never modify ~/.odoorc; pass CLI flags or use a project odoo.conf.", mode)

    for protected in ("addons", "enterprise", "odoo"):
        core_dir = (root / protected).resolve()
        if core_dir.is_dir() and resolved.is_relative_to(core_dir):
            emit("deny", f"Odoo core directory '{protected}/' is read-only.", mode)

    if mode == "antigravity":
        emit("allow", "", mode)


def parse_psql(cmd: str, conf: dict[str, str], agent_type: str, mode: str) -> None:
    if r"\!" in cmd or re.search(r"\\[ow]\b", cmd):
        emit("deny", "psql shell escapes (\\!) and file output (\\o/\\w) are blocked.", mode)

    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    port = None
    sql_chunks = []
    file_args = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-p", "--port") and i + 1 < len(tokens):
            port = tokens[i + 1]
            i += 2
            continue
        if tok.startswith("--port="):
            port = tok.split("=", 1)[1]
        elif tok.startswith("-p") and len(tok) > 2 and tok[2:].isdigit():
            port = tok[2:]
        elif tok in ("-c", "--command") and i + 1 < len(tokens):
            sql_chunks.append(tokens[i + 1])
            i += 2
            continue
        elif tok.startswith("--command="):
            sql_chunks.append(tok.split("=", 1)[1])
        elif tok in ("-f", "--file") and i + 1 < len(tokens):
            file_args.append(tokens[i + 1])
            i += 2
            continue
        elif tok.startswith("--file="):
            file_args.append(tok.split("=", 1)[1])
        i += 1

    ask_decision = "force_ask" if mode == "antigravity" else "ask"

    for fpath in file_args:
        if Path(fpath).name not in ALLOWLISTED_SQL_SCRIPTS:
            if agent_type in READ_ONLY_AGENTS:
                emit("deny", f"Read-only agent cannot run arbitrary SQL file '{fpath}'.", mode)
            emit(ask_decision, f"Running SQL file '{fpath}' requires user confirmation.", mode)

    combined_sql = strip_sql_comments("\n".join(sql_chunks))
    if re.search(r"\bDROP\s+DATABASE\b", combined_sql, re.IGNORECASE):
        match = re.search(r"\bDROP\s+DATABASE\s+(?:IF\s+EXISTS\s+)?\"?([a-zA-Z0-9_]+)\"?", combined_sql, re.IGNORECASE)
        db = match.group(1) if match else ""
        if agent_type in READ_ONLY_AGENTS or not SCRATCH_DB_RE.match(db):
            emit("deny", f"DROP DATABASE blocked (only scratch DBs matching {SCRATCH_DB_RE.pattern} may be dropped).", mode)

    if MUTATING_SQL_RE.search(combined_sql):
        if agent_type in READ_ONLY_AGENTS:
            emit("deny", f"Read-only agent '{agent_type}' may only execute SELECT queries.", mode)
        emit(ask_decision, "Mutating psql statement requires explicit user confirmation.", mode)

    expected_port = (conf.get("db_port") or DEFAULT_V19_PORT).strip()
    if port and port != expected_port:
        emit(
            ask_decision,
            f"psql port mismatch: Odoo 19 workspace expects port {expected_port}, got -p {port}. Confirm target server.",
            mode,
        )
    if conf.get("db_port") and not port:
        emit(
            ask_decision,
            f"psql without -p {expected_port} may connect to the wrong PostgreSQL server. Confirm target server.",
            mode,
        )

    if (sql_chunks or file_args or re.search(r"\s-l\b", cmd)) and not re.search(r"[;&|`]\s*(?!psql\b)", cmd):
        emit("allow", f"Read-only psql query on expected Odoo 19 port ({expected_port}).", mode)


def check_read_only_bash(cmd: str, agent_type: str, mode: str) -> None:
    cleaned = re.sub(r"\b2>&1\b|\b2>/dev/null\b|>/dev/null\b", "", cmd)
    if re.search(r"(?:^|[^0-9])>>?\s*[^\s&]", cleaned):
        emit("deny", f"Read-only agent '{agent_type}' cannot redirect output to files.", mode)

    mutators = (
        r"\b(?:rm|mv|cp|chmod|chown|mkdir|touch|tee|dropdb|createdb|psql\b.*(?:INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE))\b|"
        r"\bsed\s+-i\b|\bperl\s+-[a-z]*i\b|"
        r"\bgit\s+(?:-C\s+\S+\s+)?(?:commit|push|checkout|switch|reset|clean|add|apply|stash|merge|rebase)\b|"
        r"\bpip3?\s+install\b|\bbrew\s+services\b"
    )
    if re.search(mutators, cmd):
        emit("deny", f"Read-only agent '{agent_type}' cannot run mutating shell commands.", mode)

    if re.search(r"\bodoo-bin\b", cmd):
        if agent_type == "odoo-verifier":
            # Allow verifier only with --test-enable against a test DB (never -s/--save)
            if "--test-enable" in cmd:
                return
            emit("deny", "odoo-verifier may only run odoo-bin with --test-enable on a named test database.", mode)
        emit("deny", f"Read-only agent '{agent_type}' cannot run odoo-bin.", mode)

    if re.search(r"\bpython(?:3(?:\.\d+)?)?\b", cmd):
        if agent_type == "odoo-verifier" and ("test_run.py" in cmd or "--test-enable" in cmd):
            return
        if re.search(r"\b-m\s+py_compile\b", cmd):
            return
        if any(script in cmd for script in ALLOWLISTED_READ_SCRIPTS):
            return
        if "xml.etree.ElementTree" in cmd and "ET.parse" in cmd and "write" not in cmd:
            return
        emit("deny", f"Read-only agent '{agent_type}' may only invoke allowlisted read-only Python checks.", mode)


def check_bash_tool(cmd: str, bypass_sandbox: bool, agent_type: str, root: Path, mode: str) -> None:
    if not cmd:
        emit("allow" if mode == "antigravity" else "", "", mode)

    conf = read_odoo_conf(root)
    ask_decision = "force_ask" if mode == "antigravity" else "ask"

    if DANGEROUS_PG_RE.search(cmd):
        emit("deny", "pg_upgrade and initdb are blocked by project safety rules.", mode)
    if GLOBAL_PGPORT_RE.search(cmd):
        emit("deny", "Never set PGPORT globally; pass -p <port> per command.", mode)
    if ODOORC_WRITE_RE.search(cmd):
        emit("deny", "Never modify ~/.odoorc.", mode)
    if ODOO_SAVE_RE.search(cmd):
        emit("deny", "Never run odoo-bin with -s/--save.", mode)
    if LIVE_BANK_RE.search(cmd):
        emit("deny", "Live bank payment/upload endpoints are blocked.", mode)
    if FORCE_PUSH_RE.search(cmd):
        emit("deny", "Force push is blocked; ask the user to run it manually if intended.", mode)
    if HARD_RESET_RE.search(cmd):
        emit(ask_decision, "git reset --hard discards uncommitted work; requires user confirmation.", mode)

    if re.search(r"\brm\b", cmd):
        data_dir = (conf.get("data_dir") or "").strip()
        if re.search(r"postgresql(?:@\d+)?|pgdata|/var/lib/postgresql", cmd, re.IGNORECASE):
            emit("deny", "Deleting PostgreSQL data directories is blocked.", mode)
        if data_dir and data_dir in cmd and not re.search(r"filestore/(?:gec19_t_|gec20_t_|odoo_t_|test_scratch_)", cmd):
            emit("deny", f"Deleting Odoo data_dir ({data_dir}) is blocked (except scratch test filestores).", mode)

    drop_match = re.search(r"\bdropdb\b(?:\s+-[^\s]+(?:\s+[^\s-]+)?)*\s+([a-zA-Z0-9_.-]+)", cmd)
    if drop_match:
        target_db = drop_match.group(1)
        if agent_type in READ_ONLY_AGENTS or not SCRATCH_DB_RE.match(target_db):
            emit("deny", f"dropdb '{target_db}' blocked (only scratch DBs matching {SCRATCH_DB_RE.pattern} may be dropped).", mode)

    if agent_type in READ_ONLY_AGENTS:
        check_read_only_bash(cmd, agent_type, mode)

    if re.search(r"(?:^|[;&|]\s*)(?:\S*/)?psql\b", cmd):
        parse_psql(cmd, conf, agent_type, mode)

    if mode == "antigravity":
        if bypass_sandbox:
            emit("ask", "Command requests unsandboxed execution.", mode)
        emit("allow", "", mode)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    root = project_root(payload)

    if isinstance(payload.get("toolCall"), dict):
        tc = payload["toolCall"]
        tname = (tc.get("name") or "").strip()
        args = tc.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        if tname in {"edit_file", "write_file"}:
            check_file_tool(str(args.get("Path") or ""), "", root, "antigravity")
        elif tname == "run_command":
            check_bash_tool(
                str(args.get("CommandLine") or "").strip(),
                bool(args.get("BypassSandbox")),
                "",
                root,
                "antigravity",
            )
        else:
            emit("allow", "", "antigravity")
        return

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        sys.exit(0)
    agent_type = (payload.get("agent_type") or "").strip().rsplit(":", 1)[-1]

    if tool_name in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        check_file_tool(str(raw), agent_type, root, "claude")
    elif tool_name == "Bash":
        check_bash_tool(str(tool_input.get("command") or "").strip(), False, agent_type, root, "claude")


if __name__ == "__main__":
    main()
