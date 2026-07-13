import { request } from './httpClient'
import type { Room } from './types'

export interface RoomCreateInput {
  name: string
}

export interface RoomUpdateInput {
  name?: string
  is_active?: boolean
  inactive_until?: string | null
}

export function listActiveRooms(token: string) {
  return request<Room[]>('/rooms', { token })
}

export function listAllRooms(token: string) {
  return request<Room[]>('/admin/rooms', { token })
}

export function createRoom(token: string, payload: RoomCreateInput) {
  return request<Room>('/admin/rooms', { method: 'POST', body: payload, token })
}

export function updateRoom(token: string, roomId: string, payload: RoomUpdateInput) {
  return request<Room>(`/admin/rooms/${roomId}`, { method: 'PATCH', body: payload, token })
}
