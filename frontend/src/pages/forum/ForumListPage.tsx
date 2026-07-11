import { Badge, Button, Group, Modal, Stack, Table, Textarea, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { createPost, listPosts, type ForumPostCreateInput } from '../../api/forum'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'

export function ForumListPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [opened, { open, close }] = useDisclosure(false)

  const isStudent = principal?.role === 'student'

  const { data: posts, isLoading } = useQuery({
    queryKey: ['forum', 'posts'],
    queryFn: () => listPosts(token),
  })

  const form = useForm<ForumPostCreateInput>({
    initialValues: { title: '', body: '' },
    validate: {
      title: (value) => (value.trim().length > 0 ? null : 'Title is required'),
      body: (value) => (value.trim().length > 0 ? null : 'Body is required'),
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: ForumPostCreateInput) => createPost(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forum', 'posts'] })
      notifications.show({ message: 'Post created', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create post'),
        color: 'red',
      })
    },
  })

  const sortedPosts = [...(posts ?? [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Forum</Title>
        {isStudent && <Button onClick={open}>New Post</Button>}
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Title</Table.Th>
              <Table.Th>Score</Table.Th>
              <Table.Th>Posted</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedPosts.map((post) => (
              <Table.Tr
                key={post.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/forum/${post.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/forum/${post.id}`)
                  }
                }}
                tabIndex={0}
                role="button"
              >
                <Table.Td>{post.title}</Table.Td>
                <Table.Td>
                  <Badge color={post.score >= 0 ? 'blue' : 'red'}>{post.score}</Badge>
                </Table.Td>
                <Table.Td>{new Date(post.created_at).toLocaleString()}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="New Post">
        <form onSubmit={form.onSubmit((values) => createMutation.mutate(values))}>
          <Stack>
            <TextInput label="Title" {...form.getInputProps('title')} />
            <Textarea label="Body" minRows={4} {...form.getInputProps('body')} />
            <Button type="submit" loading={createMutation.isPending}>
              Post
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
