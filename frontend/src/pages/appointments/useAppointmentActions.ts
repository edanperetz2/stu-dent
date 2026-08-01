import type { UseFormReturnType } from '@mantine/form'
import { useState } from 'react'
import {
  createAppointment,
  type AppointmentCreateInput,
} from '../../api/appointments'
import { ApiError } from '../../api/httpClient'
import { interpretSchedulingRequest } from '../../api/schedulingAssistant'
import type { ConflictReason } from '../../api/types'
import { joinWaitlist } from '../../api/waitlist'
import { useMutationWithToast } from '../../hooks/useMutationWithToast'
import { isoToMantineDateTime } from '../../utils/dates'

export interface CreateFormValues {
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  // DateTimePicker value format -- see src/utils/dates.ts
  start_time: string | null
  end_time: string | null
  notes: string
}

interface UseAppointmentActionsParams {
  token: string
  form: UseFormReturnType<CreateFormValues>
  /** Called after a successful create *or* a successful join-waitlist --
   * the create-appointment modal's own close/open state lives with the
   * caller (it also needs to open the modal, which this hook has no
   * reason to know about). */
  onSubmitSuccess: () => void
  /** Called after a successful interpret applies its start/end times to the
   * form -- lets the caller switch its duration-chip state to "Custom" so
   * the interpreted end time isn't silently overwritten by a stale preset
   * the next time start_time changes. Optional: only the rebuilt New
   * Appointment modal needs this, not any other future caller. */
  onInterpretApplied?: () => void
}

/** The create/interpret/join-waitlist mutation cluster for the New
 * Appointment modal, extracted out of AppointmentsListPage so that page
 * only has to render, not also own this much mutation/state logic. Built
 * on useMutationWithToast (see hooks/useMutationWithToast.ts) except for
 * createMutation's onError, which keeps a bespoke branch: a 409 with a
 * structured conflict list opens the ConflictResolutionModal instead of
 * showing the default error toast. */
export function useAppointmentActions({
  token,
  form,
  onSubmitSuccess,
  onInterpretApplied,
}: UseAppointmentActionsParams) {
  const [describeText, setDescribeText] = useState('')
  const [interpretWarnings, setInterpretWarnings] = useState<string[]>([])
  const [conflictState, setConflictState] = useState<{
    payload: AppointmentCreateInput
    conflicts: ConflictReason[]
  } | null>(null)

  function resetInterpretState() {
    setDescribeText('')
    setInterpretWarnings([])
  }

  const createMutation = useMutationWithToast({
    mutationFn: (payload: AppointmentCreateInput) => createAppointment(token, payload),
    invalidateKeys: [['appointments']],
    successMessage: 'Appointment requested',
    errorFallback: 'Failed to create appointment',
    onSuccess: () => {
      form.reset()
      resetInterpretState()
      onSubmitSuccess()
    },
    onError: (err, payload) => {
      if (err instanceof ApiError && err.status === 409 && err.conflicts?.length) {
        setConflictState({ payload, conflicts: err.conflicts })
        return true
      }
      return false
    },
  })

  const joinWaitlistMutation = useMutationWithToast({
    mutationFn: (payload: AppointmentCreateInput) => joinWaitlist(token, payload),
    invalidateKeys: [['waitlist']],
    successMessage: 'Added to the waitlist',
    errorFallback: 'Failed to join the waitlist',
    onSuccess: () => {
      setConflictState(null)
      form.reset()
      resetInterpretState()
      onSubmitSuccess()
    },
  })

  const interpretMutation = useMutationWithToast({
    mutationFn: (text: string) => interpretSchedulingRequest(token, text),
    invalidateKeys: [],
    errorFallback: 'Failed to interpret request',
    onSuccess: (data) => {
      form.setValues({
        ...(data.patient_id && { patient_id: data.patient_id }),
        ...(data.attending_id && { attending_id: data.attending_id }),
        ...(data.room_id && { room_id: data.room_id }),
        ...(data.equipment_id && { equipment_id: data.equipment_id }),
        ...(data.start_time && { start_time: isoToMantineDateTime(data.start_time) }),
        ...(data.end_time && { end_time: isoToMantineDateTime(data.end_time) }),
        ...(data.notes && { notes: data.notes }),
      })
      setInterpretWarnings(data.warnings)
      onInterpretApplied?.()
    },
  })

  return {
    describeText,
    setDescribeText,
    interpretWarnings,
    resetInterpretState,
    conflictState,
    setConflictState,
    createMutation,
    joinWaitlistMutation,
    interpretMutation,
  }
}
