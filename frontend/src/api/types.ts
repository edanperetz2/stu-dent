export type Role = 'student' | 'attending' | 'admin' | 'patient'

export type AppointmentStatus =
  | 'proposed'
  | 'awaiting_confirmation'
  | 'confirmed'
  | 'cancelled'
  | 'completed'
  | 'no_show'
  | 'rescheduling_requested'

export type WaitlistStatus = 'active' | 'booked' | 'cancelled'

export type ConflictResourceType = 'student' | 'patient' | 'attending' | 'room' | 'equipment'

export interface ConflictReason {
  resource_type: ConflictResourceType
  resource_id: string
  resource_name: string
}

export type NotificationType =
  | 'appointment_reminder'
  | 'appointment_expired'
  | 'waitlist_slot_available'
  | 'patient_registration_request'
  | 'resource_deactivated'
  | 'appointment_needs_resolution'
  | 'feedback_reminder'
  | 'appointment_created'
  | 'appointment_status_changed'

export type PreferredTimeOfDay = 'morning' | 'afternoon' | 'evening'

export type ReportPeriodType = 'weekly' | 'monthly' | 'ad_hoc'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  // Meaningful only when role === 'patient'; null for student/attending/admin.
  owner_student_id: string | null
  // Resolved server-side from owner_student_id; only populated by GET/PATCH /users/me.
  owner_student_name: string | null
  owner_confirmed_at: string | null
  contact_phone: string | null
  preferred_time_of_day: PreferredTimeOfDay | null
}

export interface StudentPublic {
  id: string
  full_name: string
}

export interface Room {
  id: string
  name: string
  is_active: boolean
  inactive_until: string | null
}

export interface Equipment {
  id: string
  name: string
  equipment_type: string | null
  is_active: boolean
  inactive_until: string | null
}

// One busy window for a room or equipment item, from GET /resources/schedule --
// reveals which student booked it (for coordination) but deliberately nothing
// else about the appointment, see the backend schema's docstring.
export interface ResourceBooking {
  resource_kind: 'room' | 'equipment'
  resource_id: string
  resource_name: string
  start_time: string
  end_time: string
  student_name: string
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
  student_name: string
  patient_name: string
  attending_name: string | null
  room_name: string | null
  equipment_name: string | null
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
  notes: string | null
  status: WaitlistStatus
  resolved_at: string | null
  resulting_appointment_id: string | null
  // The resulting appointment's status keeps progressing after promotion
  // (e.g. awaiting_confirmation -> confirmed), so this is resolved fresh
  // server-side on every read rather than frozen at promotion time.
  resulting_appointment_status: AppointmentStatus | null
  conflicts: ConflictReason[]
  student_name: string
  patient_name: string
  attending_name: string | null
  room_name: string | null
  equipment_name: string | null
}

export type FeedbackAuthorRole = 'patient' | 'attending'

export interface Feedback {
  id: string
  appointment_id: string
  student_id: string
  author_id: string
  author_role: FeedbackAuthorRole
  went_well: string
  could_improve: string
  additional_comments: string | null
  created_at: string
  student_name: string
  author_name: string
  patient_id: string
  patient_name: string
  appointment_start_time: string
}

export interface PendingFeedback {
  appointment_id: string
  appointment_start_time: string
  student_id: string
  student_name: string
  patient_id: string
  patient_name: string
}

export interface ForumPost {
  id: string
  author_student_id: string
  title: string
  body: string
  likes: number
  dislikes: number
  comment_count: number
  my_vote: 1 | -1 | null
  created_at: string
  updated_at: string
}

export interface ForumComment {
  id: string
  post_id: string
  author_student_id: string
  body: string
  likes: number
  dislikes: number
  my_vote: 1 | -1 | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  sender_id: string
  sender_name: string
  body: string
  created_at: string
}

export interface Contact {
  id: string
  full_name: string
  role: Role
}

export interface GroupSummary {
  id: string
  title: string
  participant_ids: string[]
  participant_names: string[]
}

export interface AuditLogEntry {
  id: number
  actor_id: string | null
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

export interface Report {
  id: string
  period_type: ReportPeriodType
  period_start: string
  period_end: string
  question: string | null
  title: string
  content: string
  created_at: string
}

export interface RealtimeEvent {
  event: 'notification' | 'message' | 'connected'
  recipient_id?: string
  [key: string]: unknown
}
