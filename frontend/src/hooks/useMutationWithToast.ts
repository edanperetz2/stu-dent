import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { apiErrorMessage } from '../api/httpClient'

interface UseMutationWithToastOptions<TData, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData>
  /** Query keys invalidated on success -- covers the common case of one
   * mutation feeding one or more list views. */
  invalidateKeys: QueryKey[]
  /** Omit to keep the mutation silent on success (e.g. a mark-read toggle) --
   * several call sites intentionally don't toast on every success today. */
  successMessage?: string
  errorFallback: string
  onSuccess?: (data: TData, variables: TVariables) => void
  /** Return `true` to signal the error was already handled (e.g. a
   * scheduling-conflict 409 that opens a resolution modal instead of a
   * toast) and skip the default error toast. */
  onError?: (err: unknown, variables: TVariables) => boolean | void
}

/** The onSuccess-invalidate-and-toast / onError-toast triad written out by
 * hand across every page's useMutation calls, deduped into one place -- see
 * docs/stu-dent-review.html's P0-1 finding: a fix like the isError handling
 * below only reaches every page if there's one place to make it. */
export function useMutationWithToast<TData, TVariables>({
  mutationFn,
  invalidateKeys,
  successMessage,
  errorFallback,
  onSuccess,
  onError,
}: UseMutationWithToastOptions<TData, TVariables>) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn,
    onSuccess: (data, variables) => {
      for (const queryKey of invalidateKeys) {
        queryClient.invalidateQueries({ queryKey })
      }
      if (successMessage) {
        notifications.show({ message: successMessage, color: 'green' })
      }
      onSuccess?.(data, variables)
    },
    onError: (err, variables) => {
      const handled = onError?.(err, variables)
      if (!handled) {
        notifications.show({ message: apiErrorMessage(err, errorFallback), color: 'red' })
      }
    },
  })
}
