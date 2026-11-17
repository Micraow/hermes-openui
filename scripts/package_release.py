"""Build an installable archive from the current bundle (Python standard library)."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT / "package.json").read_text())["version"]
OUTPUT = ROOT / "local" / "releases"
OUTPUT.mkdir(parents=True, exist_ok=True)

# Hermes loads the manifest, Python registration, skill, API and browser bundle.
files = [ROOT / name for name in ("plugin.yaml", "__init__.py", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "package-lock.json")]
files.extend((ROOT / "scripts" / "install.py", ROOT / "scripts" / "__init__.py"))
for directory in ("skills", "dashboard", "docs", "desktop"):
    files.extend(path for path in (ROOT / directory).rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts
                 and "tests" not in path.relative_to(ROOT).parts and path.suffix != ".pyc")
for name in ("desktop/plugin.js", "desktop/maplibre-gl-worker.mjs"):
    if not (ROOT / name).is_file():
        raise SystemExit(f"Missing {name}; run npm run build first.")

# The browser bundle includes third-party code. Keep installed dependencies' notices.
notices = []
for manifest in sorted((ROOT / "node_modules").glob("**/package.json")):
    if manifest.parent.name == "node_modules":
        continue
    package = json.loads(manifest.read_text())
    licenses = [path for path in manifest.parent.iterdir() if path.is_file()
                and path.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE"))]
    if licenses:
        notices.append(f"\n{'=' * 72}\n{package.get('name', manifest.parent.name)} {package.get('version', '')}\n")
        notices.extend(f"\n{path.name}\n{path.read_text(errors='replace')}\n" for path in sorted(licenses))
if not notices:
    raise SystemExit("No dependency licenses found; run npm ci first.")
license_text = "Notices for bundled dependencies and build tooling.\n" + "".join(notices)
(OUTPUT / "THIRD_PARTY_LICENSES.txt").write_text(license_text)
archive = OUTPUT / f"hermes-openui-v{VERSION}.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(set(files)):
        bundle.write(path, "hermes-openui/" + path.relative_to(ROOT).as_posix())
    bundle.writestr("hermes-openui/THIRD_PARTY_LICENSES.txt", license_text)
print(archive)
