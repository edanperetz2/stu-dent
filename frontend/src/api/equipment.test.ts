import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { createEquipment, listActiveEquipment, listAllEquipment, updateEquipment } from './equipment'

describe('equipment api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listActiveEquipment requests GET /equipment', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listActiveEquipment('tok')
    expect(lastFetchCall(fetchMock).url).toMatch(/\/equipment$/)
  })

  it('listAllEquipment requests GET /admin/equipment', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listAllEquipment('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/admin/equipment')
  })

  it('createEquipment requests POST /admin/equipment with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await createEquipment('tok', { name: 'Scanner', equipment_type: 'imaging' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/equipment')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ name: 'Scanner', equipment_type: 'imaging' })
  })

  it('updateEquipment requests PATCH /admin/equipment/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updateEquipment('tok', 'eq-1', { is_active: false })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/equipment/eq-1')
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ is_active: false })
  })
})
