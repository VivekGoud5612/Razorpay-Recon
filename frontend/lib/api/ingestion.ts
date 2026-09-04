import { apiPostForm } from './client'
import type { IngestMerchantSourceResponse } from '@/lib/types/domain'

/**
 * POST /ingestion/merchant/batch — uploads several merchant-side source
 * files in one request (multipart/form-data, repeated `files` fields).
 *
 * The backend dispatches each file to its merchant_source_id purely by
 * filename (SOURCE_BY_FILENAME in api/routes/ingestion.py: merchant_orders.csv,
 * ledger.csv, pos.csv, other_gateway.csv, bank_statement.csv) — not by any
 * field the caller sends — so each entry's `filename` must be that exact
 * expected name, regardless of the File object's own local name. The
 * response is a list of per-file results in the same order the files were
 * sent.
 */
export function ingestMerchantSourcesBatch(
  entries: { file: File; filename: string }[],
  options?: { signal?: AbortSignal },
): Promise<IngestMerchantSourceResponse[]> {
  const form = new FormData()
  for (const { file, filename } of entries) {
    form.append('files', file, filename)
  }

  return apiPostForm<IngestMerchantSourceResponse[]>('/ingestion/merchant/batch', form, options)
}
