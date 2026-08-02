import { notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/httpClient'
import { useMutationWithToast } from './useMutationWithToast'

vi.mock('@mantine/notifications', () => ({ notifications: { show: vi.fn() } }))

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return { wrapper, invalidateSpy }
}

describe('useMutationWithToast', () => {
  beforeEach(() => {
    vi.mocked(notifications.show).mockClear()
  })

  it('on success: invalidates every given query key and shows the success toast', async () => {
    const { wrapper, invalidateSpy } = makeWrapper()
    const { result } = renderHook(
      () =>
        useMutationWithToast({
          mutationFn: () => Promise.resolve('ok'),
          invalidateKeys: [['appointments'], ['waitlist']],
          successMessage: 'Saved',
          errorFallback: 'Failed',
        }),
      { wrapper },
    )

    act(() => {
      result.current.mutate(undefined)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['appointments'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['waitlist'] })
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Saved', color: 'green' }),
    )
  })

  it('stays silent on success when no successMessage is given', async () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(
      () =>
        useMutationWithToast({
          mutationFn: () => Promise.resolve('ok'),
          invalidateKeys: [],
          errorFallback: 'Failed',
        }),
      { wrapper },
    )

    act(() => {
      result.current.mutate(undefined)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(notifications.show).not.toHaveBeenCalled()
  })

  it('on error: shows the API error message (falling back when not an ApiError)', async () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(
      () =>
        useMutationWithToast({
          mutationFn: () => Promise.reject(new ApiError(409, 'Conflict detected')),
          invalidateKeys: [],
          errorFallback: 'Failed to save',
        }),
      { wrapper },
    )

    act(() => {
      result.current.mutate(undefined)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(notifications.show).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Conflict detected', color: 'red' }),
    )
  })

  it("skips the default error toast when the caller's onError reports it already handled the error", async () => {
    const { wrapper } = makeWrapper()
    const onError = vi.fn().mockReturnValue(true)
    const { result } = renderHook(
      () =>
        useMutationWithToast({
          mutationFn: () => Promise.reject(new Error('boom')),
          invalidateKeys: [],
          errorFallback: 'Failed',
          onError,
        }),
      { wrapper },
    )

    act(() => {
      result.current.mutate(undefined)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(onError).toHaveBeenCalled()
    expect(notifications.show).not.toHaveBeenCalled()
  })
})
