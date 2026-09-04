import { API_BASE_URL } from './config'

/**
 * Thrown for any non-2xx response. Carries the HTTP status and whatever
 * message the backend supplied so callers/UI can distinguish "not found"
 * (404) from other failures without re-parsing the response body.
 */
export class ApiError extends Error {
  readonly status: number
  readonly url: string

  constructor(status: number, message: string, url: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
  }

  get isNotFound(): boolean {
    return this.status === 404
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const { detail } = body as { detail?: unknown }

    if (typeof detail === 'string') return detail

    // FastAPI's default request-validation errors return detail as a list
    // of {loc, msg, type} objects rather than a string.
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : JSON.stringify(item)))
        .join('; ')
    }

    return response.statusText || `Request failed with status ${response.status}`
  } catch {
    return response.statusText || `Request failed with status ${response.status}`
  }
}

async function handleResponse<T>(response: Response, url: string): Promise<T> {
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response), url)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export interface RequestOptions {
  signal?: AbortSignal
}

/** GET request. Returns parsed JSON, typed as T. */
export async function apiGet<T>(path: string, options?: RequestOptions): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal: options?.signal,
  })

  return handleResponse<T>(response, url)
}

/** POST request with a JSON body. */
export async function apiPostJson<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
    signal: options?.signal,
  })

  return handleResponse<T>(response, url)
}

/** POST request with a multipart/form-data body (file uploads). */
export async function apiPostForm<T>(path: string, form: FormData, options?: RequestOptions): Promise<T> {
  const url = `${API_BASE_URL}${path}`

  // Deliberately no Content-Type header: the browser sets the multipart
  // boundary itself. Setting it manually breaks the boundary parameter.
  const response = await fetch(url, {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body: form,
    signal: options?.signal,
  })

  return handleResponse<T>(response, url)
}
