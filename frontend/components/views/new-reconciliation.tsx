'use client'

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Upload } from 'lucide-react'
import { Shell, Title } from '@/components/shell'
import { useIngestMerchantSourcesBatch } from '@/lib/hooks/useIngestMerchantSourcesBatch'
import { useRunReconciliation } from '@/lib/hooks/useRunReconciliation'
import { ApiError } from '@/lib/api/client'
import type { MerchantSourceId } from '@/lib/types/domain'

// The fixed merchant source types the ingestion endpoint accepts (seeded in
// the `sources` table). `hint` doubles as the exact filename the batch
// endpoint dispatches on (SOURCE_BY_FILENAME in api/routes/ingestion.py) —
// files are sent under that name regardless of the file's local name, and
// it's also the exact filename we match a selected file against below.
const SOURCE_SLOTS: { id: MerchantSourceId; label: string; hint: string }[] = [
  { id: 'merchant_orders', label: 'Orders', hint: 'merchant_orders.csv' },
  { id: 'merchant_ledger', label: 'Ledger', hint: 'ledger.csv' },
  { id: 'merchant_bank', label: 'Bank statement', hint: 'bank_statement.csv' },
  { id: 'merchant_pos', label: 'POS', hint: 'pos.csv' },
  { id: 'merchant_gateway', label: 'Other gateway', hint: 'other_gateway.csv' },
]

const SLOT_BY_FILENAME: Record<string, MerchantSourceId> = Object.fromEntries(
  SOURCE_SLOTS.map((slot) => [slot.hint, slot.id]),
)

// Best-effort tokens for attributing a failed batch ingestion back to the
// slot that caused it — the backend's error text names either the exact
// filename (dispatch failure) or the entity type (validation failure), never
// a source id, so we match on both when we can.
const SLOT_ERROR_TOKENS: Record<MerchantSourceId, string[]> = {
  merchant_orders: ['merchant_orders.csv', 'merchant_order'],
  merchant_ledger: ['ledger.csv', 'ledger_entry'],
  merchant_bank: ['bank_statement.csv', 'bank_transaction'],
  merchant_pos: ['pos.csv', 'pos_transaction'],
  merchant_gateway: ['other_gateway.csv', 'gateway_transaction'],
}

function attributeError(message: string): MerchantSourceId | null {
  const lower = message.toLowerCase()
  const matches = SOURCE_SLOTS.filter((slot) => SLOT_ERROR_TOKENS[slot.id].some((token) => lower.includes(token)))
  return matches.length === 1 ? matches[0].id : null
}

