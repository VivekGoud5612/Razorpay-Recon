import { useMutation } from '@tanstack/react-query'
import { ingestMerchantSourcesBatch } from '@/lib/api/ingestion'

/** Uploads + ingests several merchant-side source files in one batch request. */
export function useIngestMerchantSourcesBatch() {
  return useMutation({
    mutationFn: (entries: { file: File; filename: string }[]) => ingestMerchantSourcesBatch(entries),
  })
}
