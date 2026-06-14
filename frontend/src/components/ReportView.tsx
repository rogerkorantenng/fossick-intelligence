import { useEffect, useState } from "react"
import { fetchInvestigation } from "../api"
import type { InvestigationReport, Finding } from "../types"

// ── Severity helpers ──────────────────────────────────────────────────────────
const SEV_CONFIG: Record<string, { color: string; bg: string; border: string; dot: string }> = {
  critical: { color: "var(--red)",    bg: "var(--red-bg)",    border: "var(--red-b)",    dot: "#E02020" },
  high:     { color: "var(--orange)", bg: "var(--orange-bg)", border: "var(--orange-b)", dot: "#D97706" },
  medium:   { color: "var(--amber)",  bg: "var(--amber-bg)",  border: "var(--amber-b)",  dot: "#B45309" },
  low:      { color: "var(--slate)",  bg: "var(--slate-bg)",  border: "var(--slate-b)",  dot: "#475569" },
}

const CONF_CONFIG: Record<string, { color: string; bars: [boolean, boolean, boolean] }> = {
  HIGH:   { color: "var(--red)",    bars: [true, true, true]   },
  MEDIUM: { color: "var(--orange)", bars: [true, true, false]  },
  LOW:    { color: "var(--amber)",  bars: [true, false, false]  },
}

const SLACK_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  confirmed:      { label: "Confirmed",    color: "var(--green)",  bg: "var(--green-bg)",  icon: "✓" },
  false_positive: { label: "False +ve",   color: "var(--red)",    bg: "var(--red-bg)",    icon: "✗" },
  pending_review: { label: "Pending",      color: "var(--blue)",   bg: "var(--blue-bg)",   icon: "⏳" },
  auto_confirmed: { label: "Auto",         color: "var(--slate)",  bg: "var(--slate-bg)",  icon: "·" },
}

function SeverityBar({ sev }: { sev: string }) {
  const c = SEV_CONFIG[sev] || SEV_CONFIG.low
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
      background: c.bg, border: `1px solid ${c.border}`, color: c.color,
      letterSpacing: "0.04em", textTransform: "uppercase",
    }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: c.dot, flexShrink: 0 }} />
      {sev}
    </span>
  )
}

function ConfidenceBars({ conf }: { conf: string }) {
  const c = CONF_CONFIG[conf] || CONF_CONFIG.LOW
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      {c.bars.map((filled, i) => (
        <div key={i} style={{
          width: 10, height: 10, borderRadius: 2,
          background: filled ? c.color : "var(--bg-raised)",
          border: `1px solid ${filled ? c.color : "var(--border)"}`,
        }} />
      ))}
      <span style={{ fontSize: 11, color: c.color, fontWeight: 500, marginLeft: 2 }}>{conf}</span>
    </div>
  )
}

function SlackBadge({ status }: { status: string | null }) {
  if (!status || status === "pending_review") return null
  const c = SLACK_CONFIG[status]
  if (!c) return null
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 7px", borderRadius: 20, fontSize: 10, fontWeight: 500,
      background: c.bg, color: c.color,
    }}>
      <span>{c.icon}</span> Slack: {c.label}
    </span>
  )
}

