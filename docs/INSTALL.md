# Install Hermes OpenUI

Hermes OpenUI has two runtime halves and one authoring Skill:

- the agent plugin under `$HERMES_HOME/plugins/hermes-openui/`
- the built browser bundle under that package's `desktop/` directory
- the bundled `hermes-openui:openui` Skill

Keep them together. The plugin registers the Skill from its own package; there
is no separate installation or generated copy.

## Requirements

- Hermes 0.23.1 or newer, with a Webapp or Desktop chat surface
- Python 3.10 or newer for the installer
- Node.js 22.15.0 or newer and npm when building or testing from source
- POSIX shell commands for the example below

Hermes profiles are isolated by `HERMES_HOME`. If the Webapp serves a named
profile, install into that profile's home rather than the default `~/.hermes`.
The installer looks for `hermes` on `PATH`; set `HERMES_BIN` when it is
installed elsewhere.

## Download v0.1.1

The release archive includes the built browser bundle and installer, so it
needs no Node.js installation:

[Download hermes-openui-v0.1.1.zip](https://github.com/Micraow/hermes-openui/releases/download/v0.1.1/hermes-openui-v0.1.1.zip)

```sh
unzip hermes-openui-v0.1.1.zip
cd hermes-openui
```

This directory contains `plugin.yaml` and the built browser bundle. Skip the
source build and continue with **Install and check the serving profile**.

## Build from source

```sh
git clone https://github.com/Micraow/hermes-openui.git
cd hermes-openui
npm ci
npm run build
```

The build writes:

```text
desktop/plugin.js
desktop/maplibre-gl-worker.mjs
```

Both files must remain in the installed desktop bundle.

## Install and check the serving profile

The default profile home is `~/.hermes`. From the archive or source directory:

```sh
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
python3 scripts/install.py
```

The installer:

- links this directory into an empty
  `$HERMES_HOME/plugins/hermes-openui/` slot;
- keeps a pre-existing plugin slot or link unchanged;
- runs `hermes plugins doctor` and
  `hermes plugins enable hermes-openui`;
- verifies the bundled `hermes-openui:openui` Skill;
- validates the prebuilt `desktop/plugin.js` and MapLibre worker;
- reports whether Hermes Desktop has already materialized that build under the
  app-level `desktop-plugins/hermes-openui/` directory at the Hermes root.

Hermes starts noninteractive installs disabled. The installer deliberately
enables the Agent half after the public Plugin Doctor check; the Desktop
browser switch remains a separate user choice.

It reports the three states separately:

```text
Agent    OK       enabled
Skill    OK       hermes-openui:openui installed
Browser  BUILD OK runtime pending; activation is user-controlled
```

`runtime pending` means the prebuilt browser package is valid but a Desktop
rescan is still required. The installer does not call Hermes' private
reconciliation implementation or write Desktop's UI preference database.

Run a read-only check at any time:

```sh
python3 scripts/install.py --check
```

For a named Hermes profile, set its home explicitly:

```sh
export HERMES_HOME="$HOME/.hermes/profiles/<profile-name>"
python3 scripts/install.py
```

The Agent half is installed in `$HERMES_HOME/plugins/hermes-openui/`. Hermes
keeps Desktop plugins at the app level, so a profile home below
`profiles/<name>` is paired with the Hermes root's `desktop-plugins/`
directory.

The installer does not restart the gateway and does not change Hermes itself.
Start a new chat after installation. Reopen the Webapp if an already-open tab
does not refresh its plugin catalog.

## Enable the browser half

If the status says `runtime pending`, open the Hermes Desktop command palette
and run **Reload desktop plugins**. Then open **Capabilities → Plugins** and
turn on the Desktop switch for **OpenUI cards** (`hermes-openui`).

Hermes deliberately starts the browser half of a unified package off. The
plugin's browser toggle is separate from `hermes plugins enable`, which gates
the agent-side code and Skill. Hermes exposes no public command for
materializing the browser copy into a running Desktop or for setting this
Desktop-only switch. The installer reports the build and copy state while
leaving reconciliation and activation to these documented Desktop operations.

## First answer

Start a new chat and invoke the Skill explicitly:

```text
/hermes-openui:openui Compare three retrieval strategies with clearly labeled illustrative scores. Let me switch the metric, adjust a threshold, and request a deeper explanation.
```

The card should begin rendering before the assistant message finishes. Its
controls become interactive once the OpenUI source is complete.

## Update

For a linked development checkout:

```sh
git pull --ff-only
npm ci
npm run build
python3 scripts/install.py
```

The installer detects the existing link and does not replace it. Desktop's
linked-source watcher refreshes the browser copy after the build changes.

## Verify

Run the installer's read-only status check:

```sh
python3 scripts/install.py --check
```

In a new chat, the prompt above should create one visible interactive card. The
OpenUI source itself must not appear as text in the transcript.

## Troubleshooting

**The Skill does not appear.** Run `python3 scripts/install.py --check`. If
`Agent` or `Skill` is missing, run the installer without `--check`, then start
a new chat. The Skill is namespaced as `hermes-openui:openui`.

**Text works but no card appears.** Run `python3 scripts/install.py --check`.
If Browser reports `runtime pending`, run **Reload desktop plugins** in the
Desktop command palette. After the copy is present, enable **OpenUI cards**
under **Capabilities → Plugins**. This is separate from `hermes plugins
enable`; Agent and Skill status do not prove browser activation.

If the transcript shows the literal `::openui{id="…"}` directive, no browser
contribution claimed the directive. If the installer reports the browser build
missing, rebuild or reinstall the package. If the runtime is pending, use
**Reload desktop plugins** from the command palette, then enable the Desktop
switch for **OpenUI cards**.

**The transcript says “Interactive card unavailable.”** The model returned an
incomplete or invalid source envelope. Ask again with
`/hermes-openui:openui`; this plugin does not silently repair model output.

**A selected value resets near completion.** Hermes 0.23.1 can replace
transcript DOM while a message settles. The plugin persists completed card
state per session, but it cannot prevent every host remount during finalization.

**Images or maps do not load.** Those components require outbound network
access. Photo captions, source links, and a direct place link remain available
when optional media fails.

**Query data fails.** Follow [QUERY.md](QUERY.md). The card reports missing
configuration and upstream failures with a visible retry control.
