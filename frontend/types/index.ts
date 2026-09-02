export interface HealthCheckResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface ControlStep {
  id: string;
  name: string;
  description: string;
  layer: "control" | "ai" | "safety" | "audit";
}

export interface ArchitecturalLayer {
  id: string;
  number: number;
  name: string;
  category: "deterministic" | "ai" | "governance";
  description: string;
  guarantees: string[];
}

export type VerificationStatusType =
  | "PENDING"
  | "RUNNING"
  | "PASSED"
  | "VERIFIED"
  | "FAILED"
  | "ESCALATED";

export interface VerificationEvidenceItem {
  check_id: string;
  check_type: string;
  source_table: string;
  source_record_id?: string | null;
  expected_value: any;
  actual_value: any;
  result: "PASS" | "FAIL" | "WARNING" | "NOT_APPLICABLE";
  explanation: string;
}

export interface VerificationRecord {
  verification_id: string;
  remediation_id: string;
  exception_id: string;
  policy_decision_id?: string | null;
  risk_assessment_id?: string | null;
  investigation_id?: string | null;
  verification_status: VerificationStatusType;
  verification_mode: string;
  attempt_number: number;
  original_exposure: number;
  remaining_exposure: number;
  exposure_reduction: number;
  exposure_reduction_bps: number;
  checks_passed: string[];
  checks_failed: string[];
  evidence_summary: VerificationEvidenceItem[];
  failure_reasons: string[];
  final_exception_state: string;
  actor_type: string;
  actor_id: string;
  verifier_version: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface VerificationDryRunResponse {
  dry_run: boolean;
  remediation_id: string;
  exception_id: string;
  projected_status: string;
  projected_remaining_exposure: number;
  projected_exposure_reduction: number;
  projected_exposure_reduction_bps: number;
  eligible_for_closure: boolean;
  checks_passed: string[];
  checks_failed: string[];
  evidence_summary: VerificationEvidenceItem[];
  failure_reasons: string[];
}

export interface ComponentScores {
  detection: number;
  investigation: number;
  financial: number;
  risk: number;
  policy: number;
  remediation: number;
  verification: number;
  safety: number;
  overall: number;
}

export interface EvaluationRunResponse {
  evaluation_run_id: string;
  dataset_id: string;
  benchmark_version: string;
  system_version: string;
  status: string;
  total_ground_truth_cases: number;
  total_predictions: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  precision_bps: number;
  recall: number;
  recall_bps: number;
  f1_score: number;
  f1_score_bps: number;
  overall_score: number;
  scores: ComponentScores;
  safety_status: string;
  critical_safety_failure: boolean;
  safety_failure_reasons: string[];
  started_at: string;
  completed_at?: string | null;
  created_at: string;
}

export interface EvaluationMetricDetail {
  name: string;
  expected_count: number;
  predicted_count: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  precision_bps: number;
  recall: number;
  recall_bps: number;
  f1_score: number;
  f1_score_bps: number;
}

export interface ExposureAccuracySummary {
  exact_matches: number;
  total_evaluated: number;
  exact_match_rate: number;
  exact_match_rate_bps: number;
  total_expected_exposure: number;
  total_predicted_exposure: number;
  total_absolute_error: number;
  max_absolute_error: number;
  mean_absolute_error: number;
  zero_exposure_cases_verified: number;
}

export interface ConfusionMatrixItem {
  expected_class: string;
  predicted_class: string;
  count: number;
}

export interface EvaluationCaseResponse {
  evaluation_case_id: string;
  evaluation_run_id: string;
  ground_truth_case_id?: string | null;
  predicted_exception_id?: string | null;
  match_status: string;
  matched_by: string;
  matched_identifier?: string | null;
  expected_exception_type?: string | null;
  predicted_exception_type?: string | null;
  expected_root_cause?: string | null;
  predicted_root_cause?: string | null;
  expected_exposure: number;
  predicted_exposure: number;
  exposure_error: number;
  expected_severity?: string | null;
  predicted_severity?: string | null;
  expected_priority?: string | null;
  predicted_priority?: string | null;
  expected_resolution_class?: string | null;
  predicted_resolution_class?: string | null;
  expected_policy_decision?: string | null;
  predicted_policy_decision?: string | null;
  remediation_result?: string | null;
  verification_result?: string | null;
  is_false_closure: boolean;
  is_legitimate_case: boolean;
  error_categories: string[];
  details: Record<string, any>;
  created_at?: string | null;
}

export interface EvaluationReportSummary {
  run: EvaluationRunResponse;
  detection_by_type: Record<string, EvaluationMetricDetail>;
  detection_by_severity: Record<string, EvaluationMetricDetail>;
  exposure_accuracy: ExposureAccuracySummary;
  root_cause_accuracy: number;
  root_cause_accuracy_bps: number;
  root_cause_breakdown: Record<string, any>;
  severity_accuracy: number;
  severity_confusion_matrix: ConfusionMatrixItem[];
  priority_accuracy: number;
  priority_confusion_matrix: ConfusionMatrixItem[];
  policy_accuracy: number;
  policy_compliance_rate_bps: number;
  remediation_success_rate: number;
  remediation_success_rate_bps: number;
  verification_success_rate: number;
  verification_success_rate_bps: number;
  false_closure_count: number;
  legitimate_cases_summary: Record<string, any>;
  normal_cases_summary: Record<string, any>;
  false_positives: EvaluationCaseResponse[];
  false_negatives: EvaluationCaseResponse[];
  misclassifications: EvaluationCaseResponse[];
  critical_safety_violations: string[];
}

// ─── Live Digital-Twin Injection Types ──────────────────────────────────────

export interface SupportedFamily {
  family: string;
  description: string;
  category: string;
  severity: string;
  is_legitimate: boolean;
}

export interface InjectionStageEvent {
  stage: string;
  timestamp: string;
  message: string;
  injection_id?: string;
  exception_family?: string;
  exception_id?: string;
  exception_type?: string;
  severity?: string;
  exposure?: number;
  state?: string;
  generated_identifiers?: Record<string, any>;
  counts?: Record<string, number>;
  audit_event_id?: string;
  decision?: string;
  action_type?: string;
  priority?: string;
  risk_score?: number;
  data?: InjectionResponse;
  [key: string]: any;
}

export interface InjectionResponse {
  injection_id: string;
  exception_family: string;
  source_flag: string;
  triggered_at: string;
  generated_record_identifiers: Record<string, string[]>;
  processing_status: string;
  linked_exception_id?: string | null;
  exception_state?: string | null;
  exception_type?: string | null;
  exposure?: number | null;
  message: string;
  stages: InjectionStageEvent[];
}

export interface InjectedCaseSummary {
  injection_id: string;
  exception_family: string;
  triggered_by: string;
  triggered_at: string;
  source_flag: string;
  linked_exception_id?: string | null;
  status: string;
  generated_identifiers?: Record<string, string[]> | null;
  details?: Record<string, any> | null;
}

export interface ExceptionSummary {
  exception_id: string;
  exception_type: string;
  severity: string;
  state: string;
  exposure: number;
  confidence: number;
  source_flag: string;
  description?: string | null;
  primary_payment_id?: string | null;
  primary_order_id?: string | null;
  detected_at: string;
  created_at: string;
  updated_at: string;
}
