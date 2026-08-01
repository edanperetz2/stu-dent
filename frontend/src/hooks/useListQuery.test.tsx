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
