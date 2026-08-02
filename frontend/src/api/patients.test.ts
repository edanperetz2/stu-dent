import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { confirmPatient, createPatient, deletePatient, getPatient, listPatients, updatePatient } from './patients'

describe('patients api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listPatients requests GET /patients', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listPatients('tok')
    expect(lastFetchCall(fetchMock).url).toMatch(/\/patients$/)
  })

  it('getPatient requests GET /patients/:id', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await getPatient('tok', 'patient-1')
    expect(lastFetchCall(fetchMock).url).toContain('/patients/patient-1')
  })

  it('createPatient requests POST /patients with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    const payload = { full_name: 'Pat Ient', email: 'pat@example.com', password: 'password123' }
    await createPatient('tok', payload)
    const call = lastFetchCall(fetchMock)
    expect(call.url).toMatch(/\/patients$/)
    expect(call.method).toBe('POST')
    expect(call.body).toEqual(payload)
  })

  it('updatePatient requests PATCH /patients/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updatePatient('tok', 'patient-1', { full_name: 'New Name' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/patients/patient-1')
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ full_name: 'New Name' })
  })

  it('deletePatient requests DELETE /patients/:id', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await deletePatient('tok', 'patient-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/patients/patient-1')
    expect(call.method).toBe('DELETE')
  })

  it('confirmPatient requests POST /patients/:id/confirm', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await confirmPatient('tok', 'patient-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/patients/patient-1/confirm')
    expect(call.method).toBe('POST')
  })
})
