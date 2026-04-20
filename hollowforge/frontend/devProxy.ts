export const DEFAULT_BACKEND_PROXY_TARGET = 'http://localhost:8000'
export const HOLLOWFORGE_DEV_PROXY_TARGET_ENV = 'HOLLOWFORGE_DEV_PROXY_TARGET'

export function resolveBackendProxyTarget(
  env: NodeJS.ProcessEnv = process.env,
): string {
  const override = env[HOLLOWFORGE_DEV_PROXY_TARGET_ENV]?.trim()
  return override || DEFAULT_BACKEND_PROXY_TARGET
}
