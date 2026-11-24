"""PostToolUse & CLI offline validator for Odoo 19 custom modules (dual-protocol, portable).

Verified against Odoo 19.0 FINAL source:
- Enforces Odoo 19 security (`security/ir.model.access.csv` 8-column schema + XML `ir.rule`),
  and blocks v20-only `security/ir.access.csv` / `ir.access` / `compute_sql` / OWL 3 APIs.
- Also blocks removed pre-19 APIs (`_sql_constraints`, `_name_search`, `name_get`, `<tree>`,
  `attrs=`, `states=`, `numbercall`, `groups_id` on ir.actions.*, `@api.one`/`@api.multi`, `_(f"...")`).
- Preserves valid Odoo 19 APIs (OWL 2 `useState`/`useRef`/`static props`, Font Awesome `fa fa-*`,
  `ir.attachment.datas`, `uom.rounding`, `res.partner.company_type`, `res.bank`).
- Supports Claude Code PostToolUse, Antigravity PostToolUse, and CLI `--files`.
- Runs cleanly with stdlib-only Python and uses lxml, polib, msgfmt, node, and ruff
  opportunistically when installed.
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from lxml import etree as LXML_ET
except ImportError:
    LXML_ET = None

try:
    import polib
except ImportError:
    polib = None

SKIP_PARTS = {
    "__pycache__",
    "node_modules",
    ".git",
    "migrations",
    "odoo20",
    "static/lib",
}

PROTECTED_ROOTS = {"addons", "enterprise", "odoo", ".claude", ".agents", ".backups", ".devmap"}

# Verified against odoo19 source & scripts/v20_patterns.txt
PY_V19_HARD_PATTERNS = [
    # Removed/ignored in Odoo 19
    (re.compile(r"\b_sql_constraints\s*="), "_sql_constraints is ignored in Odoo 19; use models.Constraint / models.UniqueIndex"),
    (re.compile(r"\bdef\s+name_get\s*\("), "name_get() was removed; override _compute_display_name()"),
    (re.compile(r"\bdef\s+_name_search\s*\("), "_name_search() was removed in Odoo 19; override _search_display_name()"),
    (re.compile(r"@api\.(?:one|multi)\b"), "@api.one / @api.multi were removed"),
    (re.compile(r"\b(?:_|_lt)\s*\(\s*f['\"]"), "Never pass an f-string to _() / _lt(); use static literal with %s / %(name)s args"),
    # Odoo 20-only APIs that crash Odoo 19
    (re.compile(r"\bcompute_sql\s*="), "compute_sql= is Odoo 20-only; use search= or store=True in Odoo 19"),
    (re.compile(r"['\"]ir\.access['\"]"), "ir.access is Odoo 20-only; Odoo 19 uses ir.model.access.csv + ir.rule"),
    (re.compile(r",\s*['\"]access['\"]\s*,"), "Domain 'access' operator is Odoo 20-only"),
    (re.compile(r"\bmodels\.CachedModel\b"), "models.CachedModel is Odoo 20-only"),
    (re.compile(r"\bTableSQL\b"), "TableSQL is Odoo 20-only"),
    (re.compile(r"\.(?:get|set)_(?:str|bool|int|float)\s*\("), "ir.config_parameter get_str/get_int/get_float/get_bool are Odoo 20-only; use get_param()/set_param()"),
    (re.compile(r"\buser_writeable\s*="), "user_writeable= is Odoo 20-only"),
    (re.compile(r"\bapi\.ormcache\b|from\s+odoo\.api\s+import\b.*\bormcache\b"), "odoo.api.ormcache is Odoo 20-only; use odoo.tools.ormcache in Odoo 19"),
    (re.compile(r"\binvalidate_ormcache\s*\("), "invalidate_ormcache() is Odoo 20-only"),
    (re.compile(r"\bBinary(?:Value|Bytes)\b"), "BinaryValue / BinaryBytes are Odoo 20-only"),
    (re.compile(r"\bMockHTTPClient\b"), "MockHTTPClient is Odoo 20-only"),
    (re.compile(r"dispatcher\.serialize_exception\b"), "dispatcher.serialize_exception is Odoo 20-only"),
    (re.compile(r"^\s*(?:def|class)\s+\w+\["), "PEP 695 generic syntax requires Python 3.12+; Odoo 19 supports Python 3.10+"),
    (re.compile(r"^type\s+\w+\s*="), "PEP 695 type statement requires Python 3.12+; Odoo 19 supports Python 3.10+"),
]

PY_V19_ADVISORY_PATTERNS = [
    (re.compile(r"\bcheck_access_rights\s*\("), "check_access_rights() is deprecated in Odoo 19; prefer check_access() / has_access()"),
    (re.compile(r"\bself\._(?:cr|uid|context)\b"), "self._cr/_uid/_context are deprecated in Odoo 19; prefer self.env.cr/.uid/.context"),
    (re.compile(r"\bgroup_operator\s*="), "group_operator is deprecated; prefer aggregator="),
    (re.compile(r"\btype\s*=\s*['\"]json['\"]"), "Route type='json' is deprecated in Odoo 19; prefer type='jsonrpc' or type='json2'"),
]

XML_V19_PATTERNS = [
    # Removed in Odoo 19
    (re.compile(r"<\s*tree\b"), "<tree> fails RNG validation in Odoo 19; use <list>"),
    (re.compile(r"\battrs\s*=\s*['\"]"), "attrs= is unsupported in Odoo 19; use invisible=/readonly=/required="),
    (re.compile(r"\bstates\s*=\s*['\"][^'\"]+['\"]"), "states= is unsupported in Odoo 19; use invisible=\"state ...\""),
    (re.compile(r"name\s*=\s*['\"]numbercall['\"]"), "ir.cron numbercall was removed in Odoo 19"),
    # Odoo 20-only XML that breaks Odoo 19
    (re.compile(r"model\s*=\s*['\"]ir\.access['\"]"), "ir.access is Odoo 20-only; use ir.model.access.csv + ir.rule in Odoo 19"),
    (re.compile(r"<\s*card[\s>]"), "<card> view is Odoo 20-only"),
    (re.compile(r'class\s*=\s*"[^"]*\boi\b[^"]*"\s+data-icon\s*='), "Material Symbols data-icon is Odoo 20-only; Odoo 19 uses Font Awesome"),
    (re.compile(r"\bt-call-slot\b"), "t-call-slot is OWL 3 (Odoo 20-only); Odoo 19 OWL 2 uses t-slot"),
    (re.compile(r"\bt-custom-portal\b"), "t-custom-portal is OWL 3 (Odoo 20-only)"),
    (re.compile(r'\bt-ref\s*=\s*["\']this\.'), "t-ref='this.*' is OWL 3 (Odoo 20-only); Odoo 19 OWL 2 uses useRef('name') + t-ref='name'"),
]

JS_V20_ONLY_PATTERNS = [
    (re.compile(r'import\s*\{[^}]*\bproxy\b[^}]*\}\s*from\s*["\']@odoo/owl["\']'), "OWL 3 proxy() is Odoo 20-only; Odoo 19 OWL 2 uses useState()"),
    (re.compile(r"\buseProps\s*\("), "OWL 3 useProps() is Odoo 20-only; Odoo 19 OWL 2 uses static props"),
    (re.compile(r"\buseListener\s*\("), "OWL 3 useListener() is Odoo 20-only; Odoo 19 OWL 2 uses useExternalListener()"),
    (re.compile(r"\buseLayoutEffect\s*\("), "useLayoutEffect() is Odoo 20 OWL 3 compat-only; Odoo 19 OWL 2 uses useEffect()"),
    (re.compile(r"@web/owl2/utils"), "@web/owl2/utils is Odoo 20-only"),
    (re.compile(r"\bsignal\.ref\s*\("), "OWL 3 signal.ref() is Odoo 20-only; Odoo 19 OWL 2 uses useRef()"),
]


def project_root(payload: dict | None = None) -> Path:
    if isinstance(payload, dict):
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


def find_module_dir(path: Path, root: Path) -> Path | None:
    cur = path.parent if path.is_file() or not path.exists() else path
    while cur != cur.parent:
        if (cur / "__manifest__.py").is_file():
            return cur
        if cur == root:
            break
        cur = cur.parent
    return None


def is_in_scope(resolved: Path, root: Path) -> tuple[bool, Path | None]:
    parts_str = resolved.as_posix()
    for skip in SKIP_PARTS:
        if f"/{skip}/" in parts_str or resolved.name == skip:
            return False, None

    for protected in PROTECTED_ROOTS:
        pdir = (root / protected).resolve()
        if pdir.is_dir() and resolved.is_relative_to(pdir):
            return False, None

    custom_dir = (root / "custom_addons").resolve()
    if custom_dir.is_dir() and resolved.is_relative_to(custom_dir):
        return True, find_module_dir(resolved, custom_dir)

    # Light Workspace support (e.g. manager workspace with 2-3 module folders directly under root)
    if resolved.is_relative_to(root):
        mod = find_module_dir(resolved, root)
        if mod is not None:
            return True, mod

    return False, None


def code_lines_without_strings_or_comments(source: str) -> dict[int, str]:
    lines = source.splitlines()
    keep: dict[int, list[str]] = {}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return {i: line for i, line in enumerate(lines, 1)}

    docstring_lines: set[int] = set()
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    ds = node.body[0]
                    for ln in range(ds.lineno, (ds.end_lineno or ds.lineno) + 1):
                        docstring_lines.add(ln)
    except SyntaxError:
        pass

    for tok_type, tok_str, (sline, _), _, _ in tokens:
        if tok_type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        if sline in docstring_lines:
            continue
        keep.setdefault(sline, []).append(tok_str)

    return {ln: lines[ln - 1] for ln in keep if 1 <= ln <= len(lines)}


def check_manifest(path: Path, source: str, errors: list[str], advisories: list[str]) -> None:
    try:
        data = ast.literal_eval(source)
    except Exception as exc:
        errors.append(f"{path}: __manifest__.py must be a valid Python dict literal ({exc}).")
        return
    if not isinstance(data, dict):
        errors.append(f"{path}: __manifest__.py must evaluate to a dict.")
        return

    for key in ("name", "author", "license"):
        if not data.get(key):
            errors.append(f"{path}: Odoo 19 __manifest__.py requires non-empty '{key}'.")

    version = str(data.get("version") or "")
    if re.match(r"^(?:2[0-9]|1[4-8])\.", version):
        errors.append(f"{path}: version '{version}' is not compatible with Odoo 19 (use '19.0.x.y.z' or module-local '1.0').")

    data_files = data.get("data") or []
    if isinstance(data_files, list):
        seen: set[str] = set()
        for entry in data_files:
            if not isinstance(entry, str):
                continue
            if entry in seen:
                advisories.append(f"{path}: duplicate entry '{entry}' in manifest data.")
            seen.add(entry)
            if entry.endswith("ir.access.csv"):
                errors.append(f"{path}: '{entry}' is Odoo 20-only; Odoo 19 uses security/ir.model.access.csv + ir.rule XML.")


def find_ruff() -> str | None:
    venv_ruff = Path(sys.executable).parent / "ruff"
    if venv_ruff.is_file() and os.access(venv_ruff, os.X_OK):
        return str(venv_ruff)
    return shutil.which("ruff")


def check_python(path: Path, mod_dir: Path | None, errors: list[str], advisories: list[str]) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 ({exc}).")
        return

    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        errors.append(f"{path}:{exc.lineno}: Python syntax error: {exc.msg}")
        return

    if path.name == "__manifest__.py":
        check_manifest(path, source, errors, advisories)
        return

    rel_parts = path.relative_to(mod_dir).parts if mod_dir and path.is_relative_to(mod_dir) else path.parts
    if "tests" not in rel_parts:
        all_lines = source.splitlines()
        code_map = code_lines_without_strings_or_comments(source)
        for lineno, line in sorted(code_map.items()):
            window = "\n".join(all_lines[max(0, lineno - 5):lineno])
            if re.search(r"['\"]ir\.access['\"]\s+in\b|hasattr\s*\([^)]*['\"]get_float['\"]", window):
                continue
            for regex, msg in PY_V19_HARD_PATTERNS:
                if regex.search(line):
                    errors.append(f"{path}:{lineno}: {msg}")
            for regex, msg in PY_V19_ADVISORY_PATTERNS:
                if regex.search(line):
                    advisories.append(f"{path}:{lineno}: {msg}")

    ruff_bin = find_ruff()
    if ruff_bin:
        try:
            proc = subprocess.run(
                [
                    ruff_bin, "check", "--quiet", "--output-format=concise",
                    "--select", "E9,F,B,BLE,S101,S110,S112,S113,S501,S602,SIM107,DTZ,RUF012,I",
                    "--ignore", "E501,COM812",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0 and proc.stdout.strip():
                ruff_lines = proc.stdout.strip().splitlines()[:8]
                advisories.append("ruff advisories:\n" + "\n".join(ruff_lines))
        except (OSError, subprocess.TimeoutExpired):
            pass


def check_xml(path: Path, root: Path, errors: list[str], advisories: list[str]) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 ({exc}).")
        return

    try:
        xml_root = LXML_ET.fromstring(raw.encode("utf-8")) if LXML_ET is not None else ET.fromstring(raw)
    except Exception as exc:
        errors.append(f"{path}: XML parse error: {exc}")
        return

    uncommented = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), raw, flags=re.DOTALL)
    for lineno, line in enumerate(uncommented.splitlines(), 1):
        for regex, msg in XML_V19_PATTERNS:
            if regex.search(line):
                errors.append(f"{path}:{lineno}: {msg}")

    seen_ids: set[str] = set()
    for elem in xml_root.iter():
        tag = elem.tag if isinstance(elem.tag, str) else ""
        if tag == "record":
            rec_id = elem.get("id")
            rec_model = elem.get("model") or ""
            if rec_id:
                if rec_id in seen_ids:
                    errors.append(f"{path}: duplicate <record id='{rec_id}'> in file.")
                seen_ids.add(rec_id)
            if rec_model.startswith("ir.actions."):
                for child in elem:
                    if child.tag == "field" and child.get("name") == "groups_id":
                        errors.append(f"{path}: ir.actions.* field 'groups_id' was renamed to 'group_ids' in Odoo 19.")
        if tag == "field":
            eval_expr = elem.get("eval")
            if eval_expr:
                try:
                    ast.parse(eval_expr.strip(), mode="eval")
                except SyntaxError as exc:
                    errors.append(f"{path}: invalid Python in eval=\"{eval_expr}\": {exc.msg}")

    rng_dir = root / "odoo/addons/base/rng"
    if LXML_ET is not None and rng_dir.is_dir():
        for rec in xml_root.findall(".//record[@model='ir.ui.view']"):
            if rec.find("field[@name='inherit_id']") is not None:
                continue
            arch = rec.find("field[@name='arch']")
            if arch is None or len(arch) == 0:
                continue
            view_el = arch[0]
            view_tag = view_el.tag if isinstance(view_el.tag, str) else ""
            if view_tag in {"list", "search", "calendar", "graph", "pivot", "activity"}:
                rng_file = rng_dir / f"{view_tag}_view.rng"
                if rng_file.is_file():
                    try:
                        schema = LXML_ET.RelaxNG(LXML_ET.parse(str(rng_file)))
                        if not schema.validate(view_el):
                            first_err = schema.error_log.last_error
                            errors.append(f"{path}: Odoo 19 RNG validation failed on <{view_tag}>: {first_err}")
                    except Exception:
                        pass


def check_ir_model_access_csv(path: Path, mod_dir: Path | None, errors: list[str], advisories: list[str]) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 ({exc}).")
        return

    rows = list(csv.reader(io.StringIO(raw)))
    if not rows:
        errors.append(f"{path}: empty ir.model.access.csv.")
        return

    expected_header = ["id", "name", "model_id:id", "group_id:id", "perm_read", "perm_write", "perm_create", "perm_unlink"]
    if rows[0] != expected_header:
        errors.append(f"{path}:1: header must be {','.join(expected_header)} (got {','.join(rows[0])}).")
        return

    seen_ids: set[str] = set()
    for lineno, row in enumerate(rows[1:], 2):
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) != 8:
            errors.append(f"{path}:{lineno}: expected 8 columns, got {len(row)}.")
            continue
        rid, _name, model_id, group_id, pr, pw, pc, pd = (c.strip() for c in row)
        if not rid:
            errors.append(f"{path}:{lineno}: missing id.")
        elif rid in seen_ids:
            errors.append(f"{path}:{lineno}: duplicate id '{rid}'.")
        seen_ids.add(rid)

        if not model_id:
            errors.append(f"{path}:{lineno}: missing model_id:id.")
        for pname, pval in (("perm_read", pr), ("perm_write", pw), ("perm_create", pc), ("perm_unlink", pd)):
            if pval not in {"0", "1"}:
                errors.append(f"{path}:{lineno}: {pname} must be 0 or 1 (got '{pval}').")

        if not group_id:
            errors.append(f"{path}:{lineno}: empty group_id:id in ir.model.access.csv grants access to EVERY user (portal/public included).")
        elif group_id in {"base.group_public", "base.group_portal"} and "1" in (pw, pc, pd):
            errors.append(f"{path}:{lineno}: granting write/create/unlink to '{group_id}' is forbidden.")


def check_po(path: Path, errors: list[str]) -> None:
    msgfmt = shutil.which("msgfmt")
    if msgfmt:
        try:
            proc = subprocess.run(
                [msgfmt, "--check-format", "-o", os.devnull, str(path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout).strip().splitlines()[:5]
                errors.append(f"{path}: msgfmt failed: " + " | ".join(msg))
            return
        except (OSError, subprocess.TimeoutExpired):
            pass

    if polib is not None:
        try:
            polib.pofile(str(path))
        except Exception as exc:
            errors.append(f"{path}: PO parse error: {exc}")


def check_js(path: Path, errors: list[str], advisories: list[str]) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 ({exc}).")
        return

    node = shutil.which("node")
    if node:
        try:
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=5)
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout).strip().splitlines()[:4]
                errors.append(f"{path}: JS syntax error: " + " | ".join(msg))
                return
        except (OSError, subprocess.TimeoutExpired):
            pass

    uncommented = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.DOTALL)
    for lineno, line in enumerate(uncommented.splitlines(), 1):
        code = re.sub(r"//.*$", "", line)
        for regex, msg in JS_V20_ONLY_PATTERNS:
            if regex.search(code):
                errors.append(f"{path}:{lineno}: {msg}")


def validate_file(raw_path: str, root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    advisories: list[str] = []
    if not raw_path:
        return errors, advisories

    target = Path(raw_path)
    if not target.is_absolute():
        target = root / target
    if not target.is_file():
        return errors, advisories

    resolved = target.resolve()
    in_scope, mod_dir = is_in_scope(resolved, root)
    if not in_scope:
        return errors, advisories

    name = resolved.name
    if name == "ir.access.csv":
        errors.append(f"{resolved}: security/ir.access.csv is Odoo 20-only; Odoo 19 uses security/ir.model.access.csv + ir.rule XML.")
    elif name == "ir.model.access.csv":
        check_ir_model_access_csv(resolved, mod_dir, errors, advisories)
    elif resolved.suffix == ".py":
        check_python(resolved, mod_dir, errors, advisories)
    elif resolved.suffix == ".xml":
        check_xml(resolved, root, errors, advisories)
    elif resolved.suffix == ".po":
        check_po(resolved, errors)
    elif resolved.suffix == ".js":
        check_js(resolved, errors, advisories)

    return errors, advisories


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--files", nargs="*")
    args, _ = parser.parse_known_args()
    root = project_root()

    if args.files is not None:
        all_errors: list[str] = []
        all_advisories: list[str] = []
        for f in args.files:
            errs, advs = validate_file(f, root)
            all_errors.extend(errs)
            all_advisories.extend(advs)
        for adv in all_advisories:
            print(f"[advisory] {adv}")
        for err in all_errors:
            print(f"[error] {err}", file=sys.stderr)
        sys.exit(2 if all_errors else 0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    root = project_root(payload)

    if isinstance(payload.get("toolCall"), dict):
        tc = payload["toolCall"]
        args_obj = tc.get("args") or {}
        raw_path = str(args_obj.get("Path") or "") if isinstance(args_obj, dict) else ""
        errors, _advisories = validate_file(raw_path, root)
        if errors:
            print("Offline Odoo 19 check failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        print("{}")
        sys.exit(0)

    raw_path = (
        (payload.get("tool_input") or {}).get("file_path")
        or (payload.get("tool_response") or {}).get("filePath")
        or ""
    )
    errors, advisories = validate_file(raw_path, root)
    if errors:
        print("Offline Odoo 19 check failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        sys.exit(2)
    if advisories:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Offline check advisories:\n- " + "\n- ".join(advisories[:10]),
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
