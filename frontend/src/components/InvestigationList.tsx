import { useEffect, useState } from "react"
import { fetchAllInvestigations, startInvestigation } from "../api"
import type { InvestigationSummary } from "../types"

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, [string, string, string]> = {
    completed: ["var(--green)", "var(--green-bg)", "var(--green-b)"],
    running:   ["var(--blue)",  "var(--blue-bg)",  "var(--blue-b)"],
    failed:    ["var(--red)",   "var(--red-bg)",   "var(--red-b)"],
  }
  const [color, bg, border] = colors[status] || ["var(--slate)", "var(--slate-bg)", "var(--slate-b)"]
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 500,
      background: bg, border: `1px solid ${border}`, color,
    }}>
      <span style={{
        width: 5, height: 5, borderRadius: "50%", background: color, flexShrink: 0,
        animation: status === "running" ? "pulse 1.5s ease-in-out infinite" : "none",
      }} />
      {status === "running" ? "Analyzing…" : status === "completed" ? "Complete" : "Failed"}
    </span>
  )
}

export function InvestigationList({ onSelect }: { onSelect: (id: string) => void }) {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([])
  const [imagePath, setImagePath] = useState("")
  const [caseId, setCaseId] = useState("")
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    const load = () => fetchAllInvestigations().then(setInvestigations).catch(() => {})
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  async function handleStart() {
    if (!imagePath.trim()) return
    setStarting(true); setError("")
    try {
      await startInvestigation(imagePath.trim(), caseId.trim() || undefined)
      setImagePath(""); setCaseId("")
      setTimeout(() => fetchAllInvestigations().then(setInvestigations), 800)
    } catch (e) {
      setError("Failed to start investigation")
    } finally { setStarting(false) }
  }

  const byStatus = {
    running:   investigations.filter(i => i.status === "running").length,
    completed: investigations.filter(i => i.status === "completed").length,
  }

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "32px 40px" }}>

      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h1 className="display" style={{ fontSize: 24, fontWeight: 700, color: "var(--text-0)", marginBottom: 4 }}>
              Investigations
            </h1>
            <p style={{ fontSize: 13, color: "var(--text-2)" }}>
              Autonomous DFIR analysis across disk and memory artifacts
            </p>
          </div>
          {investigations.length > 0 && (
            <div style={{ display: "flex", gap: 16 }}>
              <Stat label="Complete" value={byStatus.completed} color="var(--green)" />
              <Stat label="Running"  value={byStatus.running}   color="var(--blue)"  />
              <Stat label="Total"    value={investigations.length} color="var(--text-2)" />
            </div>
          )}
        </div>
      </div>

      {/* New investigation card */}
      <div style={{
        background: "var(--bg)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "20px 24px",
        marginBottom: 24,
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-1)", marginBottom: 14, letterSpacing: "0.03em", textTransform: "uppercase" }}>
          New Investigation
        </p>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ flex: "2 1 280px" }}>
            <label style={{ fontSize: 11, color: "var(--text-2)", display: "block", marginBottom: 5 }}>Image Path</label>
            <input
              value={imagePath}
              onChange={e => setImagePath(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleStart()}
              placeholder="/case_data/disk.E01  or  /case_data/memory.vmem"
              className="mono"
              style={{
                width: "100%", padding: "8px 12px",
                border: "1px solid var(--border)", borderRadius: 7,
                fontSize: 12, color: "var(--text-0)", background: "var(--bg-subtle)",
                outline: "none", transition: "border-color .15s",
              }}
              onFocus={e => (e.target.style.borderColor = "var(--blue)")}
              onBlur={e => (e.target.style.borderColor = "var(--border)")}
            />
          </div>
          <div style={{ flex: "1 1 160px" }}>
            <label style={{ fontSize: 11, color: "var(--text-2)", display: "block", marginBottom: 5 }}>Case ID <span style={{ color: "var(--text-4)" }}>(optional)</span></label>
            <input
              value={caseId}
              onChange={e => setCaseId(e.target.value)}
              placeholder="incident-2026-001"
              style={{
                width: "100%", padding: "8px 12px",
                border: "1px solid var(--border)", borderRadius: 7,
                fontSize: 12, color: "var(--text-0)", background: "var(--bg-subtle)",
                outline: "none", transition: "border-color .15s",
              }}
              onFocus={e => (e.target.style.borderColor = "var(--blue)")}
              onBlur={e => (e.target.style.borderColor = "var(--border)")}
            />
          </div>
          <button
            onClick={handleStart}
            disabled={starting || !imagePath.trim()}
            style={{
              padding: "8px 20px", borderRadius: 7, border: "none",
              background: starting || !imagePath.trim() ? "var(--bg-raised)" : "var(--blue)",
              color: starting || !imagePath.trim() ? "var(--text-3)" : "#fff",
              fontSize: 13, fontWeight: 500, cursor: starting || !imagePath.trim() ? "not-allowed" : "pointer",
              transition: "all .15s", whiteSpace: "nowrap", alignSelf: "flex-end",
              marginBottom: 0, flexShrink: 0,
            }}
          >
            {starting ? "Starting…" : "Analyze →"}
          </button>
        </div>
        {error && <p style={{ fontSize: 12, color: "var(--red)", marginTop: 8 }}>{error}</p>}
      </div>

      {/* Investigations table */}
      {investigations.length === 0 ? (
        <EmptyState />
      ) : (
        <div style={{
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        }}>
          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 180px 100px 90px 120px",
            padding: "10px 20px",
            background: "var(--bg-subtle)",
            borderBottom: "1px solid var(--border)",
          }}>
            {["Case / Image", "Started", "Status", "Findings", "Contradictions"].map(h => (
              <span key={h} style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.04em", textTransform: "uppercase" }}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          {investigations.map((inv, i) => (
            <InvRow key={inv.id} inv={inv} last={i === investigations.length - 1} onClick={() => onSelect(inv.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

function InvRow({ inv, last, onClick }: { inv: InvestigationSummary; last: boolean; onClick: () => void }) {
  const [hovered, setHovered] = useState(false)
  const canClick = inv.status === "completed"
  const started = new Date(inv.started_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })

  return (
    <div
      onClick={canClick ? onClick : undefined}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 180px 100px 90px 120px",
        padding: "13px 20px",
        borderBottom: last ? "none" : "1px solid var(--border)",
        background: hovered && canClick ? "var(--bg-subtle)" : "transparent",
        cursor: canClick ? "pointer" : "default",
        transition: "background .1s",
        alignItems: "center",
      }}
    >
      <div>
        <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-0)", marginBottom: 2 }}>{inv.case_id}</p>
        <p className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>
          {inv.image_path.split("/").pop()}
        </p>
      </div>
      <span style={{ fontSize: 12, color: "var(--text-2)" }}>{started}</span>
      <StatusPill status={inv.status} />
      <span style={{ fontSize: 13, color: "var(--text-1)", fontWeight: 500 }}>—</span>
      {inv.contradictions_detected > 0 ? (
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          fontSize: 12, fontWeight: 500, color: "var(--violet)",
        }}>
          <span style={{ fontSize: 14 }}>⚡</span> {inv.contradictions_detected}
        </span>
      ) : (
        <span style={{ fontSize: 12, color: "var(--text-4)" }}>—</span>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ textAlign: "right" }}>
      <p style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>{value}</p>
      <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>{label}</p>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 12,
      padding: "60px 24px", textAlign: "center",
      boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: "var(--bg-raised)", border: "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 14px",
      }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--text-4)" strokeWidth="1.5">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
      </div>
      <p style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)", marginBottom: 4 }}>No investigations yet</p>
      <p style={{ fontSize: 13, color: "var(--text-3)" }}>Enter a forensic image path above to start your first analysis</p>
    </div>
  )
}
