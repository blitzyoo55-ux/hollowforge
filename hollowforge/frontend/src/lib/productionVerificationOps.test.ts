import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

import { expect, test } from 'vitest'

import { PRODUCTION_VERIFICATION_SOP_PATH } from './productionVerificationOps'

test('operator SOP path exists in the repository', () => {
  const sopPath = resolve(process.cwd(), '..', PRODUCTION_VERIFICATION_SOP_PATH)

  expect(existsSync(sopPath)).toBe(true)
})
