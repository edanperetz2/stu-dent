import { request } from './httpClient'
import type { StudentPublic } from './types'

/** Public, unauthenticated -- used by the registration form's "choose your
 * student" picker, which runs before any token exists. */
export function listStudents() {
  return request<StudentPublic[]>('/students')
}
