import { useMutation } from '@tanstack/react-query'
import { ingestMerchantSource } from '@/lib/api/ingestion'
import type { MerchantSourceId } from '@/lib/types/domain'

/** Uploads + ingests one merchant-side source file. */
export function useIngestMerchantSource() {
  return useMutation({
    mutationFn: ({ file, merchantSourceId }: { file: File; merchantSourceId: MerchantSourceId }) =>
      ingestMerchantSource(file, merchantSourceId),
  })
}
