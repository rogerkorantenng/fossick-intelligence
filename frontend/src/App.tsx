import { useState } from "react"
import { InvestigationList } from "./components/InvestigationList"
import { ReportView } from "./components/ReportView"

export default function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  return (
    <div>
      {/* Nav */}
      <div style={{ padding: "0 16px", height: 42, background: "#fff",
        borderBottom: "1px solid #E2E5EC", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 24, height: 24, borderRadius: 5, background: "#2563EB",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 12, fontWeight: 700, color: "#fff" }}>F</div>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#111827", cursor: "pointer" }}
          onClick={() => setSelectedId(null)}>Fossick</span>
        {selectedId && (
          <>
            <span style={{ color: "#D1D5DB" }}>/</span>
            <button onClick={() => setSelectedId(null)}
              style={{ fontSize: 13, color: "#6B7280", background: "none", border: "none", cursor: "pointer" }}>
              Investigations
            </button>
            <span style={{ color: "#D1D5DB" }}>/</span>
            <span style={{ fontSize: 13, color: "#111827" }}>{selectedId.slice(0, 8)}…</span>
          </>
        )}
      </div>

      {selectedId
        ? <ReportView investigationId={selectedId} />
        : <InvestigationList onSelect={setSelectedId} />
      }
    </div>
  )
}
