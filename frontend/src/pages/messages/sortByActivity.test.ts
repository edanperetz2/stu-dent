import { describe, expect, it } from 'vitest'
import type { ThreadSummary } from '../../api/messages'
import { sortByActivity } from './MessagesPage'

function summaryMap(entries: ThreadSummary[]): Map<string, ThreadSummary> {
  return new Map(entries.map((s) => [s.target_key, s]))
}

describe('sortByActivity', () => {
  it('puts unread threads before read ones regardless of recency', () => {
    const items = [
      { target: { kind: 'direct' as const, otherUserId: 'a' }, label: 'Alice' },
      { target: { kind: 'direct' as const, otherUserId: 'b' }, label: 'Bob' },
    ]
    const summaries = summaryMap([
      { target_key: 'direct:a', last_message_at: '2026-01-05T00:00:00Z', has_unread: false },
      { target_key: 'direct:b', last_message_at: '2026-01-01T00:00:00Z', has_unread: true },
    ])

    const sorted = sortByActivity(items, summaries)
    expect(sorted.map((i) => i.label)).toEqual(['Bob', 'Alice'])
  })

  it('sorts same-unread-status threads by most-recent activity first', () => {
    const items = [
      { target: { kind: 'direct' as const, otherUserId: 'a' }, label: 'Older' },
      { target: { kind: 'direct' as const, otherUserId: 'b' }, label: 'Newer' },
    ]
    const summaries = summaryMap([
      { target_key: 'direct:a', last_message_at: '2026-01-01T00:00:00Z', has_unread: false },
      { target_key: 'direct:b', last_message_at: '2026-01-10T00:00:00Z', has_unread: false },
    ])

    const sorted = sortByActivity(items, summaries)
    expect(sorted.map((i) => i.label)).toEqual(['Newer', 'Older'])
  })

  it('sorts threads with no activity yet last, alphabetically among themselves', () => {
    const items = [
      { target: { kind: 'direct' as const, otherUserId: 'a' }, label: 'Zoe' },
      { target: { kind: 'direct' as const, otherUserId: 'b' }, label: 'Amy' },
      { target: { kind: 'direct' as const, otherUserId: 'c' }, label: 'Has Activity' },
    ]
    const summaries = summaryMap([
      { target_key: 'direct:c', last_message_at: '2026-01-01T00:00:00Z', has_unread: false },
    ])

    const sorted = sortByActivity(items, summaries)
    expect(sorted.map((i) => i.label)).toEqual(['Has Activity', 'Amy', 'Zoe'])
  })

  it('does not mutate the input array', () => {
    const items = [
      { target: { kind: 'direct' as const, otherUserId: 'a' }, label: 'B' },
      { target: { kind: 'direct' as const, otherUserId: 'b' }, label: 'A' },
    ]
    const original = [...items]
    sortByActivity(items, new Map())
    expect(items).toEqual(original)
  })
})
