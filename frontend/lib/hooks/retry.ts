import { ApiError } from '@/lib/api/client'

/**
 * Shared TanStack Query retry policy: never retry a 404 (the resource
 * genuinely doesn't exist yet — retrying just delays the empty/not-found
 * state), retry other failures (network blips, 5xx) up to twice.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.isNotFound) return false
  return failureCount < 2
}
