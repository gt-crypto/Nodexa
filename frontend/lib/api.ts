import {
  HealthCheckResponse,
  VerificationRecord,
  VerificationDryRunResponse,
  VerifierOpinion,
  ClustersResponse,
  ExceptionCluster,
} from "../types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

/**
 * Fetches the health status from the backend service.
 */
export async function fetchHealthStatus(): Promise<HealthCheckResponse> {
  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    throw error;
  }
}

/**
 * Deterministically verifies an executed remediation plan.
 */
export async function verifyRemediation(
  remediationId: string,
  dryRun: boolean = false,
  actorType: string = "SYSTEM",
  actorId: string = "verifier-v1"
): Promise<VerificationRecord | VerificationDryRunResponse> {
  const url = `${BACKEND_URL}/remediations/${remediationId}/verify?dry_run=${dryRun}&actor_type=${actorType}&actor_id=${actorId}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Verification failed" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Retrieves the latest verification record for a remediation plan.
 */
export async function getLatestVerification(
  remediationId: string
): Promise<VerificationRecord | null> {
  const url = `${BACKEND_URL}/remediations/${remediationId}/verification`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Retries verification for a previously failed verification record.
 */
export async function retryVerification(
  verificationId: string,
  reason?: string
): Promise<VerificationRecord> {
  const url = `${BACKEND_URL}/verifications/${verificationId}/retry`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Retry failed" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Runs a benchmark evaluation on a specified dataset.
 */
export async function runEvaluation(
  datasetId: string,
  forceRerun: boolean = false
): Promise<any> {
  const url = `${BACKEND_URL}/evaluation/run`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, force_rerun: forceRerun }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Evaluation run failed" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Retrieves the latest benchmark report.
 */
export async function getLatestBenchmark(): Promise<any | null> {
  const url = `${BACKEND_URL}/evaluation/benchmark`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Lists historical evaluation runs.
 */
export async function getEvaluationRuns(limit: number = 20): Promise<any[]> {
  const url = `${BACKEND_URL}/evaluation/runs?limit=${limit}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Retrieves case-level match results for an evaluation run.
 */
export async function getEvaluationCases(runId: string): Promise<any[]> {
  const url = `${BACKEND_URL}/evaluation/runs/${runId}/cases`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

// ─── Live Digital-Twin Injection API ──────────────────────────────────────

/**
 * Fetches the list of supported anomaly families for live injection.
 */
export async function fetchSupportedFamilies(): Promise<any[]> {
  const url = `${BACKEND_URL}/demo/supported-families`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}

/**
 * Injects a live synthetic anomaly via the synchronous API.
 */
export async function injectAnomaly(
  exceptionFamily: string,
  triggeredBy: string = "demo-operator",
  idempotencyKey?: string,
  accountId: string = "nodal_escrow_main"
): Promise<any> {
  const url = `${BACKEND_URL}/demo/inject`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exception_family: exceptionFamily,
      triggered_by: triggeredBy,
      idempotency_key: idempotencyKey,
      account_id: accountId,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Injection failed" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Fetches the list of past live-injected cases.
 */
export async function fetchInjectedCases(limit: number = 20): Promise<any[]> {
  const url = `${BACKEND_URL}/demo/injected-cases?limit=${limit}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}

/**
 * Fetches the exceptions list with optional source_flag filter.
 */
export async function fetchExceptions(
  sourceFlag?: string,
  limit: number = 100
): Promise<any[]> {
  let url = `${BACKEND_URL}/exceptions?limit=${limit}`;
  if (sourceFlag) url += `&source_flag=${encodeURIComponent(sourceFlag)}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}

/**
 * Opens an SSE stream for live injection progress.
 * Returns an EventSource instance.
 */
export function createInjectionStream(
  family: string,
  triggeredBy: string = "demo-operator",
  idempotencyKey?: string
): EventSource {
  let url = `${BACKEND_URL}/demo/inject/stream?family=${encodeURIComponent(family)}&triggered_by=${encodeURIComponent(triggeredBy)}`;
  if (idempotencyKey) url += `&idempotency_key=${encodeURIComponent(idempotencyKey)}`;
  return new EventSource(url);
}

/**
 * Fetches the independent adversarial verifier opinion for an exception.
 * Calls PRD endpoint: GET /exceptions/{exception_id}/verifier-opinion
 */
export async function fetchVerifierOpinion(
  exceptionId: string
): Promise<VerifierOpinion> {
  const url = `${BACKEND_URL}/exceptions/${encodeURIComponent(exceptionId)}/verifier-opinion`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch verifier opinion" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Executes a fresh independent adversarial verifier evaluation for an exception.
 * Calls PRD endpoint: POST /exceptions/{exception_id}/verifier-opinion
 */
export async function evaluateVerifierOpinion(
  exceptionId: string
): Promise<VerifierOpinion> {
  const url = `${BACKEND_URL}/exceptions/${encodeURIComponent(exceptionId)}/verifier-opinion`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to evaluate verifier opinion" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Fetches recurring pattern clusters from the Pattern Miner.
 * Calls PRD endpoint: GET /clusters
 */
export async function fetchClusters(params?: {
  pattern_type?: string;
  exception_family?: string;
  merchant_id?: string;
  source?: string;
  min_count?: number;
  limit?: number;
}): Promise<ClustersResponse> {
  const query = new URLSearchParams();
  if (params?.pattern_type) query.set("pattern_type", params.pattern_type);
  if (params?.exception_family) query.set("exception_family", params.exception_family);
  if (params?.merchant_id) query.set("merchant_id", params.merchant_id);
  if (params?.source) query.set("source", params.source);
  if (params?.min_count) query.set("min_count", params.min_count.toString());
  if (params?.limit) query.set("limit", params.limit.toString());

  const url = `${BACKEND_URL}/clusters${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch clusters" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Forces recomputation of pattern clusters.
 * Calls POST /clusters/refresh
 */
export async function refreshClusters(minClusterSize?: number): Promise<ClustersResponse> {
  let url = `${BACKEND_URL}/clusters/refresh`;
  if (minClusterSize) url += `?min_cluster_size=${minClusterSize}`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to refresh clusters" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}


