import assert from 'node:assert/strict'
import {
  access,
  cp,
  lstat,
  mkdir,
  rm,
  symlink,
  writeFile
} from 'node:fs/promises'
import path from 'node:path'

import {
  DEFAULT_MODEL_PORT,
  DEFAULT_QUERY_PORT,
  DEFAULT_WEBAPP_PORT,
  REPO_ROOT,
  resolveHermesRuntime,
  runHermes,
  testPort
} from './hermes-runtime.mjs'

const runtime = resolveHermesRuntime()
const installSource = path.resolve(
  process.env.OPENUI_TEST_INSTALL_SOURCE?.trim() || REPO_ROOT
)
const installMode = process.env.OPENUI_TEST_INSTALL_MODE?.trim() || 'link'
const webappPort = testPort('OPENUI_TEST_WEBAPP_PORT', DEFAULT_WEBAPP_PORT)
const modelPort = testPort('OPENUI_FIXTURE_PORT', DEFAULT_MODEL_PORT)
const queryPort = testPort('OPENUI_QUERY_FIXTURE_PORT', DEFAULT_QUERY_PORT)

assert.ok(
  installMode === 'link' || installMode === 'copy',
  'OPENUI_TEST_INSTALL_MODE must be link or copy'
)
assert.equal(
  new Set([webappPort, modelPort, queryPort]).size,
  3,
  'The Webapp, model fixture, and Query fixture ports must differ'
)

const pluginLink = path.join(runtime.home, 'plugins', 'hermes-openui')
const desktopLink = path.join(runtime.home, 'desktop-plugins', 'hermes-openui')
await mkdir(path.dirname(pluginLink), { recursive: true })
await mkdir(path.dirname(desktopLink), { recursive: true })

function isManagedProfilePath(target) {
  const relative = path.relative(path.join(REPO_ROOT, 'local'), target)
  return relative !== '' && !relative.startsWith('..') && !path.isAbsolute(relative)
}

async function removeManagedPath(target) {
  try {
    const entry = await lstat(target)
    if (!entry.isSymbolicLink()) {
      assert.ok(
        isManagedProfilePath(target),
        `${target} exists outside local/; inspect and remove it manually`
      )
    }
    await rm(target, { force: true, recursive: true })
  } catch (error) {
    if (error?.code !== 'ENOENT') {
      throw error
    }
  }
}

for (const filename of ['plugin.yaml', '__init__.py', 'skills/openui/SKILL.md']) {
  await access(path.join(installSource, filename))
}
await removeManagedPath(pluginLink)
await removeManagedPath(desktopLink)

runHermes(runtime, ['plugins', 'doctor', '--help'])
runHermes(runtime, ['webapp', '--help'])
const doctor = runHermes(runtime, ['plugins', 'doctor', '--ci', installSource])
assert.match(
  doctor,
  /OK: runtime discovery, manifest parsing, import, and registration passed/
)

if (installMode === 'link') {
  await symlink(installSource, pluginLink, 'dir')
} else {
  await mkdir(pluginLink, { recursive: true })
  for (const entry of ['__init__.py', 'plugin.yaml', 'skills', 'dashboard']) {
    await cp(path.join(installSource, entry), path.join(pluginLink, entry), {
      force: true,
      recursive: true
    })
  }

  await mkdir(desktopLink, { recursive: true })
  for (const entry of ['plugin.js', 'maplibre-gl-worker.mjs']) {
    await access(path.join(installSource, 'desktop', entry))
    await cp(
      path.join(installSource, 'desktop', entry),
      path.join(desktopLink, entry),
      { force: true }
    )
  }
}

const config = `model:
  default: stream-fixture
  provider: custom
  api_mode: chat_completions
  base_url: http://127.0.0.1:${modelPort}/v1
  context_length: 65536
plugins:
  enabled:
    - hermes-openui
  disabled: []
  entries:
    hermes-openui:
      settings:
        query_url: http://127.0.0.1:${queryPort}/rows
webapp:
  enabled: true
  host: 127.0.0.1
  port: ${webappPort}
updates:
  check: false
`
await writeFile(path.join(runtime.home, 'config.yaml'), config)

runHermes(runtime, ['plugins', 'enable', 'hermes-openui'])

console.log(JSON.stringify({
  hermes: runtime.executable,
  repository: runtime.repository,
  home: runtime.home,
  install: {
    mode: installMode,
    source: installSource
  },
  ports: {
    model: modelPort,
    query: queryPort,
    webapp: webappPort
  },
  status: 'ready'
}, null, 2))
