import { Button, Group, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { apiErrorMessage } from '../api/httpClient'

let toastCounter = 0

/** A dismissible, auto-closing notification with an "Undo" action -- for
 * reversible actions that don't need an interrupting confirm modal (the
 * action just happens immediately; the toast is the safety net). Only
 * use this where the underlying action has no side effects that would
 * make a delayed undo unsafe. Deactivating a user or cancelling a
 * waitlist entry both qualify (pure status flips, nothing else reacts to
 * them) -- appointment cancel/reject deliberately does NOT use this,
 * since cancelling can synchronously auto-promote a *different* waitlist
 * entry into a real booking, and a later "undo" could then collide with
 * that new appointment. */
export function showUndoToast({
  message,
  onUndo,
  undoLabel = 'Undo',
}: {
  message: string
  // May return a promise -- callers that fire the original action via
  // mutateAsync and awaits it here before re-mutating, so a fast Undo
  // click can't race the original request (both hitting the server
  // concurrently, with the *later-resolving response* winning the
  // displayed state rather than the later *click*). The toast itself
  // still closes immediately on click; only the actual undo work waits.
  onUndo: () => void | Promise<void>
  undoLabel?: string
}) {
  const id = `undo-toast-${++toastCounter}`
  notifications.show({
    id,
    color: 'blue',
    autoClose: 6000,
    message: (
      <Group justify="space-between" wrap="nowrap" gap="sm">
        <Text size="sm">{message}</Text>
        <Button
          size="compact-xs"
          variant="light"
          onClick={() => {
            // Normalizes both a plain `void` onUndo and a real Promise into
            // one chain -- a rejecting onUndo (a real caller today all
            // happen to avoid this, but the primitive itself had no
            // defensive catch) would otherwise be a silent unhandled
            // rejection with no user-facing feedback at all.
            Promise.resolve(onUndo()).catch((err: unknown) => {
              notifications.show({
                message: apiErrorMessage(err, 'Undo failed'),
                color: 'red',
              })
            })
            notifications.hide(id)
          }}
        >
          {undoLabel}
        </Button>
      </Group>
    ),
  })
}
