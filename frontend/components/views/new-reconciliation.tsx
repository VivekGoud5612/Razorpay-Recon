'use client'

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Upload } from 'lucide-react'
import { Shell, Title } from '@/components/shell'
import { useIngestMerchantSource } from '@/lib/hooks/useIngestMerchantSource'
import { useRunReconciliation } from '@/lib/hooks/useRunReconciliation'
import { ApiError } from '@/lib/api/client'
import type { MerchantSourceId } from '@/lib/types/domain'

// The fixed merchant source types the ingestion endpoint accepts (seeded in
// the `sources` table). Labels are the operator-facing names for each.
const SOURCE_SLOTS: { id: MerchantSourceId; label: string; hint: string }[] = [
  { id: 'merchant_orders', label: 'Orders', hint: 'merchant_orders.csv' },
  { id: 'merchant_ledger', label: 'Ledger', hint: 'ledger.csv' },
  { id: 'merchant_bank', label: 'Bank statement', hint: 'bank_statement.csv' },
  { id: 'merchant_pos', label: 'POS', hint: 'pos.csv' },
  { id: 'merchant_gateway', label: 'Other gateway', hint: 'other_gateway.csv' },
]

type SlotStatus = 'idle' | 'uploading' | 'done' | 'error'

interface SlotState {
  file: File | null
  status: SlotStatus
  importId?: string
  error?: string
}

const initialSlots: Record<MerchantSourceId, SlotState> = Object.fromEntries(
  SOURCE_SLOTS.map((slot) => [slot.id, { file: null, status: 'idle' as SlotStatus }]),
) as Record<MerchantSourceId, SlotState>

export function NewReconciliation() {
  const navigate = useNavigate()
  const ingest = useIngestMerchantSource()
  const runReconciliation = useRunReconciliation()

  const [settlementId, setSettlementId] = useState('')
  const [slots, setSlots] = useState<Record<MerchantSourceId, SlotState>>(initialSlots)
  const [runError, setRunError] = useState<string | null>(null)
  const [phase, setPhase] = useState<'idle' | 'ingesting' | 'running'>('idle')

  const filledSlots = SOURCE_SLOTS.filter((slot) => slots[slot.id].file !== null)
  const canSubmit = settlementId.trim().length > 0 && filledSlots.length > 0 && phase === 'idle'

  const setSlot = (id: MerchantSourceId, patch: Partial<SlotState>) => {
    setSlots((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  const handleFileChange = (id: MerchantSourceId, file: File | null) => {
    setSlot(id, { file, status: 'idle', importId: undefined, error: undefined })
  }

  const handleSubmit = async () => {
    setRunError(null)
    setPhase('ingesting')

    const importIds: string[] = []

    for (const slot of filledSlots) {
      const state = slots[slot.id]
      if (!state.file) continue

      setSlot(slot.id, { status: 'uploading' })

      try {
        const response = await ingest.mutateAsync({ file: state.file, merchantSourceId: slot.id })
        setSlot(slot.id, { status: 'done', importId: response.import_id })
        importIds.push(response.import_id)
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Upload failed'
        setSlot(slot.id, { status: 'error', error: message })
        setPhase('idle')
        return
      }
    }

    setPhase('running')

    try {
      await runReconciliation.mutateAsync({ settlement_id: settlementId.trim(), import_ids: importIds })
      navigate(`/reconciliations/${encodeURIComponent(settlementId.trim())}`)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to run reconciliation'
      setRunError(message)
      setPhase('idle')
    }
  }

  return (
    <Shell>
      <main className="narrow">
        <div className="back">
          <Link to="/reconciliations">← Reconciliations</Link>
        </div>
        <Title eyebrow="NEW WORKSPACE" title="Start a reconciliation" />
        <p className="lead">
          Enter the Razorpay settlement to reconcile, then upload the merchant-side source files. Each file is ingested
          individually and tagged with its source type before the deterministic engine runs.
        </p>

        <div className="field-row">
          <label htmlFor="settlement-id">Settlement ID</label>
          <input
            id="settlement-id"
            type="text"
            placeholder="e.g. SETL-S11-001"
            value={settlementId}
            onChange={(e) => setSettlementId(e.target.value)}
            disabled={phase !== 'idle'}
          />
        </div>

        <div className="source-picker">
          {SOURCE_SLOTS.map((slot) => {
            const state = slots[slot.id]
            return (
              <div className={`source-slot ${state.status === 'done' ? 'filled' : ''}`} key={slot.id}>
                <b>{slot.label}</b>
                <span>{slot.hint}</span>
                <input
                  type="file"
                  accept=".csv"
                  disabled={phase !== 'idle'}
                  onChange={(e) => handleFileChange(slot.id, e.target.files?.[0] ?? null)}
                />
                {state.status === 'uploading' && <span>Uploading…</span>}
                {state.status === 'done' && (
                  <span>
                    <FileText size={12} /> {state.importId}
                  </span>
                )}
                {state.status === 'error' && <span className="form-error">{state.error}</span>}
              </div>
            )
          })}
        </div>

        {phase === 'running' && <p className="lead">Running deterministic reconciliation…</p>}
        {runError && <p className="form-error">{runError}</p>}

        <div className="actions">
          <Link className="button" to="/reconciliations">
            Cancel
          </Link>
          <button className="button primary" disabled={!canSubmit} onClick={handleSubmit}>
            {phase === 'ingesting' ? 'Ingesting…' : phase === 'running' ? 'Running…' : 'Ingest & run'}
            <Upload size={15} />
          </button>
        </div>
      </main>
    </Shell>
  )
}
