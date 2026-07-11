export type Role = 'student' | 'attending' | 'admin'

export type PrincipalType = 'user' | 'patient'

export type AppointmentStatus =
  | 'proposed'
  | 'awaiting_confirmation'
  | 'confirmed'
  | 'cancelled'
  | 'completed'
  | 'no_show'
  | 'rescheduling_requested'

export type WaitlistStatus = 'active' | 'notified' | 'cancelled'

export type NotificationType =
  | 'appointment_reminder'
  | 'appointment_expired'
  | 'waitlist_slot_available'

export type PreferredTimeOfDay = 'morning' | 'afternoon' | 'evening'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
}

export interface Patient {
  id: string
  owner_student_id: string
  full_name: string
  contact_phone: string | null
  email: string | null
  is_active: boolean
  preferred_time_of_day: PreferredTimeOfDay | null
}

export interface Room {
  id: string
  name: string
  is_active: boolean
}

export interface Equipment {
  id: string
  name: string
  equipment_type: string | null
  is_active: boolean
}

export interface Appointment {
  id: string
  student_id: string
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  start_time: string
  end_time: string
  status: AppointmentStatus
  student_confirmed_at: string | null
  attending_approved_at: string | null
  notes: string | null
}

export interface AvailabilityWindow {
  id: string
  day_of_week: number
  start_time: string
  end_time: string
}

export interface Notification {
  id: string
  notification_type: NotificationType
  message: string
  related_appointment_id: string | null
  read_at: string | null
  created_at: string
}

export interface WaitlistEntry {
  id: string
  student_id: string
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  start_time: string
  end_time: string
  status: WaitlistStatus
  notified_at: string | null
}

export interface ForumPost {
  id: string
  author_student_id: string
  title: string
  body: string
  score: number
  created_at: string
  updated_at: string
}

export interface ForumComment {
  id: string
  post_id: string
  author_student_id: string
  body: string
  score: number
  created_at: string
  updated_at: string
}

export interface DirectMessage {
  id: string
  patient_id: string
  sender_user_id: string | null
  sender_patient_id: string | null
  body: string
  read_at: string | null
  created_at: string
}

export interface AuditLogEntry {
  id: number
  actor_user_id: string | null
  actor_patient_id: string | null
  attempted_identifier: string | null
  action: string
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  extra_data: Record<string, unknown> | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface RealtimeEvent {
  event: 'notification' | 'direct_message'
  kind: PrincipalType
  recipient_id: string
  [key: string]: unknown
}
