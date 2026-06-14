import type { InvestigationReport, InvestigationSummary } from "./types"

export async function fetchAllInvestigations(): Promise<InvestigationSummary[]> {
  const res = await fetch("/investigations")
  if (!res.ok) throw new Error("Failed to fetch investigations")
  return res.json()
}

export async function fetchInvestigation(id: string): Promise<InvestigationReport> {
  const res = await fetch(`/investigations/${id}`)
  if (!res.ok) throw new Error(`Investigation ${id} not found`)
  return res.json()
}

export async function startInvestigation(imagePath: string, caseId?: string): Promise<{ status: string }> {
  const res = await fetch("/investigate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_path: imagePath, case_id: caseId }),
  })
  if (!res.ok) throw new Error("Failed to start investigation")
  return res.json()
}
