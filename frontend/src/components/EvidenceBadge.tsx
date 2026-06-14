export function EvidenceBadge({ verified }: { verified: boolean }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 4, fontSize: 11, fontWeight: 600,
      background: verified ? "#F0FDF4" : "#FEF2F2",
      border: `1px solid ${verified ? "#BBF7D0" : "#FECACA"}`,
      color: verified ? "#15803D" : "#DC2626",
    }}>
      {verified ? "✓ Evidence Integrity Verified" : "⚠ Evidence Integrity — CHECK REQUIRED"}
    </span>
  )
}
