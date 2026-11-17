import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { homedir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..'
)

export const DEFAULT_WEBAPP_PORT = 19_120
export const DEFAULT_MODEL_PORT = 19_121
export const DEFAULT_QUERY_PORT = 19_124

const FORBIDDEN_PORTS = new Set([1934, 3082])

function explicitPath(value) {
  const trimmed = value?.trim()
  return trimmed ? path.resolve(trimmed) : null
}

export function resolveHermesRuntime(environment = process.env) {
  const repository = explicitPath(environment.HERMES_REPO)
  const executable = explicitPath(
    environment.OPENUI_TEST_HERMES ?? environment.HERMES
  ) ?? (repository ? path.join(repository, 'hermes') : null)

  assert.ok(
    executable,
    'Set HERMES to the Hermes executable, or set HERMES_REPO to a v0.23.1 checkout'
  )

  const home = explicitPath(environment.HERMES_HOME) ??
    path.join(REPO_ROOT, 'local', 'hermes-webapp')
  assert.notEqual(
    home,
    path.join(homedir(), '.hermes'),
    'Refusing to run Webapp tests against the real ~/.hermes profile'
  )

  const inheritedPythonPath = environment.PYTHONPATH?.trim()
  const pythonPath = repository
    ? [repository, inheritedPythonPath].filter(Boolean).join(path.delimiter)
    : inheritedPythonPath

  const runtimeEnvironment = {
    ...environment,
    HERMES_HOME: home,
    NO_COLOR: '1',
    TMPDIR: environment.OPENUI_TEST_TMPDIR?.trim() || '/tmp'
  }
  if (pythonPath) {
    runtimeEnvironment.PYTHONPATH = pythonPath
  }

  return {
    environment: runtimeEnvironment,
    executable,
    home,
    repository
  }
}

export function testPort(name, fallback) {
  const raw = process.env[name]
  const port = raw === undefined || raw.trim() === ''
    ? fallback
    : Number(raw)

  assert.ok(
    Number.isInteger(port) && port >= 1 && port <= 65_535,
    `${name} must be an integer from 1 to 65535`
  )
  assert.ok(
    !FORBIDDEN_PORTS.has(port),
    `${name} must not use preview port ${port}`
  )
  return port
}

export function runHermes(runtime, args, options = {}) {
  return execFileSync(runtime.executable, args, {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    env: runtime.environment,
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 30_000,
    ...options
  })
}
