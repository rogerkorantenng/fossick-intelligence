import type { Finding } from "../types"

const SEV_DOT: Record<string, string> = {
  critical: "#DC2626", high: "#EA580C", medium: "#D97706", low: "#6B7280"
}

export function TimelinePanel({ findings }: { findings: Finding[] }) {
  const withTs = findings
    .filter(f => f.timestamp)
    .sort((a, b) => new Date(a.timestamp!).getTime() - new Date(b.timestamp!).getTime())

  if (!withTs.length) return (
    <p style={{ fontSize: 12, color: "#6B7280", padding: "16px 0", textAlign: "center" }}>
      No timestamped events
    </p>
  )

  return (
    <div style={{ position: "relative", paddingLeft: 20 }}>
      <div style={{ position: "absolute", left: 7, top: 8, bottom: 8, width: 1, background: "#E2E5EC" }} />
      {withTs.map(f => (
        <div key={f.id} style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 14, position: "relative" }}>
          <div style={{ position: "absolute", left: -13, top: 4, width: 8, height: 8, borderRadius: "50%",
            background: SEV_DOT[f.severity] || "#6B7280", border: "2px solid #fff" }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 10, color: "#9CA3AF", fontFamily: "'JetBrains Mono', monospace", marginBottom: 2 }}>
              {new Date(f.timestamp!).toLocaleString()}
            </p>
            <p style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginBottom: 1 }}>{f.title}</p>
            <p style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.4 }}>
              {f.description.slice(0, 100)}{f.description.length > 100 ? "…" : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
