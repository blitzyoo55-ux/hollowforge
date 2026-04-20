import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterEach, describe, expect, it } from 'vitest'

const scriptsDir = dirname(fileURLToPath(import.meta.url))
const scriptPath = resolve(scriptsDir, 'run-worktree-handoff-stack.sh')
const repoRoot = resolve(scriptsDir, '..', '..')

const tempDirs: string[] = []

function createFakeNpmDir(): string {
  const dir = mkdtempSync(resolve(tmpdir(), 'hf-worktree-stack-'))
  const npmPath = resolve(dir, 'npm')
  writeFileSync(npmPath, '#!/bin/sh\nexit 0\n')
  chmodSync(npmPath, 0o755)
  tempDirs.push(dir)
  return dir
}

function runScript(args: string[]): string {
  const fakeNpmDir = createFakeNpmDir()
  return execFileSync(scriptPath, args, {
    cwd: repoRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${fakeNpmDir}:${process.env.PATH ?? ''}`,
      HOLLOWFORGE_BACKEND_PYTHON: '/usr/bin/true',
      HOLLOWFORGE_ALT_BACKEND_PORT: '49140',
      HOLLOWFORGE_ALT_FRONTEND_PORT: '49141',
    },
  })
}

afterEach(() => {
  while (tempDirs.length > 0) {
    const dir = tempDirs.pop()
    if (!dir) continue
    rmSync(dir, { recursive: true, force: true })
  }
})

describe('run-worktree-handoff-stack.sh', () => {
  it('prints usage and exits when --help is provided', () => {
    const output = runScript(['--help'])
    expect(output).toContain('Usage:')
  })

  it('prints the browser target in dry-run mode when --open-browser is enabled', () => {
    const output = runScript(['--dry-run', '--open-browser'])
    expect(output).toContain('Browser:  http://127.0.0.1:49141/production')
  })
})
