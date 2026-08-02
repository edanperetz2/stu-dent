import { useQuery, type QueryKey } from '@tanstack/react-query'
import { apiErrorMessage } from '../api/httpClient'

export type ListQueryResult<TData> =
  | { status: 'loading' }
  | { status: 'error'; message: string; retry: () => void }
  | { status: 'empty' }
  | { status: 'ready'; data: TData }

interface UseListQueryOptions<TQueryFnData> {
  queryKey: QueryKey
  queryFn: () => Promise<TQueryFnData>
  errorFallback: string
  enabled?: boolean
  /** Defaults to "an empty array" -- pass `() => false` for a page (like
   * AppointmentsListPage) whose content branches already render their own
   * empty state, or for a single-object query (PreferencesPage) where
   * "empty" isn't a real state to begin with. */
  isEmpty?: (data: TQueryFnData) => boolean
}

/**
 * Wraps useQuery's loading/isError/data trio -- hand-copied identically
 * across a dozen pages, with the error branch missing on 11 of them until
 * it was added by hand one page at a time -- into one discriminated union a
 * page switches over instead. The guardrail this buys isn't a lint rule,
 * it's the TypeScript compiler: `result.data` only type-checks inside the
 * `status === 'ready'` branch, so a page can't reach the list while
 * silently skipping the possibility that the request failed, the way the
 * old `isLoading ? ... : data?.length === 0 ? ... : ...` ternary could
 * (and did, before that fix) by never checking `isError` at all.
 */
export function useListQuery<TQueryFnData>({
  queryKey,
  queryFn,
  errorFallback,
  enabled,
  isEmpty = (data) => Array.isArray(data) && data.length === 0,
}: UseListQueryOptions<TQueryFnData>): ListQueryResult<TQueryFnData> {
  const { data, isError, error, refetch } = useQuery({ queryKey, queryFn, enabled })
  const retry = () => {
    void refetch()
  }

  // `data` checked before `isError`: TanStack Query keeps the last
  // successful result in place across a *background* refetch failure
  // (isError flips true, data stays populated) -- only a query that has
  // never once succeeded has `data === undefined`. Checking isError first
  // used to throw away already-loaded, still-valid rows and show the full
  // error/"Try again" screen on any transient refetch failure (a tab
  // switch, a brief network blip, a backend restart), not just a genuine
  // first-load failure.
  if (data !== undefined) {
    if (isEmpty(data)) return { status: 'empty' }
    return { status: 'ready', data }
  }
  if (isError) return { status: 'error', message: apiErrorMessage(error, errorFallback), retry }
  return { status: 'loading' }
}