type SlotStatus = 'idle' | 'uploading' | 'done' | 'error'
type Phase = 'idle' | 'ingesting' | 'running' | 'complete'

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
  const ingestBatch = useIngestMerchantSourcesBatch()
  const runReconciliation = useRunReconciliation()

  const [settlementId, setSettlementId] = useState('')
  const [slots, setSlots] = useState<Record<MerchantSourceId, SlotState>>(initialSlots)
  const [unmatchedFiles, setUnmatchedFiles] = useState<string[]>([])
  const [runError, setRunError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')

  const filledSlots = SOURCE_SLOTS.filter((slot) => slots[slot.id].file !== null)
  const canSubmit = settlementId.trim().length > 0 && filledSlots.length > 0 && phase === 'idle'

  const setSlot = (id: MerchantSourceId, patch: Partial<SlotState>) => {
    setSlots((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  // One multi-select input replaces the previous five separate file pickers.
  // Routing is unchanged: a selected file is matched to a source purely by
  // its exact filename (the same SOURCE_BY_FILENAME contract the backend
  // batch endpoint itself dispatches on) — a file with any other name is
  // left unmatched and reported, never guessed at.
  const handleFilesSelected = (fileList: FileList | null) => {
    if (!fileList) return

    const unmatched: string[] = []
    setSlots((prev) => {
      const next = { ...prev }
      for (const file of Array.from(fileList)) {
        const slotId = SLOT_BY_FILENAME[file.name]
        if (slotId) {
          next[slotId] = { file, status: 'idle', importId: undefined, error: undefined }
        } else {
          unmatched.push(file.name)
        }
      }
      return next
    })
    setUnmatchedFiles(unmatched)
  }

  const handleSubmit = async () => {
    setRunError(null)
    setPhase('ingesting')

    for (const slot of filledSlots) {
      setSlot(slot.id, { status: 'uploading', error: undefined })
    }

    let importIds: string[] = []

    try {
      const entries = filledSlots.map((slot) => ({ file: slots[slot.id].file as File, filename: slot.hint }))
      const responses = await ingestBatch.mutateAsync(entries)
      const bySourceId = new Map(responses.map((r) => [r.merchant_source_id, r]))

      for (const slot of filledSlots) {
        const response = bySourceId.get(slot.id)
        if (response) {
          setSlot(slot.id, { status: 'done', importId: response.import_id })
        }
      }

      importIds = responses.map((r) => r.import_id)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Batch ingestion failed'
      const failedSlot = attributeError(message)

      for (const slot of filledSlots) {
        if (failedSlot === null || slot.id === failedSlot) {
          setSlot(slot.id, { status: 'error', error: message })
        } else {
          setSlot(slot.id, { status: 'idle' })
        }
      }

      setPhase('idle')
      return
    }

    setPhase('running')

    try {
      await runReconciliation.mutateAsync({ settlement_id: settlementId.trim(), import_ids: importIds })
      setPhase('complete')
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
          Enter the Razorpay settlement to reconcile, then choose all of its merchant-side source files at once. Each file
          is routed to a source by its exact filename and sent to the backend in a single batch ingestion request before
          the deterministic engine runs.
        </p>

        <div className="field-row">
          <label htmlFor="settlement-id">Settlement ID</label>
          <input
            id="settlement-id"
            type="text"
            placeholder="the settlement ID this data belongs to"
            value={settlementId}
            onChange={(e) => setSettlementId(e.target.value)}
            disabled={phase !== 'idle'}
          />
        </div>

        <div className="upload-box">
          <input
            id="batch-files"
            type="file"
            accept=".csv"
            multiple
            disabled={phase !== 'idle'}
            onChange={(e) => handleFilesSelected(e.target.files)}
          />
          <label htmlFor="batch-files">
            <Upload size={22} />
            Choose files
            <span>Select all 5 source CSVs at once — merchant_orders.csv, ledger.csv, bank_statement.csv, pos.csv, other_gateway.csv</span>
          </label>
        </div>

        {unmatchedFiles.length > 0 && (
          <p className="form-error">
            {unmatchedFiles.length} file{unmatchedFiles.length === 1 ? '' : 's'} didn&apos;t match any expected source
            filename and were not selected: {unmatchedFiles.join(', ')}
          </p>
        )}

        <div className="file-list">
          {SOURCE_SLOTS.map((slot) => {
            const state = slots[slot.id]
            return (
              <div className="file-row" key={slot.id}>
                <FileText size={16} />
                <div>
                  <b>{slot.label}</b>
                  <span>{slot.hint}</span>
                </div>
                {!state.file && <span className="muted">Not selected</span>}
                {state.file && state.status === 'idle' && <span>Selected</span>}
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

        {phase !== 'idle' && (
          <ul className="step-list">
            <li className={phase === 'ingesting' ? 'active' : 'done'}>Uploading</li>
            <li className={phase === 'ingesting' ? 'active' : 'done'}>Ingesting (batch)</li>
            <li className={phase === 'running' ? 'active' : phase === 'complete' ? 'done' : ''}>Running reconciliation</li>
            <li className={phase === 'complete' ? 'active' : ''}>Complete</li>
          </ul>
        )}
        {runError && <p className="form-error">{runError}</p>}

        <div className="actions">
          <Link className="button" to="/reconciliations">
            Cancel
          </Link>
          <button className="button primary" disabled={!canSubmit} onClick={handleSubmit}>
            {phase === 'ingesting' ? 'Ingesting…' : phase === 'running' ? 'Running…' : phase === 'complete' ? 'Done' : 'Ingest & run'}
            <Upload size={15} />
          </button>
        </div>
      </main>
    </Shell>
  )
}
