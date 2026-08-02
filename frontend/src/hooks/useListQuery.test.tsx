import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { useListQuery } from './useListQuery'

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useListQuery', () => {
  it('reports the error branch, not empty, on a rejected query', async () => {
    const { result } = renderHook(
      () =>
        useListQuery({
          queryKey: ['test-error'],
          queryFn: () => Promise.reject(new Error('boom')),
          errorFallback: 'Failed to load.',
        }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.status === 'error' && result.current.message).toBe('Failed to load.')
  })

  it('reports empty for a resolved empty array by default', async () => {
    const { result } = renderHook(
      () =>
        useListQuery({
          queryKey: ['test-empty'],
          queryFn: () => Promise.resolve([]),
          errorFallback: 'Failed to load.',
        }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.status).toBe('empty'))
  })

  it('reports ready with the resolved data for a non-empty result', async () => {
    const { result } = renderHook(
      () =>
        useListQuery({
          queryKey: ['test-ready'],
          queryFn: () => Promise.resolve([1, 2, 3]),
          errorFallback: 'Failed to load.',
        }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.status === 'ready' && result.current.data).toEqual([1, 2, 3])
  })

  it('keeps showing the last-good data, not the error screen, when a background refetch fails', async () => {
    // Regression test: TanStack Query keeps a query's last-successful
    // `data` populated across a *background* refetch failure (only a
    // query that has never once succeeded has `data === undefined`) --
    // this hook used to check `isError` before `data`, so an ordinary
    // transient refetch failure (tab-switch-back, a brief network blip)
    // discarded already-loaded, still-valid rows and showed the full
    // error/"Try again" screen instead.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    function localWrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    }

    let callCount = 0
    const { result } = renderHook(
      () =>
        useListQuery({
          queryKey: ['test-refetch-failure'],
          queryFn: () => {
            callCount += 1
            if (callCount === 1) return Promise.resolve([1, 2, 3])
            return Promise.reject(new Error('transient failure'))
          },
          errorFallback: 'Failed to load.',
        }),
      { wrapper: localWrapper },
    )

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.status === 'ready' && result.current.data).toEqual([1, 2, 3])

    await queryClient.refetchQueries({ queryKey: ['test-refetch-failure'] }).catch(() => {})

    // Waited for (not a bare synchronous check): the query's internal
    // isError flip and this hook's re-render both happen after
    // refetchQueries's own promise resolves, so asserting immediately
    // could observe a stale pre-refetch render and pass for the wrong
    // reason even on the old, buggy branch order.
    await waitFor(() => expect(queryClient.getQueryState(['test-refetch-failure'])?.status).toBe('error'))
    expect(result.current.status).toBe('ready')
    expect(result.current.status === 'ready' && result.current.data).toEqual([1, 2, 3])
  })

  it('never reports empty when isEmpty is overridden to false, even for an empty array', async () => {
    const { result } = renderHook(
      () =>
        useListQuery({
          queryKey: ['test-no-empty'],
          queryFn: () => Promise.resolve([]),
          errorFallback: 'Failed to load.',
          isEmpty: () => false,
        }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.status).toBe('ready'))
  })
})
