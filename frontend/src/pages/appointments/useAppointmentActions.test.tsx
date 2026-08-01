import { MantineProvider } from '@mantine/core'
import { useForm } from '@mantine/form'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as appointmentsApi from '../../api/appointments'
import { ApiError } from '../../api/httpClient'
import * as schedulingAssistantApi from '../../api/schedulingAssistant'
import * as waitlistApi from '../../api/waitlist'
import { useAppointmentActions, type CreateFormValues } from './useAppointmentActions'

vi.mock('../../api/appointments')
vi.mock('../../api/waitlist')
vi.mock('../../api/schedulingAssistant')

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <MantineProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MantineProvider>
  )
}

function useHarness(onSubmitSuccess: () => void, onInterpretApplied?: () => void) {
  const form = useForm<CreateFormValues>({
    initialValues: {
      patient_id: 'patient-1',
      attending_id: null,
      room_id: 'room-1',
      equipment_id: null,
      start_time: '2026-09-01 09:00:00',
      end_time: '2026-09-01 09:30:00',
      notes: '',
    },
  })
  const actions = useAppointmentActions({ token: 'tok', form, onSubmitSuccess, onInterpretApplied })
  return { form, actions }
}

const CREATE_PAYLOAD = { start_time: '2026-09-01T09:00:00.000Z', end_time: '2026-09-01T09:30:00.000Z' }

describe('useAppointmentActions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('resets the form and calls onSubmitSuccess after a successful create', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(appointmentsApi.createAppointment).mockResolvedValue({ id: 'appt-1' } as any)
    const onSubmitSuccess = vi.fn()
    const { result } = renderHook(() => useHarness(onSubmitSuccess), { wrapper })

    act(() => result.current.form.setFieldValue('patient_id', 'patient-2'))
    await act(async () => {
      result.current.actions.createMutation.mutate(CREATE_PAYLOAD)
    })

    await waitFor(() => expect(onSubmitSuccess).toHaveBeenCalledTimes(1))
    expect(result.current.form.values.patient_id).toBe('patient-1')
  })

  it('opens the conflict state instead of a default error toast on a 409 with conflicts', async () => {
    const conflicts = [{ resource_type: 'room' as const, resource_id: 'room-2', resource_name: 'Room 2' }]
    vi.mocked(appointmentsApi.createAppointment).mockRejectedValue(
      new ApiError(409, 'Conflicting booking', conflicts),
    )
    const { result } = renderHook(() => useHarness(vi.fn()), { wrapper })

    await act(async () => {
      result.current.actions.createMutation.mutate(CREATE_PAYLOAD)
    })

    await waitFor(() => expect(result.current.actions.conflictState).not.toBeNull())
    expect(result.current.actions.conflictState?.conflicts).toEqual(conflicts)
  })

  it('clears the conflict state, resets the form and calls onSubmitSuccess after joining the waitlist', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(waitlistApi.joinWaitlist).mockResolvedValue({ id: 'wl-1' } as any)
    const onSubmitSuccess = vi.fn()
    const { result } = renderHook(() => useHarness(onSubmitSuccess), { wrapper })

    act(() => result.current.actions.setConflictState({ payload: CREATE_PAYLOAD, conflicts: [] }))
    act(() => result.current.form.setFieldValue('patient_id', 'patient-2'))

    await act(async () => {
      result.current.actions.joinWaitlistMutation.mutate(CREATE_PAYLOAD)
    })

    await waitFor(() => expect(onSubmitSuccess).toHaveBeenCalledTimes(1))
    expect(result.current.actions.conflictState).toBeNull()
    expect(result.current.form.values.patient_id).toBe('patient-1')
  })

  it('applies interpreted values to the form and calls onInterpretApplied', async () => {
    vi.mocked(schedulingAssistantApi.interpretSchedulingRequest).mockResolvedValue({
      patient_id: 'patient-9',
      attending_id: null,
      room_id: null,
      equipment_id: null,
      start_time: '2026-09-05T10:00:00.000Z',
      end_time: '2026-09-05T10:30:00.000Z',
      notes: null,
      warnings: ['Assumed room from your usual booking'],
    })
    const onInterpretApplied = vi.fn()
    const { result } = renderHook(() => useHarness(vi.fn(), onInterpretApplied), { wrapper })

    await act(async () => {
      result.current.actions.interpretMutation.mutate('book Jane tomorrow at 10')
    })

    await waitFor(() => expect(result.current.form.values.patient_id).toBe('patient-9'))
    expect(onInterpretApplied).toHaveBeenCalledTimes(1)
    expect(result.current.actions.interpretWarnings).toEqual(['Assumed room from your usual booking'])
  })
})
