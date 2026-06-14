export type Confidence = "HIGH" | "MEDIUM" | "LOW"
export type Severity = "critical" | "high" | "medium" | "low"
export type InvestigationStatus = "running" | "completed" | "failed"
export type SlackStatus = "auto_confirmed" | "pending_review" | "confirmed" | "false_positive" | null

export interface Finding {
  id: string
  severity: Severity
  title: string
  description: string
  confidence: Confidence
  sources: string[]
  tool_call_ids: string[]
  timestamp: string | null
  contradiction: boolean
  contradiction_description: string | null
  slack_status: SlackStatus
}

export interface ToolCallLog {
  id: string
  tool_name: string
  agent: string
  called_at: string
  duration_ms: number
  params: Record<string, unknown>
  result_summary: string
  image_sha256: string
  hash_verified: boolean
  spoliation_detected: boolean
}

export interface InvestigationReport {
  id: string
  case_id: string
  image_path: string
  image_sha256: string
  status: InvestigationStatus
  started_at: string
  completed_at: string | null
  findings: Finding[]
  contradictions_detected: number
  contradictions_resolved: number
  execution_log: ToolCallLog[]
  evidence_integrity_verified: boolean
  error: string | null
}

export interface InvestigationSummary {
  id: string
  case_id: string
  image_path: string
  status: InvestigationStatus
  started_at: string
  completed_at: string | null
  contradictions_detected: number
}
