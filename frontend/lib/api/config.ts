/**
 * Backend base URL. Configurable via NEXT_PUBLIC_API_BASE_URL — see
 * frontend/README.md. Falls back to the FastAPI default dev port so local
 * development works with zero configuration.
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, '') || 'http://localhost:8000'
