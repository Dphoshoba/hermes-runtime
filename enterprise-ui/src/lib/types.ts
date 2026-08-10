export interface DashboardStats {
  total_repositories: number;
  active_repositories: number;
  total_findings: number;
  open_findings: number;
  critical_findings: number;
  high_findings: number;
  total_missions: number;
  pending_missions: number;
  running_missions: number;
  completed_missions: number;
  failed_missions: number;
  total_reports: number;
  avg_health_score: number | null;
  journal_events_today: number;
}

export interface JournalEvent {
  id: string;
  event_id: string;
  timestamp: string;
  event_type: string;
  stage: string;
  repository_id: string | null;
  actor: string;
  payload: Record<string, unknown>;
  payload_sha256: string;
  created_at: string;
}

export interface Repository {
  id: string;
  name: string;
  url: string;
  default_branch: string;
  language: string | null;
  status: string;
  provider: string;
  identifier: string | null;
  commit_sha: string | null;
  visibility: string | null;
  last_scanned_at: string | null;
  last_synced_at: string | null;
  health_score: number | null;
  findings_count: number;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  repository_id: string | null;
  finding_type: string;
  severity: string;
  category: string;
  title: string;
  description: string | null;
  module: string | null;
  priority_score: number | null;
  effort: string | null;
  status: string;
  created_at: string;
}

export interface Mission {
  id: string;
  mission_id: string;
  repository_id: string | null;
  title: string;
  description: string | null;
  mission_type: string;
  status: string;
  priority: number;
  created_at: string;
}

export interface Report {
  id: string;
  mission_id: string | null;
  repository_id: string | null;
  title: string;
  status: string;
  summary: string | null;
  report_data: Record<string, unknown>;
  duration_seconds: number | null;
  tasks_planned: number | null;
  tasks_completed: number | null;
  tasks_failed: number | null;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_admin: boolean;
}

export interface ScanJob {
  id: string;
  repository_id: string;
  status: string;
  scan_type: string;
  branch: string | null;
  commit_sha: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  stages_completed: string[];
  current_stage: string | null;
  findings_count: number;
  attempt: number;
  previous_scan_id: string | null;
  requested_by: string | null;
  cancellation_requested_at: string | null;
  cancelled_at: string | null;
  failure_classification: string | null;
  stage_timings: Record<string, { started_at: string; completed_at: string; duration_seconds: number }>;
  created_at: string;
}

export interface ScanHistoryEntry {
  id: string;
  scan_job_id: string;
  stage: string;
  status: string;
  message: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface DashboardActivityV2 {
  repositories_total: number;
  repositories_ready: number;
  repositories_blocked: number;
  scans_queued: number;
  scans_running: number;
  scans_completed_since: number;
  scans_failed_since: number;
  new_findings_since: number;
  governance_approved_since: number;
  governance_rejected_since: number;
  draft_missions_since: number;
  ci_failures_since: number;
  latest_activity: JournalEvent[];
  average_repository_health: number | null;
}

export interface OvernightSummary {
  window_start: string;
  window_end: string;
  repositories_scanned: number;
  blocked_repositories: number;
  successful_scans: number;
  failed_scans: number;
  new_findings: number;
  resolved_findings: number;
  governance_decisions: number;
  draft_missions: number;
  ci_failures: number;
  top_repositories_requiring_attention: { id: string; name: string; reason: string }[];
  summary: string;
}