// ── Finding card ──────────────────────────────────────────────────────────────
function FindingItem({ finding, selected, onClick }: {
  finding: Finding; selected: boolean; onClick: () => void
}) {
  const c = SEV_CONFIG[finding.severity] || SEV_CONFIG.low
  const isContra = finding.contradiction

  return (
    <div
      onClick={onClick}
      style={{
        padding: "11px 14px",
        borderBottom: "1px solid var(--border)",
        cursor: "pointer",
        background: selected ? "var(--blue-bg)" : "transparent",
        borderLeft: `3px solid ${selected ? "var(--blue)" : isContra ? "var(--violet)" : c.dot}`,
        transition: "all .1s",
      }}
      onMouseEnter={e => { if (!selected) (e.currentTarget as HTMLElement).style.background = "var(--bg-subtle)" }}
      onMouseLeave={e => { if (!selected) (e.currentTarget as HTMLElement).style.background = "transparent" }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <SeverityBar sev={isContra ? "medium" : finding.severity} />
        <div style={{ display: "flex", gap: 5 }}>
          {isContra && (
            <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 20,
              background: "var(--violet-bg)", color: "var(--violet)", fontWeight: 500 }}>
              ⚡ Contradiction
            </span>
          )}
          <SlackBadge status={finding.slack_status} />
        </div>
      </div>
      <p style={{
        fontSize: 12, fontWeight: 500,
        color: selected ? "var(--blue)" : "var(--text-0)",
        lineHeight: 1.35, marginBottom: 3,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>
        {finding.title}
      </p>
      <p style={{ fontSize: 11, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {finding.description.slice(0, 90)}
      </p>
    </div>
  )
}

// ── Finding detail panel ──────────────────────────────────────────────────────
function FindingDetail({ finding }: { finding: Finding }) {
  const c = SEV_CONFIG[finding.severity] || SEV_CONFIG.low

  return (
    <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Title */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <SeverityBar sev={finding.severity} />
          {finding.contradiction && (
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 20,
              background: "var(--violet-bg)", border: "1px solid var(--violet-b)",
              color: "var(--violet)", fontWeight: 500 }}>
              ⚡ Contradiction
            </span>
          )}
          <SlackBadge status={finding.slack_status} />
        </div>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-0)", lineHeight: 1.35 }}>
          {finding.title}
        </h2>
      </div>

      {/* Description */}
      <div style={{
        padding: "14px 16px",
        background: "var(--bg-subtle)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${c.dot}`,
        borderRadius: "0 8px 8px 0",
      }}>
        <p style={{ fontSize: 13, color: "var(--text-1)", lineHeight: 1.65 }}>{finding.description}</p>
      </div>

      {/* Contradiction reasoning */}
      {finding.contradiction && finding.contradiction_description && (
        <div style={{
          padding: "14px 16px",
          background: "var(--violet-bg)",
          border: "1px solid var(--violet-b)",
          borderRadius: 8,
        }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--violet)", textTransform: "uppercase",
            letterSpacing: "0.05em", marginBottom: 7 }}>Verifier Reasoning</p>
          <p style={{ fontSize: 13, color: "var(--text-1)", lineHeight: 1.65 }}>
            {finding.contradiction_description}
          </p>
        </div>
      )}

      {/* Metadata grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: 10,
      }}>
        <MetaCard label="Confidence" value={<ConfidenceBars conf={finding.confidence} />} />
        <MetaCard label="Sources" value={
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {finding.sources.map(s => (
              <span key={s} style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20,
                background: "var(--blue-bg)", border: "1px solid var(--blue-b)", color: "var(--blue)" }}>
                {s}
              </span>
            ))}
          </div>
        } />
        {finding.timestamp && (
          <MetaCard label="Timestamp" value={
            <span className="mono" style={{ fontSize: 11, color: "var(--text-2)" }}>
              {new Date(finding.timestamp).toLocaleString()}
            </span>
          } />
        )}
        {finding.tool_call_ids.length > 0 && (
          <MetaCard label="Tool Calls" value={
            <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>
              {finding.tool_call_ids.join(", ")}
            </span>
          } />
        )}
      </div>

      {/* Slack status */}
      {finding.slack_status && finding.slack_status !== "pending_review" && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 14px", borderRadius: 8,
          background: finding.slack_status === "confirmed" ? "var(--green-bg)" : "var(--red-bg)",
          border: `1px solid ${finding.slack_status === "confirmed" ? "var(--green-b)" : "var(--red-b)"}`,
        }}>
          <span style={{ fontSize: 16 }}>{finding.slack_status === "confirmed" ? "✅" : "❌"}</span>
          <div>
            <p style={{ fontSize: 12, fontWeight: 600,
              color: finding.slack_status === "confirmed" ? "var(--green)" : "var(--red)" }}>
              {finding.slack_status === "confirmed" ? "Confirmed by analyst via Slack" : "Marked false positive via Slack"}
            </p>
            <p style={{ fontSize: 11, color: "var(--text-3)" }}>Analyst decision recorded</p>
          </div>
        </div>
      )}
      {finding.slack_status === "pending_review" && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 14px", borderRadius: 8,
          background: "var(--blue-bg)", border: "1px solid var(--blue-b)",
        }}>
          <span style={{ fontSize: 16, animation: "pulse 1.5s ease-in-out infinite" }}>⏳</span>
          <div>
            <p style={{ fontSize: 12, fontWeight: 600, color: "var(--blue)" }}>Awaiting analyst review</p>
            <p style={{ fontSize: 11, color: "var(--text-3)" }}>Approval card sent to Slack</p>
          </div>
        </div>
      )}
    </div>
  )
}

function MetaCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      padding: "10px 12px",
      background: "var(--bg-subtle)",
      border: "1px solid var(--border)",
      borderRadius: 8,
    }}>
      <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase",
        letterSpacing: "0.05em", marginBottom: 5 }}>{label}</p>
      <div>{value}</div>
    </div>
  )
}

