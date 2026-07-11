import { request } from './httpClient'
import type { Report } from './types'

export function listReports(token: string) {
  return request<Report[]>('/reports', { token })
}

export function generateReport(token: string) {
  return request<Report[]>('/reports/generate', { method: 'POST', token })
}

export function askQuestion(token: string, question: string) {
  return request<Report>('/reports/ask', { method: 'POST', body: { question }, token })
}
