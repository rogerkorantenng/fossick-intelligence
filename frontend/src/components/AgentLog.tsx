import type { ToolCallLog } from "../types"

const AGENT_COLORS: Record<string, string> = {
  TimelineAgent: "#2563EB", MemoryAgent: "#DC2626",
  PersistenceAgent: "#EA580C", VerifierAgent: "#7C3AED",
}

export function AgentLog({ logs }: { logs: ToolCallLog[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {logs.map(log => (
        <div key={log.id} style={{ padding: "8px 10px", border: "1px solid #E2E5EC", borderRadius: 5, background: "#fff" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: AGENT_COLORS[log.agent] || "#374151" }}>{log.agent}</span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {log.hash_verified && <span style={{ fontSize: 9, color: "#16A34A" }}>✓ hash ok</span>}
              {log.spoliation_detected && <span style={{ fontSize: 9, color: "#DC2626", fontWeight: 700 }}>⚠ SPOLIATION</span>}
              <span style={{ fontSize: 10, color: "#9CA3AF", fontFamily: "'JetBrains Mono', monospace" }}>
                {log.duration_ms > 1000 ? `${(log.duration_ms/1000).toFixed(1)}s` : `${log.duration_ms}ms`}
              </span>
            </div>
          </div>
          <p style={{ fontSize: 10, color: "#6B7280", fontFamily: "'JetBrains Mono', monospace" }}>{log.tool_name}</p>
          {log.result_summary && <p style={{ fontSize: 10, color: "#374151", marginTop: 2 }}>{log.result_summary}</p>}
        </div>
      ))}
    </div>
  )
}
