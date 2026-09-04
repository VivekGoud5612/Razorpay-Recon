import { apiPostForm } from './client'
import type { IngestMerchantSourceResponse, MerchantSourceId } from '@/lib/types/domain'

/**
 * POST /ingestion/merchant — uploads one merchant-side source file
 * (multipart/form-data: `file`, `merchant_source_id`).
 */
export function ingestMerchantSource(
  file: File,
  merchantSourceId: MerchantSourceId,
  options?: { signal?: AbortSignal },
): Promise<IngestMerchantSourceResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('merchant_source_id', merchantSourceId)

  return apiPostForm<IngestMerchantSourceResponse>('/ingestion/merchant', form, options)
}
