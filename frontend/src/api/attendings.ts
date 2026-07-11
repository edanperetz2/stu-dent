import { request } from './httpClient'
import type { User } from './types'

export function listAttendings(token: string) {
  return request<User[]>('/attendings', { token })
}
