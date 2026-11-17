#!/usr/bin/env python3
"""Link, enable, and check Hermes OpenUI through Hermes' public CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_NAME = "hermes-openui"
SKILL_NAME = "hermes-openui:openui"
SOURCE_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_FILES = ("plugin.js", "maplibre-gl-worker.mjs")
FINAL_ACTION = (
    "In Hermes Desktop, run 'Reload desktop plugins' if the browser runtime is "
    "pending, then open Skills & Tools -> Plugins, select the installed OpenUI "
    "cards (hermes-openui) package, and turn on its Desktop switch. "
    "Settings -> Plugins only configures the Agent half."
)


class InstallError(RuntimeError):
    """An installation precondition or public Hermes command failed."""


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().resolve()


def hermes_root() -> Path:
    home = hermes_home()
    return home.parent.parent if home.parent.name == "profiles" else home


def run_hermes(*args: str) -> str:
    executable = os.environ.get("HERMES_BIN", "").strip() or shutil.which("hermes")
    if not executable:
        raise InstallError("Hermes CLI not found. Put `hermes` on PATH or set HERMES_BIN.")
    try:
        completed = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HERMES_HOME": str(hermes_home()), "NO_COLOR": "1"},
        )
    except OSError as exc:
        raise InstallError(f"Could not run Hermes CLI `{executable}`: {exc}") from exc
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode:
        raise InstallError(
            f"`{' '.join([executable, *args])}` failed:\n{output.strip()}"
        )
    return output


def manifest_name(path: Path) -> str | None:
    try:
        for line in (path / "plugin.yaml").read_text(encoding="utf-8").splitlines():
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return None


def installed_plugins() -> dict[str, dict]:
    output = run_hermes(
        "plugins", "list", "--enabled", "--no-bundled", "--json"
    )
    try:
        rows = json.loads(output)
    except ValueError as exc:
        raise InstallError("Hermes returned invalid JSON for the plugin list.") from exc
    if not isinstance(rows, list):
        raise InstallError("Hermes returned an unexpected plugin list.")
    return {
        str(row["name"]): row
        for row in rows
        if isinstance(row, dict) and row.get("name")
    }


def ensure_agent_link(check_only: bool) -> tuple[Path, bool]:
    target = hermes_home() / "plugins" / PLUGIN_NAME
    if target.exists() or target.is_symlink():
        if not target.is_dir():
            raise InstallError(
                f"{target} is occupied by something that is not a plugin directory; "
                "no files were changed."
            )
        if manifest_name(target) != PLUGIN_NAME:
            raise InstallError(
                f"{target} is occupied by a different plugin; no files were changed."
            )
        return target, False
    if check_only:
        return target, False

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(SOURCE_ROOT, target_is_directory=True)
    except OSError as exc:
        raise InstallError(
            f"Could not link {SOURCE_ROOT} to {target}. On Windows, enable Developer "
            "Mode or install the plugin directory manually."
        ) from exc
    return target, True


def runtime_status(agent_target: Path) -> tuple[bool, bool]:
    build_ok = agent_target.is_dir() and all(
        (agent_target / "desktop" / name).is_file() for name in DESKTOP_FILES
    )
    runtime = hermes_root() / "desktop-plugins" / PLUGIN_NAME
    marker = runtime / ".hermes-package.json"
    runtime_ok = build_ok and marker.is_file()
    if runtime_ok:
        try:
            runtime_ok = all(
                (runtime / name).is_file()
                and (runtime / name).read_bytes()
                == (agent_target / "desktop" / name).read_bytes()
                for name in DESKTOP_FILES
            )
        except OSError:
            runtime_ok = False
    return build_ok, runtime_ok


def report(check_only: bool) -> dict:
    agent_path, linked = ensure_agent_link(check_only)
    if not check_only:
        run_hermes("plugins", "doctor", "--ci", str(agent_path))
        run_hermes("plugins", "enable", PLUGIN_NAME)

    plugin = installed_plugins().get(PLUGIN_NAME, {})
    agent_ok = plugin.get("status") == "enabled"
    skill_path = agent_path / "skills" / "openui" / "SKILL.md"
    skill_ok = agent_ok and skill_path.is_file()
    build_ok, runtime_ok = runtime_status(agent_path)
    return {
        "hermesHome": str(hermes_home()),
        "linked": linked,
        "agent": {
            "ok": agent_ok,
            "enabled": agent_ok,
            "source": plugin.get("source"),
            "path": str(agent_path),
        },
        "skill": {
            "ok": skill_ok,
            "name": SKILL_NAME,
            "path": str(skill_path),
        },
        "browser": {
            "ok": build_ok,
            "build": build_ok,
            "runtime": runtime_ok,
            "path": str(hermes_root() / "desktop-plugins" / PLUGIN_NAME),
            "activation": "user-action-required",
        },
        "finalAction": FINAL_ACTION,
    }


def print_human(value: dict) -> None:
    print(
        f"Agent    {'OK' if value['agent']['ok'] else 'MISSING':<9}"
        f"{'enabled' if value['agent']['ok'] else 'not enabled'}"
    )
    print(
        f"Skill    {'OK' if value['skill']['ok'] else 'MISSING':<9}"
        f"{SKILL_NAME}"
    )
    runtime = "runtime installed" if value["browser"]["runtime"] else "runtime pending"
    print(
        f"Browser  {'BUILD OK' if value['browser']['build'] else 'MISSING':<9}"
        f"{runtime}; activation is user-controlled"
    )
    print(f"\nFinal step:\n  {FINAL_ACTION}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Link, enable, and check Hermes OpenUI with Hermes' public CLI."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report Agent, Skill, and Browser status without changing files.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    args = parser.parse_args()
    try:
        value = report(args.check)
    except InstallError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(value, indent=2))
    else:
        print_human(value)
    return 0 if value["agent"]["ok"] and value["skill"]["ok"] and value["browser"]["build"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
