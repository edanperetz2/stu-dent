import { request } from './httpClient'
import type { Contact, GroupSummary, Message } from './types'

/** Discriminates which of the three messaging surfaces a call targets --
 * a peer-to-peer thread, the shared admin inbox (self for a non-admin
 * caller, or a specific user's thread when an admin is browsing it), or a
 * group conversation -- so the handful of list/send/read operations below
 * can share one implementation instead of three near-identical copies. */
export type MessageTarget =
  | { kind: 'direct'; otherUserId: string }
  | { kind: 'admin'; ownerId?: string }
  | { kind: 'group'; conversationId: string }

function targetPath(target: MessageTarget): string {
  switch (target.kind) {
    case 'direct':
      return `/messages/direct/${target.otherUserId}`
    case 'admin':
      return target.ownerId ? `/messages/admin-inbox/${target.ownerId}` : '/messages/admin'
    case 'group':
      return `/messages/groups/${target.conversationId}`
  }
}

export function targetKey(target: MessageTarget): string {
  switch (target.kind) {
    case 'direct':
      return `direct:${target.otherUserId}`
    case 'admin':
      return `admin:${target.ownerId ?? 'self'}`
    case 'group':
      return `group:${target.conversationId}`
  }
}

export function listContacts(token: string) {
  return request<Contact[]>('/messages/contacts', { token })
}

export function listGroups(token: string) {
  return request<GroupSummary[]>('/messages/groups', { token })
}

export function createGroup(token: string, title: string, participantIds: string[]) {
  return request<GroupSummary>('/messages/groups', {
    method: 'POST',
    body: { title, participant_ids: participantIds },
    token,
  })
}

export function listMessages(token: string, target: MessageTarget) {
  return request<Message[]>(targetPath(target), { token })
}

export function sendMessage(token: string, target: MessageTarget, body: string) {
  return request<Message>(targetPath(target), { method: 'POST', body: { body }, token })
}

export function markRead(token: string, target: MessageTarget) {
  return request<{ last_read_at: string }>(`${targetPath(target)}/read`, {
    method: 'POST',
    token,
  })
}
