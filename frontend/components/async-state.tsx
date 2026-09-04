'use client'

import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { ApiError } from '@/lib/api/client'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state-panel">
      <Loader2 className="spin" size={20} />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="state-panel">
      <Inbox size={20} />
      <b>{title}</b>
      <p>{message}</p>
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  const status = error instanceof ApiError ? error.status : null

  return (
    <div className="state-panel error">
      <AlertTriangle size={20} />
      <b>{status ? `Request failed (${status})` : 'Request failed'}</b>
      <p>{message}</p>
      {retry && (
        <button className="button" onClick={retry}>
          Retry
        </button>
      )}
    </div>
  )
}
