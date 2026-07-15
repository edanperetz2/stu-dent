import { request } from './httpClient'
import type { Feedback, PendingFeedback } from './types'

export interface FeedbackCreateInput {
  went_well: string
  could_improve: string
  additional_comments: string | null
}

export function listPendingFeedback(token: string) {
  return request<PendingFeedback[]>('/feedback/pending', { token })
}

export function listFeedbackGiven(token: string) {
  return request<Feedback[]>('/feedback/given', { token })
}

export function listFeedbackReceived(token: string) {
  return request<Feedback[]>('/feedback/received', { token })
}

export function submitFeedback(token: string, appointmentId: string, payload: FeedbackCreateInput) {
  return request<Feedback>(`/appointments/${appointmentId}/feedback`, {
    method: 'POST',
    body: payload,
    token,
  })
}
