import { useEffect, useState } from "react"
import { fetchInvestigation } from "../api"
import type { InvestigationReport, Finding } from "../types"
import { FindingCard } from "./FindingCard"
import { TimelinePanel } from "./TimelinePanel"
import { AgentLog } from "./AgentLog"
import { EvidenceBadge } from "./EvidenceBadge"

export function ReportView({ investigationId }: { investigationId: string }) {
  const [report, setReport] = useState<InvestigationReport | null>(null)
  const [selected, setSelected] = useState<Finding | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    fetchInvestigation(investigationId)
      .then(r => { setReport(r); if (r.findings.length) setSelected(r.findings[0]) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [investigationId])

  if (loading) return <div style={{ padding: 32, color: "#6B7280" }}>Loading investigation…</div>
  if (error || !report) return <div style={{ padding: 32, color: "#DC2626" }}>Error: {error || "Not found"}</div>

  const critical = report.findings.filter(f => f.severity === "critical").length
  const high = report.findings.filter(f => f.severity === "high").length

  return (
    <div style={{ height: "calc(100vh - 42px)", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ padding: "10px 20px", background: "#fff", borderBottom: "1px solid #E2E5EC", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "#111827", marginBottom: 2 }}>{report.case_id}</h2>
            <p style={{ fontSize: 11, color: "#6B7280", fontFamily: "'JetBrains Mono', monospace" }}>{report.image_path}</p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <EvidenceBadge verified={report.evidence_integrity_verified} />
            {critical > 0 && <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4,
              background: "#FEF2F2", border: "1px solid #FECACA", color: "#991B1B", fontWeight: 600 }}>{critical} critical</span>}
            {high > 0 && <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4,
              background: "#FFF7ED", border: "1px solid #FED7AA", color: "#9A3412", fontWeight: 600 }}>{high} high</span>}
            {report.contradictions_detected > 0 && <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4,
              background: "#FEF3C7", border: "1px solid #FDE68A", color: "#92400E", fontWeight: 600 }}>
              {report.contradictions_detected} contradictions</span>}
          </div>
        </div>
      </div>

      {/* Three panels */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Findings */}
        <div style={{ width: 300, flexShrink: 0, borderRight: "1px solid #E2E5EC", background: "#fff",
          display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #E2E5EC", fontSize: 11,
            fontWeight: 600, color: "#374151" }}>Findings ({report.findings.length})</div>
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
            {report.findings.length === 0 ? (
              <p style={{ fontSize: 12, color: "#9CA3AF", textAlign: "center", padding: 24 }}>No findings</p>
            ) : report.findings.map(f => (
              <FindingCard key={f.id} finding={f} selected={selected?.id === f.id} onClick={() => setSelected(f)} />
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "#F8F9FB" }}>
          {selected && (
            <div style={{ padding: "10px 14px", borderBottom: "1px solid #E2E5EC", background: "#fff", flexShrink: 0 }}>
              <p style={{ fontSize: 13, fontWeight: 600, color: "#111827", marginBottom: 3 }}>{selected.title}</p>
              <p style={{ fontSize: 12, color: "#374151", lineHeight: 1.6, marginBottom: 4 }}>{selected.description}</p>
              {selected.tool_call_ids.length > 0 && (
                <p style={{ fontSize: 10, color: "#9CA3AF", fontFamily: "'JetBrains Mono', monospace" }}>
                  Tool calls: {selected.tool_call_ids.join(", ")}
                </p>
              )}
            </div>
          )}
          <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px" }}>
            <p style={{ fontSize: 10, fontWeight: 600, color: "#6B7280", letterSpacing: "0.08em",
              textTransform: "uppercase", marginBottom: 10 }}>Attack Timeline</p>
            <TimelinePanel findings={report.findings} />
          </div>
        </div>

        {/* Agent Log */}
        <div style={{ width: 260, flexShrink: 0, borderLeft: "1px solid #E2E5EC", background: "#fff",
          display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #E2E5EC", fontSize: 11,
            fontWeight: 600, color: "#374151" }}>Agent Execution Log</div>
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
            <AgentLog logs={report.execution_log} />
          </div>
        </div>
      </div>
    </div>
  )
}
