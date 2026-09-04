import {
  HealthCheckResponse,
  VerificationRecord,
  VerificationDryRunResponse,
  VerifierOpinion,
  ClustersResponse,
  ExceptionCluster,
} from "../types";

/**
 * Resolves the backend base URL dynamically.
 * Evaluates NEXT_PUBLIC_BACKEND_URL, NEXT_PUBLIC_API_URL, and deployment hostnames.
 */
export function getBackendUrl(): string {
  let url = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    if (typeof window !== "undefined") {
      const hostname = window.location.hostname;
      if (hostname !== "localhost" && hostname !== "127.0.0.1") {
        url = "https://nodexa-api.onrender.com";
      } else {
        url = "http://127.0.0.1:8000";
      }
    } else {
      url = "https://nodexa-api.onrender.com";
    }
  }
  if (url && !url.startsWith("http://") && !url.startsWith("https://")) {
    url = `https://${url}`;
  }
  return url.replace(/\/+$/, "");
}

export const BACKEND_URL = getBackendUrl();

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

/**
 * Deterministic Risk Analytics: Merchant Trust Score Interface
 */
export interface MerchantScore {
  merchant_id: string;
  trust_score: number;
  impact_score: number;
  score_band: string;
  metrics: {
    exception_count: number;
    actionable_exception_count: number;
    legitimate_exception_count: number;
    high_risk_exception_count: number;
    total_exposure: number;
    recurring_pattern_count: number;
    seeded_case_count: number;
    live_injected_case_count: number;
    total_transaction_count: number;
    total_transaction_volume: number;
  };
  factors: Array<{
    factor: string;
    direction: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
    value: number;
    contribution: number;
    explanation: string;
  }>;
  scoring_version: string;
  first_seen: string | null;
  last_seen: string | null;
}

/**
 * Fetches all calculated merchant trust and impact scores.
 * Calls PRD endpoint: GET /merchants/scores
 */
export async function fetchMerchantScores(): Promise<MerchantScore[]> {
  const url = `${BACKEND_URL}/merchants/scores`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch merchant scores" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Business Impact & ROI Data Model (Tier-2 Prompt 17)
 */
export interface BusinessImpactData {
  financial_exposure_identified: number;
  financial_exposure_currency: string;
  actionable_case_count: number;
  total_cases_detected: number;
  high_risk_case_count: number;
  recurring_pattern_count: number;
  pattern_exposure_identified: number;
  merchants_impacted: number;
  seeded_case_count: number;
  seeded_exposure_identified: number;
  live_injected_case_count: number;
  live_injected_exposure_identified: number;
  automated_detection_rate: string;
  value_type: string;
  realized_savings: number | null;
  disclaimer: string;
  methodology: Record<string, string>;
  version: string;
  generated_at: string;
}

/**
 * Fetches deterministic Business Impact and ROI metrics.
 * Calls PRD endpoint: GET /impact/roi
 */
export async function fetchBusinessImpact(): Promise<BusinessImpactData> {
  const url = `${BACKEND_URL}/impact/roi`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
  } catch (netErr: any) {
    throw new Error(
      `Failed to connect to ${url} (${netErr?.message || "Network request failed. Check server connectivity or CORS"})`
    );
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = `${errorDetail}: ${typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail)}`;
      } else if (errJson.message) {
        errorDetail = `${errorDetail}: ${errJson.message}`;
      }
    } catch {
      // Body was not JSON
    }
    throw new Error(`Failed to load business impact from ${url} [${errorDetail}]`);
  }
  return await response.json();
}

/**
 * Predictive Nodal Drift Radar Data Model (Tier-3 Prompt 18)
 */
export interface DriftSignal {
  signal: string;
  name: string;
  baseline: any;
  current: any;
  delta: any;
  direction: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  contribution: number;
  explanation: string;
  evidence_ids: string[];
  growth_rate?: number;
}

export interface DriftPredictionData {
  prediction_id: string;
  nodal_account_id: string;
  prediction_timestamp: string;
  observation_window: {
    baseline_start: string | null;
    baseline_end: string | null;
    current_start: string | null;
    current_end: string | null;
  };
  horizon: string;
  drift_score: number;
  risk_band: "STABLE" | "WATCH" | "ELEVATED" | "HIGH_DRIFT";
  direction: "IMPROVING" | "STABLE" | "DETERIORATING" | "INSUFFICIENT_DATA";
  confidence: "LOW" | "MEDIUM" | "HIGH";
  predicted_dimension: string;
  signals: DriftSignal[];
  baseline_metrics: Record<string, any>;
  current_metrics: Record<string, any>;
  delta_metrics: Record<string, any>;
  evidence_ids: string[];
  source: {
    seeded_count: number;
    live_injected_count: number;
    total_observations: number;
    synthetic_included: boolean;
  };
  methodology_version: string;
  disclaimer: string;
}

/**
 * Fetches deterministic Predictive Nodal Drift Radar analytics.
 * Calls PRD endpoint: GET /predictions/drift
 */
