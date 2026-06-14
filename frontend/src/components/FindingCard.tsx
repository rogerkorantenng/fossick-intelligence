import type { Finding } from "../types"

const CONF_CONFIG = {
  HIGH:   { bg: "#FEF2F2", border: "#FECACA", text: "#991B1B" },
  MEDIUM: { bg: "#FFF7ED", border: "#FED7AA", text: "#9A3412" },
  LOW:    { bg: "#FFFBEB", border: "#FDE68A", text: "#92400E" },
}
const SEV_COLOR = { critical: "#DC2626", high: "#EA580C", medium: "#D97706", low: "#6B7280" }

export function FindingCard({ finding, selected, onClick }: {
  finding: Finding; selected: boolean; onClick: () => void
}) {
  const conf = CONF_CONFIG[finding.confidence]
  return (
    <div onClick={onClick} style={{
      padding: "10px 12px",
      border: `1px solid ${selected ? SEV_COLOR[finding.severity] : "#E2E5EC"}`,
      borderLeft: `3px solid ${SEV_COLOR[finding.severity]}`,
      borderRadius: 6, background: selected ? "#F8F9FB" : "#fff",
      cursor: "pointer", marginBottom: 6, transition: "all 0.1s",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#111827" }}>{finding.title}</span>
        <span style={{ fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 3,
          background: conf.bg, border: `1px solid ${conf.border}`, color: conf.text }}>
          {finding.confidence}
        </span>
      </div>
      <p style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.4, marginBottom: 4 }}>
        {finding.description.slice(0, 120)}{finding.description.length > 120 ? "…" : ""}
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {finding.sources.map(s => (
          <span key={s} style={{ fontSize: 10, padding: "1px 6px", borderRadius: 10,
            background: "#EFF6FF", border: "1px solid #BFDBFE", color: "#1D4ED8" }}>{s}</span>
        ))}
        {finding.contradiction && (
          <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 10,
            background: "#FEF3C7", border: "1px solid #FDE68A", color: "#92400E" }}>⚡ contradiction</span>
        )}
        {finding.slack_status === "pending_review" && (
          <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 10,
            background: "#FFFBEB", border: "1px solid #FDE68A", color: "#92400E" }}>⏳ Slack review</span>
        )}
      </div>
    </div>
  )
}
