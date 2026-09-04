'use client'

import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Dashboard } from '@/components/views/dashboard'
import { ReconciliationsList } from '@/components/views/reconciliations-list'
import { NewReconciliation } from '@/components/views/new-reconciliation'
import { ReconciliationDetail } from '@/components/views/reconciliation-detail'
import { FindingDetail } from '@/components/views/finding-detail'
import { EvidenceExplorer } from '@/components/views/evidence-explorer'
import { GraphPage } from '@/components/views/graph-page'
import { InvestigationPage } from '@/components/views/investigation-page'

export default function Page() {
  // react-router-dom's BrowserRouter touches `window` on construction, so this client-only
  // SPA shell can't render during Next's SSR pass. Bailing out via a synchronous
  // `typeof window` check would make the client's hydration-pass render diverge from the
  // server's in the same pass (hydration mismatch). Instead, render nothing on both the
  // server and the client's first (hydration) pass, and only mount the router tree from a
  // subsequent effect — a plain client-side update, not part of hydration diffing.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  if (!mounted) return null

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/reconciliations" element={<ReconciliationsList />} />
        <Route path="/reconciliations/new" element={<NewReconciliation />} />
        <Route path="/reconciliations/:id" element={<ReconciliationDetail />} />
        <Route path="/reconciliations/:id/findings/:findingId" element={<FindingDetail />} />
        <Route path="/reconciliations/:id/evidence" element={<EvidenceExplorer />} />
        <Route path="/reconciliations/:id/graph" element={<GraphPage />} />
        <Route path="/investigations/:id" element={<InvestigationPage />} />
      </Routes>
    </BrowserRouter>
  )
}
