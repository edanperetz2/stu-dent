import type { ConflictReason } from './types'

// Inlined by Vite at build time -- changing this env var after the image
// is built has no effect; a new image must be built.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  // Present only on a scheduling-conflict 409 -- a plain sibling of the
  // string `detail`, populated below when the backend includes it.
  conflicts?: ConflictReason[]

  constructor(status: number, message: string, conflicts?: ConflictReason[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.conflicts = conflicts
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

interface RequestOptions {
  method?: HttpMethod
  body?: unknown
  token?: string | null
  query?: Record<string, string | number | boolean | undefined>
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(`${API_BASE_URL}${path}`)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, query } = options

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    let detail = response.statusText
    let conflicts: ConflictReason[] | undefined
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') {
        detail = data.detail
      } else if (Array.isArray(data.detail)) {
        // FastAPI/Pydantic 422 validation errors return `detail` as a list
        // of {loc, msg} objects, not a string -- without this branch every
        // validation error silently fell back to a generic status text
        // like "Unprocessable Entity" instead of the actual message.
        detail = data.detail
          .map((item: { msg?: string; loc?: (string | number)[] }) => {
            const field = item.loc?.[item.loc.length - 1]
            return field && item.msg ? `${field}: ${item.msg}` : item.msg
          })
          .filter(Boolean)
          .join('; ')
      }
      if (Array.isArray(data.conflicts)) {
        conflicts = data.conflicts
      }
    } catch {
      // response body wasn't JSON; keep statusText
    }
    throw new ApiError(response.status, detail, conflicts)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

/** The `err instanceof ApiError ? err.message : fallback` ternary, deduped
 * -- repeated identically across every page's mutation onError handler. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}
