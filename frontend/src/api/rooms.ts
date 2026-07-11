import { request } from './httpClient'
import type { Room } from './types'

export function listActiveRooms(token: string) {
  return request<Room[]>('/rooms', { token })
}
