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
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey, queryFn, enabled })
  const retry = () => {
    void refetch()
  }

  if (isError) return { status: 'error', message: apiErrorMessage(error, errorFallback), retry }
  if (isLoading) return { status: 'loading' }
  if (data !== undefined && isEmpty(data)) return { status: 'empty' }
  return { status: 'ready', data: data as TQueryFnData }
}
