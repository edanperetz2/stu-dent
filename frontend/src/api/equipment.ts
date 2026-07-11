import { request } from './httpClient'
import type { Equipment } from './types'

export interface EquipmentCreateInput {
  name: string
  equipment_type?: string | null
}

export interface EquipmentUpdateInput {
  name?: string
  equipment_type?: string | null
  is_active?: boolean
}

export function listActiveEquipment(token: string) {
  return request<Equipment[]>('/equipment', { token })
}

export function listAllEquipment(token: string) {
  return request<Equipment[]>('/admin/equipment', { token })
}

export function createEquipment(token: string, payload: EquipmentCreateInput) {
  return request<Equipment>('/admin/equipment', { method: 'POST', body: payload, token })
}

export function updateEquipment(token: string, equipmentId: string, payload: EquipmentUpdateInput) {
  return request<Equipment>(`/admin/equipment/${equipmentId}`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}
