import { useState } from "react"
import { InvestigationList } from "./components/InvestigationList"
import { ReportView } from "./components/ReportView"

type View = { page: "list" } | { page: "report"; id: string }

export default function App() {
  const [view, setView] = useState<View>({ page: "list" })

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-subtle)", overflow: "hidden" }}>
      {/* Sidebar */}
      <aside style={{
        width: "var(--sidebar-w)",
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        background: "var(--bg)",
        borderRight: "1px solid var(--border)",
        overflow: "hidden",
      }}>
        {/* Logo */}
        <div style={{ padding: "20px 18px 16px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 2 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: "linear-gradient(135deg, #1D4ED8 0%, #6D28D9 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
            }}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M2 8l4 4 8-8" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="12" cy="4" r="2" fill="rgba(255,255,255,0.4)"/>
              </svg>
            </div>
            <div>
              <p className="display" style={{ fontSize: 13, fontWeight: 700, color: "var(--text-0)", lineHeight: 1.2 }}>
                Fossick
              </p>
              <p style={{ fontSize: 9, color: "var(--text-3)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                Intelligence
              </p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: "10px 8px", flex: 1 }}>
          <NavItem
            icon={<GridIcon />}
            label="Investigations"
            active={view.page === "list"}
            onClick={() => setView({ page: "list" })}
          />
          {view.page === "report" && (
            <NavItem
              icon={<DocIcon />}
              label="Current Report"
              active={true}
              onClick={() => {}}
              sub
            />
          )}
        </nav>

        {/* Footer */}
        <div style={{ padding: "12px 14px", borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%",
              background: "var(--green)",
              boxShadow: "0 0 0 2px var(--green-bg)",
            }} />
            <span style={{ fontSize: 11, color: "var(--text-2)" }}>Agent online</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {view.page === "list"
          ? <InvestigationList onSelect={id => setView({ page: "report", id })} />
          : <ReportView
              investigationId={(view as { page: "report"; id: string }).id}
              onBack={() => setView({ page: "list" })}
            />
        }
      </main>
    </div>
  )
}

function NavItem({ icon, label, active, onClick, sub }: {
  icon: React.ReactNode; label: string; active: boolean; onClick: () => void; sub?: boolean
}) {
  return (
    <button onClick={onClick} style={{
      width: "100%", display: "flex", alignItems: "center", gap: 8,
      padding: sub ? "6px 8px 6px 24px" : "6px 8px",
      borderRadius: 6, border: "none", cursor: "pointer", textAlign: "left",
      background: active ? "var(--blue-bg)" : "transparent",
      color: active ? "var(--blue)" : "var(--text-2)",
      fontSize: 13, fontWeight: active ? 500 : 400,
      transition: "all 0.1s",
      marginBottom: 1,
    }}
    onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "var(--bg-hover)" }}
    onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent" }}
    >
      <span style={{ opacity: active ? 1 : 0.6, flexShrink: 0 }}>{icon}</span>
      {label}
    </button>
  )
}

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  )
}

function DocIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M3 2h7l3 3v9H3V2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      <path d="M10 2v3h3" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      <line x1="5" y1="7" x2="11" y2="7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <line x1="5" y1="10" x2="9" y2="10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}
