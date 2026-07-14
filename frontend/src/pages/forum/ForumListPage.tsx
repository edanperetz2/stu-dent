import { Button, Group, Modal, Stack, Text, Textarea, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createPost, listPosts, type ForumPostCreateInput } from '../../api/forum'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'
import { ForumPostCard } from './ForumPostCard'

export function ForumListPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)
  const [expandedPostId, setExpandedPostId] = useState<string | null>(null)

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
    <Stack maw={640} mx="auto">
      <Group justify="space-between">
        <Title order={2}>Forum</Title>
        {isStudent && <Button onClick={open}>New Post</Button>}
      </Group>

      {isLoading && <LoadingText />}
      {!isLoading && sortedPosts.length === 0 && <Text c="dimmed">No posts yet.</Text>}

      <Stack gap={0}>
        {sortedPosts.map((post) => (
          <ForumPostCard
            key={post.id}
            post={post}
            expanded={expandedPostId === post.id}
            onToggleExpand={() =>
              setExpandedPostId((current) => (current === post.id ? null : post.id))
            }
          />
        ))}
      </Stack>

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
