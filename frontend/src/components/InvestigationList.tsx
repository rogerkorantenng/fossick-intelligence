import { useEffect, useState } from "react"
import { fetchAllInvestigations, startInvestigation } from "../api"
import type { InvestigationSummary } from "../types"

export function InvestigationList({ onSelect }: { onSelect: (id: string) => void }) {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([])
  const [imagePath, setImagePath] = useState("")
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    const load = () => fetchAllInvestigations().then(setInvestigations).catch(() => {})
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  async function handleStart() {
    if (!imagePath.trim()) return
    setStarting(true)
    try {
      await startInvestigation(imagePath.trim())
      setTimeout(() => fetchAllInvestigations().then(setInvestigations), 1000)
    } finally { setStarting(false) }
  }

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: "0 20px" }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: "#111827", marginBottom: 4 }}>Fossick</h1>
        <p style={{ fontSize: 14, color: "#6B7280" }}>Autonomous DFIR — finds evil, shows its work, catches itself lying</p>
      </div>

      <div style={{ padding: 16, background: "#fff", border: "1px solid #E2E5EC", borderRadius: 8, marginBottom: 24 }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 8 }}>New Investigation</p>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={imagePath} onChange={e => setImagePath(e.target.value)}
            placeholder="/case_data/disk.E01 or /case_data/memory.vmem"
            onKeyDown={e => e.key === "Enter" && handleStart()}
            style={{ flex: 1, padding: "7px 12px", border: "1px solid #D1D5DB", borderRadius: 6,
              fontSize: 13, fontFamily: "'JetBrains Mono', monospace", outline: "none" }}
          />
          <button onClick={handleStart} disabled={starting || !imagePath.trim()}
            style={{ padding: "7px 16px", borderRadius: 6, border: "none",
              background: starting || !imagePath.trim() ? "#E5E7EB" : "#2563EB",
              color: starting || !imagePath.trim() ? "#6B7280" : "#fff",
              fontSize: 13, fontWeight: 500, cursor: starting || !imagePath.trim() ? "not-allowed" : "pointer" }}>
            {starting ? "Starting…" : "Analyze"}
          </button>
        </div>
      </div>

      {investigations.length === 0 ? (
        <p style={{ fontSize: 13, color: "#9CA3AF", textAlign: "center", padding: 32 }}>
          No investigations yet. Enter an image path to start.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {investigations.map(inv => (
            <div key={inv.id} onClick={() => inv.status === "completed" && onSelect(inv.id)}
              style={{ padding: "12px 14px", background: "#fff", border: "1px solid #E2E5EC",
                borderRadius: 8, cursor: inv.status === "completed" ? "pointer" : "default", transition: "border-color 0.1s" }}
              onMouseEnter={e => { if (inv.status === "completed") (e.currentTarget as HTMLElement).style.borderColor = "#2563EB" }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "#E2E5EC" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 2 }}>{inv.case_id}</p>
                  <p style={{ fontSize: 11, color: "#6B7280", fontFamily: "'JetBrains Mono', monospace" }}>{inv.image_path}</p>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {inv.contradictions_detected > 0 && (
                    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10,
                      background: "#FEF3C7", border: "1px solid #FDE68A", color: "#92400E" }}>
                      {inv.contradictions_detected} contradictions</span>
                  )}
                  <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, fontWeight: 500,
                    background: inv.status === "completed" ? "#F0FDF4" : inv.status === "running" ? "#EFF6FF" : "#FEF2F2",
                    color: inv.status === "completed" ? "#15803D" : inv.status === "running" ? "#1D4ED8" : "#DC2626",
                    border: `1px solid ${inv.status === "completed" ? "#BBF7D0" : inv.status === "running" ? "#BFDBFE" : "#FECACA"}` }}>
                    {inv.status === "running" ? "⟳ Running" : inv.status === "completed" ? "✓ Done" : "✗ Failed"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
