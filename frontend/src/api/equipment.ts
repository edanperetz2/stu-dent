import { request } from './httpClient'
import type { Equipment } from './types'

export function listActiveEquipment(token: string) {
  return request<Equipment[]>('/equipment', { token })
}
