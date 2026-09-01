import {
  HealthCheckResponse,
  VerificationRecord,
  VerificationDryRunResponse,
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
