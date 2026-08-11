export const MINIMUM_SIGN_IN_MS = 1000
export const GOOGLE_MINIMUM_SIGN_IN_MS = 1500

export function remainingSignInTime(
  startedAt: number,
  now: number,
  minimumDurationMs = MINIMUM_SIGN_IN_MS,
): number {
  return Math.max(0, minimumDurationMs - (now - startedAt))
}

export function waitForMinimumSignInTime(
  startedAt: number,
  minimumDurationMs = MINIMUM_SIGN_IN_MS,
): Promise<void> {
  const remaining = remainingSignInTime(
    startedAt,
    window.performance.now(),
    minimumDurationMs,
  )
  return remaining > 0
    ? new Promise((resolve) => window.setTimeout(resolve, remaining))
    : Promise.resolve()
}
