import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install.py"


class InstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hermes-openui-install-")
        self.home = Path(self.temporary.name)
        self.hermes = self.home / "fake-hermes"
        self.hermes.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json
                import os
                import sys
                from pathlib import Path

                home = Path(os.environ["HERMES_HOME"])
                with (home / "calls.log").open("a", encoding="utf-8") as log:
                    log.write(" ".join(sys.argv[1:]) + "\\n")

                args = sys.argv[1:]
                if args[:2] == ["plugins", "doctor"]:
                    print("OK: runtime discovery, manifest parsing, import, and registration passed")
                    raise SystemExit(0)
                if args[:2] == ["plugins", "enable"]:
                    print("Plugin enabled")
                    raise SystemExit(0)
                if args[:2] == ["plugins", "list"]:
                    print(json.dumps([{{
                        "name": "hermes-openui",
                        "status": "enabled",
                        "source": "user",
                    }}]))
                    raise SystemExit(0)
                raise SystemExit(2)
                """
            ),
            encoding="utf-8",
        )
        self.hermes.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_installer(
        self, *arguments: str, home: Path | None = None, binary: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "HERMES_BIN": str(binary or self.hermes),
                "HERMES_HOME": str(home or self.home),
                "NO_COLOR": "1",
            },
        )

    def test_links_agent_and_reports_browser_runtime_pending(self) -> None:
        completed = self.run_installer("--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["agent"]["ok"])
        self.assertTrue(report["skill"]["ok"])
        self.assertTrue(report["browser"]["build"])
        self.assertFalse(report["browser"]["runtime"])
        self.assertEqual(report["browser"]["activation"], "user-action-required")
        self.assertIn("Reload desktop plugins", report["finalAction"])

        agent = self.home / "plugins" / "hermes-openui"
        desktop = self.home / "desktop-plugins" / "hermes-openui"
        self.assertTrue(agent.is_symlink())
        self.assertEqual(agent.resolve(), ROOT)
        self.assertTrue((agent / "plugin.yaml").is_file())
        self.assertTrue((agent / "skills" / "openui" / "SKILL.md").is_file())
        self.assertFalse(desktop.exists())

        calls = (self.home / "calls.log").read_text()
        self.assertIn("plugins doctor --ci", calls)
        self.assertIn("plugins enable hermes-openui", calls)
        self.assertIn("plugins list --enabled --no-bundled --json", calls)

        checked = self.run_installer("--check", "--json")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertTrue(json.loads(checked.stdout)["browser"]["build"])

    def test_keeps_an_existing_user_link(self) -> None:
        user_plugin = self.home / "user-plugin"
        user_plugin.mkdir()
        (user_plugin / "plugin.yaml").write_text("name: hermes-openui\n")
        (user_plugin / "sentinel.txt").write_text("keep\n")
        (user_plugin / "desktop").mkdir()
        (user_plugin / "desktop" / "plugin.js").write_text("// user browser\n")
        (user_plugin / "desktop" / "maplibre-gl-worker.mjs").write_text("// worker\n")
        (user_plugin / "skills" / "openui").mkdir(parents=True)
        (user_plugin / "skills" / "openui" / "SKILL.md").write_text("keep skill\n")
        target = self.home / "plugins" / "hermes-openui"
        target.parent.mkdir()
        target.symlink_to(user_plugin, target_is_directory=True)

        completed = self.run_installer("--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), user_plugin)
        self.assertEqual((user_plugin / "sentinel.txt").read_text(), "keep\n")
        calls = (self.home / "calls.log").read_text()
        self.assertIn(f"plugins doctor --ci {target}\n", calls)
        self.assertNotIn(f"plugins doctor --ci {ROOT}\n", calls)

    def test_refuses_a_different_plugin_in_the_slot(self) -> None:
        target = self.home / "plugins" / "hermes-openui"
        target.mkdir(parents=True)
        (target / "plugin.yaml").write_text("name: another-plugin\n")

        completed = self.run_installer("--json")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("occupied by a different plugin", completed.stdout)
        self.assertTrue((target / "plugin.yaml").is_file())

    def test_refuses_a_non_directory_slot_without_replacing_it(self) -> None:
        target = self.home / "plugins" / "hermes-openui"
        target.parent.mkdir(parents=True)
        target.write_text("keep\n")

        completed = self.run_installer("--json")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not a plugin directory", completed.stdout)
        self.assertEqual(target.read_text(), "keep\n")

    def test_refuses_a_broken_link_without_replacing_it(self) -> None:
        target = self.home / "plugins" / "hermes-openui"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.home / "missing-plugin", target_is_directory=True)

        completed = self.run_installer("--json")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not a plugin directory", completed.stdout)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.readlink(), self.home / "missing-plugin")

    def test_named_profile_uses_the_root_desktop_runtime(self) -> None:
        profile_home = self.home / "profiles" / "work"
        profile_home.mkdir(parents=True)

        completed = self.run_installer("--json", home=profile_home)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        agent = profile_home / "plugins" / "hermes-openui"
        desktop = self.home / "desktop-plugins" / "hermes-openui"
        self.assertTrue(agent.is_symlink())
        self.assertEqual(report["browser"]["path"], str(desktop))
        self.assertFalse(desktop.exists())

    def test_reports_an_unlaunchable_hermes_cli(self) -> None:
        completed = self.run_installer(
            "--json", binary=self.home / "missing-hermes"
        )

        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertIn("Could not run Hermes CLI", report["error"])
        self.assertNotIn("Traceback", completed.stderr)

    def test_check_reports_a_missing_browser_build_without_changes(self) -> None:
        user_plugin = self.home / "user-plugin"
        user_plugin.mkdir()
        (user_plugin / "plugin.yaml").write_text("name: hermes-openui\n")
        (user_plugin / "skills" / "openui").mkdir(parents=True)
        (user_plugin / "skills" / "openui" / "SKILL.md").write_text("skill\n")
        (user_plugin / "desktop").mkdir()
        (user_plugin / "desktop" / "plugin.js").write_text("// browser\n")
        target = self.home / "plugins" / "hermes-openui"
        target.parent.mkdir()
        target.symlink_to(user_plugin, target_is_directory=True)

        completed = self.run_installer("--check", "--json")

        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertFalse(report["browser"]["build"])
        self.assertFalse(report["browser"]["runtime"])
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), user_plugin)

    def test_check_mode_is_read_only_when_installation_is_missing(self) -> None:
        completed = self.run_installer("--check", "--json")

        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertFalse(report["skill"]["ok"])
        self.assertFalse(report["browser"]["ok"])
        self.assertFalse((self.home / "plugins" / "hermes-openui").exists())
        self.assertFalse((self.home / "desktop-plugins" / "hermes-openui").exists())


if __name__ == "__main__":
    unittest.main()
