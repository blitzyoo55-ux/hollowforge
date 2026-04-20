import { describe, expect, it } from 'vitest'

import {
  DEFAULT_BACKEND_PROXY_TARGET,
  HOLLOWFORGE_DEV_PROXY_TARGET_ENV,
  resolveBackendProxyTarget,
} from './devProxy'

describe('resolveBackendProxyTarget', () => {
  it('uses the default backend target when the env override is missing', () => {
    expect(resolveBackendProxyTarget({})).toBe(DEFAULT_BACKEND_PROXY_TARGET)
  })

  it('uses the configured env override when present', () => {
    expect(resolveBackendProxyTarget({
      [HOLLOWFORGE_DEV_PROXY_TARGET_ENV]: 'http://127.0.0.1:8014',
    })).toBe('http://127.0.0.1:8014')
  })
})