// ── Agent log ─────────────────────────────────────────────────────────────────
function AgentLogPanel({ logs }: { logs: InvestigationReport["execution_log"] }) {
  const AGENT_COLOR: Record<string, string> = {
    TimelineAgent:    "var(--blue)",
    MemoryAgent:      "var(--red)",
    PersistenceAgent: "var(--orange)",
    VerifierAgent:    "var(--violet)",
  }

  return (
    <div style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase",
        letterSpacing: "0.06em", marginBottom: 4 }}>Agent Execution Log</p>
      {logs.map(log => (
        <div key={log.id} style={{
          padding: "10px 12px",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          borderLeft: `3px solid ${AGENT_COLOR[log.agent] || "var(--border-strong)"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: AGENT_COLOR[log.agent] || "var(--text-1)" }}>
              {log.agent}
            </span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {log.hash_verified && (
                <span style={{ fontSize: 10, color: "var(--green)", fontWeight: 500 }}>✓ hash</span>
              )}
              {log.spoliation_detected && (
                <span style={{ fontSize: 10, color: "var(--red)", fontWeight: 600 }}>⚠ SPOLIATION</span>
              )}
              <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>
                {log.duration_ms > 1000 ? `${(log.duration_ms/1000).toFixed(1)}s` : `${log.duration_ms}ms`}
              </span>
            </div>
          </div>
          <p className="mono" style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 3 }}>{log.tool_name}</p>
          {log.result_summary && (
            <p style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.4 }}>{log.result_summary}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main report view ──────────────────────────────────────────────────────────
export function ReportView({ investigationId, onBack }: { investigationId: string; onBack: () => void }) {
  const [report, setReport] = useState<InvestigationReport | null>(null)
  const [selected, setSelected] = useState<Finding | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"findings" | "agents">("findings")

  useEffect(() => {
    fetchInvestigation(investigationId)
      .then(r => {
        setReport(r)
        if (r.findings.length) setSelected(r.findings[0])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
    // Refresh if still running
    const interval = setInterval(() => {
      fetchInvestigation(investigationId).then(r => {
        setReport(r)
        if (!selected && r.findings.length) setSelected(r.findings[0])
      }).catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [investigationId])

  if (loading) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 28, height: 28, border: "2px solid var(--border)", borderTopColor: "var(--blue)",
          borderRadius: "50%", animation: "spin .7s linear infinite", margin: "0 auto 12px" }} />
        <p style={{ fontSize: 13, color: "var(--text-2)" }}>Loading investigation…</p>
      </div>
    </div>
  )
  if (!report) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <p style={{ color: "var(--red)" }}>Investigation not found</p>
    </div>
  )

  const critical    = report.findings.filter(f => f.severity === "critical" && !f.contradiction).length
  const high        = report.findings.filter(f => f.severity === "high" && !f.contradiction).length
  const contradictions = report.findings.filter(f => f.contradiction)
  const regular     = report.findings.filter(f => !f.contradiction)
  const slack_tracked = report.findings.filter(f => f.slack_status && f.slack_status !== "pending_review").length

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Top bar */}
      <div style={{
        padding: "0 24px",
        height: 52,
        background: "var(--bg)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={onBack} style={{
            display: "flex", alignItems: "center", gap: 5,
            background: "none", border: "none", cursor: "pointer",
            color: "var(--text-2)", fontSize: 13, padding: "4px 0",
          }}
          onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = "var(--text-0)"}
          onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = "var(--text-2)"}
          >
            ← All
          </button>
          <div style={{ width: 1, height: 16, background: "var(--border)" }} />
          <div>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-0)" }}>{report.case_id}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--text-3)", marginLeft: 10 }}>
              {report.image_path.split("/").pop()}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {/* Evidence badge */}
          <span style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500,
            background: report.evidence_integrity_verified ? "var(--green-bg)" : "var(--red-bg)",
            border: `1px solid ${report.evidence_integrity_verified ? "var(--green-b)" : "var(--red-b)"}`,
            color: report.evidence_integrity_verified ? "var(--green)" : "var(--red)",
          }}>
            {report.evidence_integrity_verified ? "✓ Evidence Verified" : "⚠ Evidence Issue"}
          </span>
          {/* Summary pills */}
          {critical > 0 && <Pill n={critical} label="critical" color="var(--red)" bg="var(--red-bg)" border="var(--red-b)" />}
          {high > 0     && <Pill n={high}     label="high"     color="var(--orange)" bg="var(--orange-bg)" border="var(--orange-b)" />}
          {contradictions.length > 0 && <Pill n={contradictions.length} label="⚡ contra" color="var(--violet)" bg="var(--violet-bg)" border="var(--violet-b)" />}
          {slack_tracked > 0 && <Pill n={slack_tracked} label="reviewed" color="var(--green)" bg="var(--green-bg)" border="var(--green-b)" />}
        </div>
      </div>

      {/* Body — 3 columns */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left — findings list */}
        <div style={{
          width: 280,
          flexShrink: 0,
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          background: "var(--bg)",
        }}>
          {/* Tabs */}
          <div style={{
            display: "flex",
            borderBottom: "1px solid var(--border)",
            padding: "0 4px",
          }}>
            {(["findings", "agents"] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                flex: 1,
                padding: "10px 8px",
                border: "none", background: "none", cursor: "pointer",
                fontSize: 12, fontWeight: activeTab === tab ? 600 : 400,
                color: activeTab === tab ? "var(--blue)" : "var(--text-3)",
                borderBottom: activeTab === tab ? "2px solid var(--blue)" : "2px solid transparent",
                marginBottom: -1,
                textTransform: "capitalize",
              }}>
                {tab}
                <span style={{ marginLeft: 5, fontSize: 10, background: "var(--bg-raised)",
                  padding: "1px 5px", borderRadius: 10, color: "var(--text-3)" }}>
                  {tab === "findings" ? report.findings.length : report.execution_log.length}
                </span>
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            {activeTab === "findings" ? (
              <>
                {contradictions.length > 0 && (
                  <div style={{ padding: "6px 8px", background: "var(--violet-bg)",
                    borderBottom: "1px solid var(--violet-b)" }}>
                    <p style={{ fontSize: 10, fontWeight: 600, color: "var(--violet)",
                      textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      ⚡ {contradictions.length} Contradiction{contradictions.length > 1 ? "s" : ""}
                    </p>
                  </div>
                )}
                {[...contradictions, ...regular].map(f => (
                  <FindingItem
                    key={f.id}
                    finding={f}
                    selected={selected?.id === f.id}
                    onClick={() => setSelected(f)}
                  />
                ))}
                {report.findings.length === 0 && (
                  <div style={{ padding: 24, textAlign: "center" }}>
                    <p style={{ fontSize: 12, color: "var(--text-3)" }}>No findings</p>
                  </div>
                )}
              </>
            ) : (
              <AgentLogPanel logs={report.execution_log} />
            )}
          </div>
        </div>

        {/* Center — finding detail */}
        <div style={{ flex: 1, overflowY: "auto", background: "var(--bg)" }}>
          {selected ? (
            <FindingDetail finding={selected} />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
              <p style={{ fontSize: 13, color: "var(--text-3)" }}>Select a finding</p>
            </div>
          )}
        </div>

        {/* Right — stats / SHA */}
        <div style={{
          width: 220,
          flexShrink: 0,
          borderLeft: "1px solid var(--border)",
          background: "var(--bg-subtle)",
          overflowY: "auto",
          padding: "16px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}>
          <SideSection title="Case">
            <p className="mono" style={{ fontSize: 11, color: "var(--text-2)", wordBreak: "break-all" }}>
              {report.case_id}
            </p>
          </SideSection>

          <SideSection title="Started">
            <p style={{ fontSize: 12, color: "var(--text-1)" }}>
              {new Date(report.started_at).toLocaleString()}
            </p>
          </SideSection>

          {report.completed_at && (
            <SideSection title="Completed">
              <p style={{ fontSize: 12, color: "var(--text-1)" }}>
                {new Date(report.completed_at).toLocaleString()}
              </p>
            </SideSection>
          )}

          <SideSection title="SHA-256">
            <p className="mono" style={{ fontSize: 10, color: "var(--text-3)", wordBreak: "break-all", lineHeight: 1.5 }}>
              {report.image_sha256 && report.image_sha256 !== "demo_mode"
                ? report.image_sha256
                : "—"}
            </p>
          </SideSection>

          <SideSection title="Findings">
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {(["critical","high","medium","low"] as const).map(s => {
                const n = regular.filter(f => f.severity === s).length
                if (!n) return null
                const c = SEV_CONFIG[s]
                return (
                  <div key={s} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 11, color: c.color, fontWeight: 500, textTransform: "capitalize" }}>{s}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: c.color }}>{n}</span>
                  </div>
                )
              })}
              {contradictions.length > 0 && (
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 11, color: "var(--violet)", fontWeight: 500 }}>⚡ Contradictions</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--violet)" }}>{contradictions.length}</span>
                </div>
              )}
            </div>
          </SideSection>

          {slack_tracked > 0 && (
            <SideSection title="Slack Activity">
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {["confirmed","false_positive"].map(st => {
                  const n = report.findings.filter(f => f.slack_status === st).length
                  if (!n) return null
                  const c = SLACK_CONFIG[st]
                  return (
                    <div key={st} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 11, color: c.color }}>{c.icon} {c.label}</span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: c.color }}>{n}</span>
                    </div>
                  )
                })}
              </div>
            </SideSection>
          )}
        </div>
      </div>
    </div>
  )
}

function Pill({ n, label, color, bg, border }: { n: number; label: string; color: string; bg: string; border: string }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "3px 9px", borderRadius: 20, fontSize: 11, fontWeight: 500,
      background: bg, border: `1px solid ${border}`, color,
    }}>
      {n} {label}
    </span>
  )
}

function SideSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{ fontSize: 10, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase",
        letterSpacing: "0.06em", marginBottom: 7 }}>{title}</p>
      {children}
    </div>
  )
}
