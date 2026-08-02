import { Badge, Button, Group, Paper, Stack, Text, Textarea, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { askQuestion, generateReport, listReports } from '../../api/reports'
import { apiErrorMessage } from '../../api/httpClient'
import type { ReportContentSource, ReportPeriodType } from '../../api/types'
import { useAuthToken } from '../../auth/useAuthToken'
import { CardListSkeleton } from '../../components/Skeletons'
import { EmptyText, ErrorText } from '../../components/StateText'
import { formatDateTime } from '../../utils/dates'

const PERIOD_COLORS: Record<ReportPeriodType, string> = {
  weekly: 'blue',
  monthly: 'grape',
  ad_hoc: 'teal',
}

function periodLabel(periodType: ReportPeriodType): string {
  if (periodType === 'ad_hoc') return 'Q&A'
  return periodType[0].toUpperCase() + periodType.slice(1)
}

const CONTENT_SOURCE: Record<ReportContentSource, { label: string; color: string }> = {
  ai: { label: 'AI-narrated', color: 'blue' },
  fallback_summary: { label: 'Data summary', color: 'gray' },
  unsupported: { label: 'Unsupported question', color: 'yellow' },
  unavailable: { label: 'Assistant unavailable', color: 'red' },
  malformed_response: { label: 'Assistant response unusable', color: 'red' },
  unresolved_date_range: { label: 'Date range not understood', color: 'yellow' },
}

export function ReportsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [question, setQuestion] = useState('')

  const {
    data: reports,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['reports'],
    queryFn: () => listReports(token),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['reports'] })

  const generateMutation = useMutation({
    mutationFn: () => generateReport(token),
    onSuccess: () => {
      invalidate()
      notifications.show({ message: 'Report generated', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to generate report'),
        color: 'red',
      })
    },
  })

  const askMutation = useMutation({
    mutationFn: (q: string) => askQuestion(token, q),
    onSuccess: () => {
      invalidate()
      setQuestion('')
      // The new answer just lands somewhere in a mixed list of periodic
      // reports, distinguished only by a small "Q&A" badge -- without this,
      // a user who asks a question has no confirmation anything happened
      // beyond the textbox clearing.
      notifications.show({ message: 'Answer added below', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to get an answer'),
        color: 'red',
      })
    },
  })

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reports</Title>
        <Button onClick={() => generateMutation.mutate()} loading={generateMutation.isPending}>
          Generate report now
        </Button>
      </Group>

      <Stack gap="xs">
        <Textarea
          label="Ask a question"
          placeholder="e.g. which equipment is underused this month?"
          value={question}
          onChange={(event) => setQuestion(event.currentTarget.value)}
          autosize
          minRows={2}
        />
        <Button
          variant="light"
          onClick={() => askMutation.mutate(question)}
          loading={askMutation.isPending}
          disabled={!question.trim()}
        >
          Ask
        </Button>
      </Stack>

      {isLoading ? (
        <CardListSkeleton />
      ) : isError ? (
        <ErrorText onRetry={() => refetch()}>
          {apiErrorMessage(error, 'Failed to load reports.')}
        </ErrorText>
      ) : reports?.length === 0 ? (
        <EmptyText>No reports yet.</EmptyText>
      ) : (
        <Stack gap="xs">
          {reports?.map((report) => (
            <Paper key={report.id} withBorder p="sm">
              <Stack gap={4}>
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap">
                    <Badge size="sm" color={PERIOD_COLORS[report.period_type]}>
                      {periodLabel(report.period_type)}
                    </Badge>
                    <Badge
                      size="sm"
                      variant="light"
                      color={CONTENT_SOURCE[report.content_source].color}
                    >
                      {CONTENT_SOURCE[report.content_source].label}
                    </Badge>
                  </Group>
                  <Text size="xs" c="dimmed" className="text-nowrap">
                    {formatDateTime(report.created_at)}
                  </Text>
                </Group>
                <Text fw={600}>{report.title}</Text>
                {/* Visible even when content_source is a non-answer (e.g.
                    unresolved_date_range) -- lets a viewer see exactly what
                    range would have been used, not just take the narrated
                    content on faith. */}
                <Text size="xs" c="dimmed">
                  Period: {formatDateTime(report.period_start)} &ndash;{' '}
                  {formatDateTime(report.period_end)}
                </Text>
                <Text size="sm">{report.content}</Text>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
