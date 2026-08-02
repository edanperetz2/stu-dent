import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  acceptAppointment,
  approveAppointment,
  cancelAppointment,
  completeAppointment,
  createAppointment,
  getAppointment,
  listAppointments,
  markNoShow,
  rejectAppointment,
  updateAppointment,
} from './appointments'

describe('appointments api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listAppointments requests GET /appointments with only the given options as query params', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listAppointments('tok', { excludeCancelled: true, limit: 50 })

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/appointments?')
    expect(call.url).toContain('exclude_cancelled=true')
    expect(call.url).toContain('limit=50')
    expect(call.url).not.toContain('start_after')
  })

  it('getAppointment requests GET /appointments/:id', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await getAppointment('tok', 'appt-1')
    expect(lastFetchCall(fetchMock).url).toContain('/appointments/appt-1')
  })

  it('createAppointment requests POST /appointments with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    const payload = { start_time: '2026-01-01T09:00:00Z', end_time: '2026-01-01T10:00:00Z' }
    await createAppointment('tok', payload)
    const call = lastFetchCall(fetchMock)
    expect(call.method).toBe('POST')
    expect(call.body).toEqual(payload)
  })

  it('updateAppointment requests PATCH /appointments/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updateAppointment('tok', 'appt-1', { notes: 'updated' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/appointments/appt-1')
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ notes: 'updated' })
  })

  it('acceptAppointment requests POST /appointments/:id/accept, including room_id only when given', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await acceptAppointment('tok', 'appt-1')
    let call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/appointments/appt-1/accept')
    expect(call.body).toBeUndefined()

    await acceptAppointment('tok', 'appt-1', 'room-1')
    call = lastFetchCall(fetchMock)
    expect(call.body).toEqual({ room_id: 'room-1' })
  })

  it.each([
    ['approve', approveAppointment],
    ['reject', rejectAppointment],
    ['cancel', cancelAppointment],
    ['complete', completeAppointment],
    ['no-show', markNoShow],
  ] as const)('%s action requests POST /appointments/:id/%s', async (actionName, actionFn) => {
    const fetchMock = mockFetchOnce(200, {})
    await actionFn('tok', 'appt-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain(`/appointments/appt-1/${actionName}`)
    expect(call.method).toBe('POST')
  })
})
