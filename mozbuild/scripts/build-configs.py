#!/usr/bin/env python3
"""
(SheepFox) Zen browser — modular configuration compiler.

Reads every ``config/modules/*.js`` file and generates two artifacts:

``config/user.js``
    A plain ``user_pref()`` profile file for Zen Browser and stock Firefox
    (drop-in mode).

``config/autoconfig/sheepfox.cfg``
    A system AutoConfig file. ``lockPref()`` is emitted **only** for lines that
    carry a ``// @lock`` annotation (telemetry, studies, ads, Pocket and the ML
    master switch); every other preference becomes ``defaultPref()`` so users
    can still change it from ``about:preferences``.

The compiler is deliberately strict: duplicate preferences, malformed value
literals and unknown pref types are hard errors, so CI can never publish a
broken build.

Usage
-----
    python3 mozbuild/scripts/build-configs.py            # regenerate
    python3 mozbuild/scripts/build-configs.py --check    # verify in CI
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = REPO_ROOT / "config" / "modules"
USER_JS_OUT = REPO_ROOT / "config" / "user.js"
CFG_OUT = REPO_ROOT / "config" / "autoconfig" / "sheepfox.cfg"

#: ``user_pref("name", <json literal>); // optional trailing comment``
PREF_RE = re.compile(
    r'^(?P<indent>[ \t]*)user_pref\(\s*"(?P<name>[^"]+)"\s*,\s*(?P<value>.+?)\s*\)\s*;(?P<trail>.*)$'
)
LOCK_RE = re.compile(r"//\s*@lock\b")
COMMENT_RE = re.compile(r"//\s?(?P<text>.*)$")


class ConfigError(Exception):
    """Raised when a module cannot be compiled."""


@dataclass(frozen=True)
class Pref:
    """A single validated preference declaration."""

    name: str
    value_text: str
    locked: bool
    trailing: str
    source: str
    line: int


@dataclass(frozen=True)
class Module:
    """A parsed module file: its prefs plus the comment lines around them."""

    filename: str
    lines: tuple[str, ...]
    pref_indexes: tuple[int, ...]
    prefs: tuple[Pref, ...]


def _parse_value(raw: str, where: str) -> str:
    """Validate that *raw* is a JSON literal Firefox can store in a pref."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{where}: value {raw!r} is not a valid JSON literal ({exc.msg})"
        ) from exc

    if isinstance(value, bool) or isinstance(value, str):
        return raw
    if isinstance(value, int):
        # Reject bools masquerading as ints (json handles those above).
        return raw
    raise ConfigError(
        f"{where}: value {raw!r} has unsupported type {type(value).__name__}; "
        "Firefox prefs may only be bool, int or string"
    )


