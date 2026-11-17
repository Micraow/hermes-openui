# Install Hermes OpenUI

Hermes OpenUI has two runtime halves and one authoring Skill:

- the agent plugin under `$HERMES_HOME/plugins/hermes-openui/`
- the built browser bundle under that package's `desktop/` directory
- the bundled `hermes-openui:openui` Skill

Keep them together. The plugin registers the Skill from its own package; there
is no separate installation or generated copy.

## Requirements

- Hermes 0.23.1 or newer, with a Webapp or Desktop chat surface
- Node.js 22.15.0 or newer and npm when building or testing from source
- POSIX shell commands for the example below

Hermes profiles are isolated by `HERMES_HOME`. If the Webapp serves a named
profile, install into that profile's home rather than the default `~/.hermes`.

## Download v0.1.0

The release archive includes the built browser bundle, so it needs no Node.js
installation:

[Download hermes-openui-v0.1.0.zip](https://github.com/Micraow/hermes-openui/releases/download/v0.1.0/hermes-openui-v0.1.0.zip)

```sh
unzip hermes-openui-v0.1.0.zip
cd hermes-openui
```

This directory contains `plugin.yaml` and the built browser bundle. Skip the
source build and continue with **Install into the serving profile**.

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

## Install into the serving profile

The default profile home is `~/.hermes`. Set the profile that serves the
Webapp:

```sh
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins"
ln -s "$PWD" "$HERMES_HOME/plugins/hermes-openui"
```

For a named Hermes profile, use its home explicitly:

```sh
export HERMES_HOME="$HOME/.hermes/profiles/<profile-name>"
```

On a first install, the target does not exist yet. If it already exists, inspect
it before replacing anything. A stale development symlink can be removed after
checking it with:

```sh
ls -ld "$HERMES_HOME/plugins/hermes-openui"
readlink "$HERMES_HOME/plugins/hermes-openui"
```

## Validate and enable

Run the real Hermes plugin doctor from the checkout:

```sh
hermes plugins doctor --ci "$PWD"
hermes plugins enable hermes-openui
hermes gateway restart
```

`plugins doctor` runs Hermes's manifest, import, and registration checks, then
flags a stale installed copy of the desktop bundle. `plugins enable` causes the
agent half, including the Skill, to load in new sessions.

Restarting the app alone does not restart a detached gateway. Use:

```sh
hermes gateway restart
```

For a named profile started with `-p`, the active profile must be the one that
serves the Webapp. If your setup manages the gateway under a profile argument,
use:

```sh
hermes -p <profile-name> gateway restart
```

## Enable the browser half

After the gateway is running, reopen the Webapp or Desktop app. Open
**Capabilities → Plugins** and turn on **OpenUI cards**
(`hermes-openui`).

Hermes deliberately starts the browser half of a unified package off. The
plugin's browser toggle is separate from `hermes plugins enable`, which gates
the agent-side code and Skill.

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
hermes plugins doctor --ci "$PWD"
hermes gateway restart
```

Then reopen the app and use **Capabilities → Plugins → Rescan** if the browser
bundle is still the previous build.

## Verify

Useful checks:

```sh
hermes plugins show hermes-openui
hermes plugins list --enabled --no-bundled --plain
```

In a new chat, the prompt above should create one visible interactive card. The
OpenUI source itself must not appear as text in the transcript.

## Troubleshooting

**The Skill does not appear.** Confirm `hermes-openui` is in `plugins.enabled`,
start a new chat, and restart the gateway. The Skill is namespaced as
`hermes-openui:openui`.

**Text works but no card appears.** Enable **OpenUI cards** under
**Capabilities → Plugins**. If that page shows an older build, choose **Rescan**
and reopen the Webapp.

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
