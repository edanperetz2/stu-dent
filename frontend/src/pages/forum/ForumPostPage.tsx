import {
  ActionIcon,
  Badge,
  Button,
  Divider,
  Group,
  Paper,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  createComment,
  deleteComment,
  deletePost,
  getPost,
  listComments,
  removeCommentVote,
  removePostVote,
  updatePost,
  voteComment,
  votePost,
} from '../../api/forum'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { LoadingText } from '../../components/StateText'

export function ForumPostPage() {
  const { postId } = useParams<{ postId: string }>()
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [commentBody, setCommentBody] = useState('')

  const isAdmin = principal?.role === 'admin'

  const { data: post, isLoading } = useQuery({
    queryKey: ['forum', 'posts', postId],
    queryFn: () => getPost(token, postId!),
    enabled: !!postId,
  })

  const { data: comments } = useQuery({
    queryKey: ['forum', 'posts', postId, 'comments'],
    queryFn: () => listComments(token, postId!),
    enabled: !!postId,
  })

  const editForm = useForm({ initialValues: { title: '', body: '' } })

  useEffect(() => {
    if (post) editForm.setValues({ title: post.title, body: post.body })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-sync when the fetched post changes
  }, [post])

  const invalidatePost = () => {
    queryClient.invalidateQueries({ queryKey: ['forum', 'posts', postId] })
    queryClient.invalidateQueries({ queryKey: ['forum', 'posts'] })
  }
  const invalidateComments = () => {
    queryClient.invalidateQueries({ queryKey: ['forum', 'posts', postId, 'comments'] })
  }

  const updateMutation = useMutation({
    mutationFn: (values: { title: string; body: string }) => updatePost(token, postId!, values),
    onSuccess: () => {
      invalidatePost()
      setEditing(false)
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update post'),
        color: 'red',
      }),
  })

  const deletePostMutation = useMutation({
    mutationFn: () => deletePost(token, postId!),
    onSuccess: () => {
      notifications.show({ message: 'Post deleted', color: 'green' })
      navigate('/forum')
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to delete post'),
        color: 'red',
      }),
  })

  const votePostMutation = useMutation({
    mutationFn: (value: 1 | -1) => votePost(token, postId!, value),
    onSuccess: invalidatePost,
  })
  const removePostVoteMutation = useMutation({
    mutationFn: () => removePostVote(token, postId!),
    onSuccess: invalidatePost,
  })

  const addCommentMutation = useMutation({
    mutationFn: (body: string) => createComment(token, postId!, { body }),
    onSuccess: () => {
      invalidateComments()
      setCommentBody('')
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to add comment'),
        color: 'red',
      }),
  })

  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: string) => deleteComment(token, commentId),
    onSuccess: invalidateComments,
  })

  const voteCommentMutation = useMutation({
    mutationFn: ({ commentId, value }: { commentId: string; value: 1 | -1 }) =>
      voteComment(token, commentId, value),
    onSuccess: invalidateComments,
  })
  const removeCommentVoteMutation = useMutation({
    mutationFn: (commentId: string) => removeCommentVote(token, commentId),
    onSuccess: invalidateComments,
  })

  if (isLoading) return <LoadingText />
  if (!post) return <Text>Post not found.</Text>

  const isAuthor = principal?.id === post.author_student_id

  return (
    <Stack maw={720}>
      <Button variant="subtle" size="xs" onClick={() => navigate('/forum')} w="fit-content">
        Back to forum
      </Button>

      <Paper withBorder p="md">
        {editing ? (
          <Stack>
            <TextInput label="Title" {...editForm.getInputProps('title')} />
            <Textarea label="Body" minRows={4} {...editForm.getInputProps('body')} />
            <Group>
              <Button
                loading={updateMutation.isPending}
                onClick={() => updateMutation.mutate(editForm.values)}
              >
                Save
              </Button>
              <Button variant="default" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </Group>
          </Stack>
        ) : (
          <Stack>
            <Group justify="space-between">
              <Title order={2}>{post.title}</Title>
              <Badge color={post.score >= 0 ? 'blue' : 'red'}>{post.score}</Badge>
            </Group>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{post.body}</Text>
            <Group>
              <ActionIcon variant="light" color="green" onClick={() => votePostMutation.mutate(1)}>
                +
              </ActionIcon>
              <ActionIcon variant="light" color="red" onClick={() => votePostMutation.mutate(-1)}>
                -
              </ActionIcon>
              <Button size="xs" variant="subtle" onClick={() => removePostVoteMutation.mutate()}>
                Remove my vote
              </Button>
              {(isAuthor || isAdmin) && (
                <>
                  {isAuthor && (
                    <Button size="xs" variant="light" onClick={() => setEditing(true)}>
                      Edit
                    </Button>
                  )}
                  <ConfirmButton
                    label="Delete"
                    message="This will delete the post. This can't be undone."
                    onConfirm={() => deletePostMutation.mutate()}
                    loading={deletePostMutation.isPending}
                  />
                </>
              )}
            </Group>
          </Stack>
        )}
      </Paper>

      <Divider label="Comments" />
      <Stack gap="xs">
        {comments?.map((comment) => (
          <Paper key={comment.id} withBorder p="sm">
            <Group justify="space-between" align="flex-start">
              <Text size="sm">{comment.body}</Text>
              <Badge size="sm" color={comment.score >= 0 ? 'blue' : 'red'}>
                {comment.score}
              </Badge>
            </Group>
            <Group mt="xs">
              <ActionIcon
                size="sm"
                variant="light"
                color="green"
                onClick={() => voteCommentMutation.mutate({ commentId: comment.id, value: 1 })}
              >
                +
              </ActionIcon>
              <ActionIcon
                size="sm"
                variant="light"
                color="red"
                onClick={() => voteCommentMutation.mutate({ commentId: comment.id, value: -1 })}
              >
                -
              </ActionIcon>
              <Button
                size="xs"
                variant="subtle"
                onClick={() => removeCommentVoteMutation.mutate(comment.id)}
              >
                Remove my vote
              </Button>
              {(principal?.id === comment.author_student_id || isAdmin) && (
                <Button
                  size="xs"
                  variant="subtle"
                  color="red"
                  onClick={() => deleteCommentMutation.mutate(comment.id)}
                >
                  Delete
                </Button>
              )}
            </Group>
          </Paper>
        ))}
      </Stack>

      {principal?.role === 'student' && (
        <Group align="flex-end">
          <Textarea
            flex={1}
            placeholder="Add a comment..."
            value={commentBody}
            onChange={(e) => setCommentBody(e.currentTarget.value)}
          />
          <Button
            loading={addCommentMutation.isPending}
            disabled={!commentBody.trim()}
            onClick={() => addCommentMutation.mutate(commentBody)}
          >
            Comment
          </Button>
        </Group>
      )}
    </Stack>
  )
}
