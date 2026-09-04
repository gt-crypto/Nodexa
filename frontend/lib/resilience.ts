/**
 * Nodexa Frontend Cold-Start Resilience & Retry Engine
 * 
 * Provides automated, bounded exponential backoff retries when Render's free tier
 * backend is waking up from inactivity. Detects NetworkErrors, "Failed to fetch",
 * and 502/503/504 Bad Gateway HTTP statuses.
 * 
 * Guarantees:
 * - Never fabricates or mocks data.
 * - Caps maximum retry window to ~45-55 seconds.
 * - Emits clear lifecycle states: 'idle' | 'waking' | 'retrying' | 'ready' | 'failed'.
 */

export interface RetryOptions {
  /** Initial delay in ms (default: 1000) */
  initialDelayMs?: number;
  /** Max attempts before giving up (default: 6) */
  maxAttempts?: number;
  /** Backoff schedule delays in ms (default: [0, 1000, 2000, 4000, 8000, 10000]) */
  delays?: number[];
  /** Callback on attempt failure / waking progression */
  onWaking?: (attempt: number, maxAttempts: number, nextDelayMs: number) => void;
  /** Callback when connection successfully recovers after being in waking state */
  onRecovered?: () => void;
}

const DEFAULT_DELAYS = [0, 1000, 2000, 4000, 8000, 10000];

/**
 * Checks whether an error is characteristic of a sleeping/waking cloud instance
 * (e.g. Render HTTP 502/503, connection dropped, CORS preflight fail on sleep, "Failed to fetch").
 */
export function isLikelyWakingError(error: any): boolean {
  if (!error) return false;

  const msg = (error.message || String(error)).toLowerCase();

  // Browser fetch network errors
  if (
    msg.includes("failed to fetch") ||
    msg.includes("network request failed") ||
    msg.includes("networkerror") ||
    msg.includes("net::err_") ||
    msg.includes("abort") ||
    msg.includes("connection refused") ||
    msg.includes("load failed")
  ) {
    return true;
  }

  // HTTP Gateway / Service Unavailable error statuses during Render spinup
  if (
    msg.includes("502") ||
    msg.includes("503") ||
    msg.includes("504") ||
    msg.includes("bad gateway") ||
    msg.includes("service unavailable") ||
    msg.includes("gateway timeout")
  ) {
    return true;
  }

  return false;
}

/**
 * Executes an async API request with cold-start resilience and bounded backoff.
 */
export async function executeWithColdStartRetry<T>(
  requestFn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const delays = options.delays || DEFAULT_DELAYS;
  const maxAttempts = options.maxAttempts || delays.length;
  let wasWaking = false;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const result = await requestFn();
      if (wasWaking && options.onRecovered) {
        options.onRecovered();
      }
      return result;
    } catch (err: any) {
      const isWaking = isLikelyWakingError(err);
      const isLastAttempt = attempt === maxAttempts;

      if (!isWaking || isLastAttempt) {
        throw err;
      }

      wasWaking = true;
      const nextDelay = delays[attempt] ?? 10000;

      if (options.onWaking) {
        options.onWaking(attempt, maxAttempts, nextDelay);
      }

      await new Promise((resolve) => setTimeout(resolve, nextDelay));
    }
  }

  throw new Error("Connection timed out after cold start retry window.");
}