export async function fetchDriftPrediction(
  nodalAccountId: string = "nodal_escrow_main"
): Promise<DriftPredictionData> {
  const url = `${BACKEND_URL}/predictions/drift?nodal_account_id=${encodeURIComponent(nodalAccountId)}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch drift prediction" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Confidence Calibration Data Model (Tier-3 Prompt 19)
 */
export interface ConfidenceBucketData {
  confidence_level: "HIGH" | "MEDIUM" | "LOW";
  prediction_count: number;
  evaluated_count: number;
  unevaluated_count: number;
  correct_count: number;
  correctness_rate: number | null;
  coverage: number | null;
}

export interface ReliabilityBinData {
  range: string;
  count: number;
  accuracy: number | null;
  confidence: number | null;
  calibration_error: number | null;
}

export interface NumericalMetricsData {
  status: "CALCULATED" | "UNAVAILABLE";
  eligible_sample_size: number;
  brier_score: number | null;
  ece: number | null;
  reliability_bins: ReliabilityBinData[];
  reason: string | null;
}

export interface ConfidenceCalibrationData {
  snapshot_id: string;
  status: "CALIBRATED" | "PARTIALLY_CALIBRATED" | "INSUFFICIENT_DATA" | "NOT_CALIBRATABLE";
  methodology_version: string;
  prediction_type_filter: string | null;
  source_filter: string | null;
  total_predictions: number;
  evaluated_predictions: number;
  unevaluated_predictions: number;
  correct_predictions: number;
  coverage: number | null;
  correctness_rate: number | null;
  confidence_buckets: Record<string, ConfidenceBucketData>;
  numerical_metrics: NumericalMetricsData;
  source_breakdown: {
    seeded_count: number;
    live_injected_count: number;
    total: number;
  };
  insufficiency_reasons: string[] | null;
  disclaimer: string;
  generated_at: string;
}

/**
 * Fetches deterministic empirical Confidence Calibration metrics.
 * Calls PRD endpoint: GET /calibration/confidence
 */
export async function fetchConfidenceCalibration(
  predictionType?: string,
  source?: string
): Promise<ConfidenceCalibrationData> {
  const params = new URLSearchParams();
  if (predictionType) params.append("prediction_type", predictionType);
  if (source) params.append("source", source);
  const qs = params.toString() ? `?${params.toString()}` : "";

  const url = `${BACKEND_URL}/calibration/confidence${qs}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch confidence calibration" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Escalation Webhook Data Models (Tier-3 Prompt 20)
 */
export interface EscalationDeliveryItem {
  delivery_id: string;
  event_id: string;
  exception_id: string;
  event_type: string;
  delivery_status: "PENDING" | "DELIVERED" | "FAILED" | "DISABLED";
  destination_url: string | null;
  attempt_count: number;
  response_status_code: number | null;
  error_message: string | null;
  first_attempt_at: string | null;
  last_attempt_at: string | null;
  delivered_at: string | null;
  source_flag: string;
  created_at: string;
}

export interface EscalationConfigData {
  enabled: boolean;
  configured: boolean;
  destination_url: string;
  has_signing_secret: boolean;
  timeout_seconds: number;
  max_retries: number;
  authentication_method: string;
}

export interface EscalationTriggerResult {
  success: boolean;
  status: string;
  delivery_id?: string;
  event_id?: string;
  attempt_count?: number;
  response_status_code?: number;
  delivered_at?: string;
  error_message?: string;
  message: string;
}

/**
 * Fetches safe masked Escalation Webhook configuration.
 * Calls PRD endpoint: GET /escalations/config
 */
export async function fetchEscalationConfig(): Promise<EscalationConfigData> {
  const url = `${BACKEND_URL}/escalations/config`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch escalation config" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Fetches recent escalation webhook delivery records.
 * Calls PRD endpoint: GET /escalations/deliveries
 */
export async function fetchEscalationDeliveries(limit: number = 50): Promise<EscalationDeliveryItem[]> {
  const url = `${BACKEND_URL}/escalations/deliveries?limit=${limit}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to fetch escalation deliveries" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Dispatches an outbound escalation webhook for an exception.
 * Calls PRD endpoint: POST /escalations/{exception_id}/webhook
 */
export async function triggerEscalationWebhook(
  exceptionId: string,
  force: boolean = false
): Promise<EscalationTriggerResult> {
  const url = `${BACKEND_URL}/escalations/${encodeURIComponent(exceptionId)}/webhook?force=${force}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Failed to trigger escalation webhook" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Queries Ask Sentinel grounded copilot.
 * Calls PRD endpoint: POST /copilot/ask
 */
export async function askCopilot(payload: {
  question: string;
  exception_id?: string;
  actor_id?: string;
}): Promise<any> {
  const url = `${BACKEND_URL}/copilot/ask`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Copilot query failed" }));
    throw new Error(err.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}