def parse_module(path: Path) -> Module:
    """Parse one module, validating every pref declaration."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise ConfigError(f"cannot read {path}: {exc}") from exc

    if "\r" in text:
        raise ConfigError(f"{path.name}: CRLF line endings are not allowed; use LF")

    raw_lines = text.splitlines()
    lines: list[str] = []
    pref_indexes: list[int] = []
    prefs: list[Pref] = []

    for lineno, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("//"):
            lines.append(raw.rstrip())
            continue

        match = PREF_RE.match(raw.rstrip())
        if match is None:
            raise ConfigError(
                f"{path.name}:{lineno}: unsupported statement {stripped!r}; "
                "modules may only contain comments and user_pref() calls"
            )

        name = match.group("name").strip()
        if not name:
            raise ConfigError(f"{path.name}:{lineno}: empty preference name")
        if not re.fullmatch(r"[A-Za-z0-9._\-]+", name):
            raise ConfigError(
                f"{path.name}:{lineno}: preference name {name!r} contains illegal characters"
            )

        where = f"{path.name}:{lineno}: pref {name!r}"
        value_text = _parse_value(match.group("value").strip(), where)
        trail = match.group("trail").strip()
        locked = bool(LOCK_RE.search(trail))

        # Normalise the trailing comment so the lock marker is not duplicated.
        comment_match = COMMENT_RE.match(trail)
        trailing = ""
        if comment_match:
            body = comment_match.group("text").strip()
            body = LOCK_RE.sub("", body).strip()
            trailing = body

        pref_indexes.append(len(lines))
        lines.append(f'user_pref("{name}", {value_text});')
        prefs.append(
            Pref(
                name=name,
                value_text=value_text,
                locked=locked,
                trailing=trailing,
                source=path.name,
                line=lineno,
            )
        )

    if not prefs:
        raise ConfigError(f"{path.name}: module declares no preferences")

    return Module(
        filename=path.name,
        lines=tuple(lines),
        pref_indexes=tuple(pref_indexes),
        prefs=tuple(prefs),
    )


def load_modules() -> list[Module]:
    """Load every module in ``config/modules`` in filename order."""
    if not MODULES_DIR.is_dir():
        raise ConfigError(f"module directory not found: {MODULES_DIR}")

    paths = sorted(MODULES_DIR.glob("*.js"))
    if not paths:
        raise ConfigError(f"no modules found in {MODULES_DIR}")

    modules = [parse_module(path) for path in paths]

    seen: dict[str, Pref] = {}
    for module in modules:
        for pref in module.prefs:
            key = pref.name.casefold()
            if key in seen:
                first = seen[key]
                raise ConfigError(
                    f"duplicate preference {pref.name!r}: declared at "
                    f"{pref.source}:{pref.line} and again at {first.source}:{first.line}"
                )
            seen[key] = pref

    return modules


def _iter_lines(module: Module):
    """Yield ``(line, pref)`` pairs, where *pref* is None for comment lines."""
    prefs = dict(zip(module.pref_indexes, module.prefs))
    for index, line in enumerate(module.lines):
        yield line, prefs.get(index)


def _counts(modules: list[Module]) -> tuple[int, int]:
    total = sum(len(module.prefs) for module in modules)
    locked = sum(1 for module in modules for pref in module.prefs if pref.locked)
    return total, locked


def render_user_js(modules: list[Module]) -> str:
    """Render the unified ``user.js`` profile file."""
    total, locked = _counts(modules)
    names = ", ".join(module.filename for module in modules)
    out: list[str] = [
        "// ============================================================================",
        "// (SheepFox) Zen browser — Unified Profile Configuration (config/user.js)",
        "// Brave-class Gecko speed + LibreFox-grade privacy, with zero site breakage.",
        "// Works drop-in on Zen Browser and Mozilla Firefox.",
        "// License: Mozilla Public License 2.0 (MPL-2.0)",
        "//",
        "// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.",
        "// Edit config/modules/*.js and run:  make build-configs",
        f"// Modules: {names}",
        f"// Preferences: {total} ({locked} locked in the system AutoConfig)",
        "//",
        "// `// @lock` annotations are inert here: they only promote a preference to",
        "// lockPref() inside config/autoconfig/sheepfox.cfg.",
        "// ============================================================================",
        "",
    ]

    for module in modules:
        out.append("")
        out.append(f"// ---------------------------------------------------------------------------")
        out.append(f"// Source module: config/modules/{module.filename}")
        out.append(f"// ---------------------------------------------------------------------------")
        for index, line in enumerate(module.lines):
            if index in module.pref_indexes:
                pref = module.prefs[module.pref_indexes.index(index)]
                rendered = f'user_pref("{pref.name}", {pref.value_text});'
                if pref.locked:
                    rendered += " // @lock"
                elif pref.trailing:
                    rendered += f" // {pref.trailing}"
                out.append(rendered)
            else:
                out.append(line)

    text = "\n".join(out).rstrip() + "\n"
    if not text.startswith("//"):
        raise ConfigError("internal error: user.js must start with a comment")
    if re.search(r"^\s*(?:lockPref|defaultPref)\(", text, re.MULTILINE):
        raise ConfigError("internal error: user.js must not contain AutoConfig calls")
    return text


def render_cfg(modules: list[Module]) -> str:
    """Render the ``sheepfox.cfg`` system AutoConfig file."""
    total, locked = _counts(modules)
    names = ", ".join(module.filename for module in modules)
    out: list[str] = [
        "// (SheepFox) Zen browser — System AutoConfig (sheepfox.cfg)",
        "// Line 1 MUST stay a comment: Gecko skips the first line of every .cfg.",
        "//",
        "// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.",
        "// Edit config/modules/*.js and run:  make build-configs",
        f"// Modules: {names}",
        f"// Preferences: {total} ({locked} lockPref / {total - locked} defaultPref)",
        "//",
        "// lockPref() is used ONLY for lines annotated `// @lock` (telemetry, remote",
        "// studies, sponsored ads, Pocket and the ML master switch). Everything else",
        "// is defaultPref(), so it stays editable in about:preferences.",
        "// Installed alongside defaults/pref/local-settings.js.",
        "// ============================================================================",
        "",
    ]

    for module in modules:
        out.append("")
        out.append("// ---------------------------------------------------------------------------")
        out.append(f"// Source module: config/modules/{module.filename}")
        out.append("// ---------------------------------------------------------------------------")
        for line, pref in _iter_lines(module):
            if pref is not None:
                fn = "lockPref" if pref.locked else "defaultPref"
                rendered = f'{fn}("{pref.name}", {pref.value_text});'
                if pref.trailing:
                    rendered += f" // {pref.trailing}"
                out.append(rendered)
            else:
                out.append(line)

    text = "\n".join(out).rstrip() + "\n"

    # Structural invariants required by Firefox's AutoConfig loader.
    first = text.splitlines()[0]
    if not first.startswith("//"):
        raise ConfigError("sheepfox.cfg line 1 must be a // comment")
    if re.search(r"^\s*user_pref\(", text, re.MULTILINE):
        raise ConfigError("sheepfox.cfg must not contain user_pref() calls")
    if re.search(r"^\s*//\s*@lock\s*$", text, re.MULTILINE):
        raise ConfigError("sheepfox.cfg must not contain bare @lock annotations")
    return text


def _read(path: Path) -> str:
    """Read *path* as UTF-8 (returning '' when it does not exist)."""
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path: Path, text: str) -> None:
    """Write *text* as UTF-8 with LF endings on every platform."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _report_diff(path: Path, current: str, expected: str) -> None:
    """Print a readable unified diff for a stale generated file."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=f"a/{rel} (on disk)",
        tofile=f"b/{rel} (expected)",
        n=3,
    )
    sys.stderr.writelines(diff)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build-configs.py",
        description="Compile config/modules/*.js into user.js and sheepfox.cfg.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed artifacts are in sync; exit 1 if not",
    )
    args = parser.parse_args(argv)

    try:
        modules = load_modules()
        user_js = render_user_js(modules)
        cfg = render_cfg(modules)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    total, locked = _counts(modules)
    stale: list[str] = []

    for path, expected in ((USER_JS_OUT, user_js), (CFG_OUT, cfg)):
        current = _read(path)
        rel = path.relative_to(REPO_ROOT).as_posix()
        if current == expected:
            if not args.check:
                print(f"  unchanged  {rel}")
            continue
        if args.check:
            stale.append(rel)
            _report_diff(path, current, expected)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write(path, expected)
            print(f"  written    {rel}")

    if args.check:
        if stale:
            print(
                "error: generated configs are stale: "
                + ", ".join(stale)
                + "\n       run: python3 mozbuild/scripts/build-configs.py",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK  config modules and generated configs are in sync "
            f"({len(modules)} modules, {total} prefs, {locked} locked)"
        )
        return 0

    print(
        f"Built {total} preferences from {len(modules)} modules "
        f"({locked} lockPref / {total - locked} defaultPref)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
