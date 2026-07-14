import { Avatar, Button, Divider, Group, Paper, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { IconMessageCircle, IconUser } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  createComment,
  deleteComment,
  deletePost,
  listComments,
  removeCommentVote,
  removePostVote,
  updatePost,
  voteComment,
  votePost,
} from '../../api/forum'
import { apiErrorMessage } from '../../api/httpClient'
import type { ForumPost } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { LoadingText } from '../../components/StateText'
import { VoteButtons } from '../../components/VoteButtons'

interface ForumPostCardProps {
  post: ForumPost
  expanded: boolean
  onToggleExpand: () => void
}

/** A single feed card: collapsed shows a tweet-like preview (avatar, title,
 * truncated body, vote counters, reply count); expanded (in place, no route
 * change) reveals the full body plus the reply thread inline underneath. */
export function ForumPostCard({ post, expanded, onToggleExpand }: ForumPostCardProps) {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [commentBody, setCommentBody] = useState('')

  const isAdmin = principal?.role === 'admin'
  const isAuthor = principal?.id === post.author_student_id

  const editForm = useForm({ initialValues: { title: post.title, body: post.body } })

  useEffect(() => {
    editForm.setValues({ title: post.title, body: post.body })
    // Re-sync only when the post's own title/body change (e.g. after a
    // successful edit), not on every refetch triggered by unrelated vote or
    // comment-count updates, which would otherwise clobber an in-progress edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [post.title, post.body])

  const { data: comments, isLoading: commentsLoading } = useQuery({
    queryKey: ['forum', 'posts', post.id, 'comments'],
    queryFn: () => listComments(token, post.id),
    enabled: expanded,
  })

  const invalidatePosts = () => queryClient.invalidateQueries({ queryKey: ['forum', 'posts'] })
  const invalidateComments = () =>
    queryClient.invalidateQueries({ queryKey: ['forum', 'posts', post.id, 'comments'] })

  const voteMutation = useMutation({
    mutationFn: (value: 1 | -1) => votePost(token, post.id, value),
    onSuccess: invalidatePosts,
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to vote'), color: 'red' }),
  })
  const removeVoteMutation = useMutation({
    mutationFn: () => removePostVote(token, post.id),
    onSuccess: invalidatePosts,
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to remove vote'), color: 'red' }),
  })

  const updateMutation = useMutation({
    mutationFn: (values: { title: string; body: string }) => updatePost(token, post.id, values),
    onSuccess: () => {
      invalidatePosts()
      setEditing(false)
    },
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to update post'), color: 'red' }),
  })

  const deletePostMutation = useMutation({
    mutationFn: () => deletePost(token, post.id),
    onSuccess: () => {
      notifications.show({ message: 'Post deleted', color: 'green' })
      invalidatePosts()
    },
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to delete post'), color: 'red' }),
  })

  const addCommentMutation = useMutation({
    mutationFn: (body: string) => createComment(token, post.id, { body }),
    onSuccess: () => {
      invalidateComments()
      invalidatePosts()
      setCommentBody('')
    },
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to add comment'), color: 'red' }),
  })

  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: string) => deleteComment(token, commentId),
    onSuccess: () => {
      invalidateComments()
      invalidatePosts()
    },
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

  return (
    <Stack gap={0} style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}>
      <Group
        align="flex-start"
        wrap="nowrap"
        p="md"
        style={{ cursor: 'pointer' }}
        onClick={onToggleExpand}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggleExpand()
          }
        }}
        tabIndex={0}
        role="button"
        aria-expanded={expanded}
      >
        <Avatar radius="xl" color="blue">
          <IconUser size={20} />
        </Avatar>
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Text fw={700}>{post.title}</Text>
          <Text
            size="sm"
            c="dimmed"
            lineClamp={expanded ? undefined : 3}
            style={{ whiteSpace: 'pre-wrap' }}
          >
            {post.body}
          </Text>
          <Group justify="space-between" mt={6} wrap="nowrap">
            <Group gap="lg" wrap="nowrap">
              <VoteButtons
                size="sm"
                likes={post.likes}
                dislikes={post.dislikes}
                myVote={post.my_vote}
                onVote={(value) => voteMutation.mutate(value)}
                onRemoveVote={() => removeVoteMutation.mutate()}
                loading={voteMutation.isPending || removeVoteMutation.isPending}
              />
              <Group gap={4} c="dimmed" wrap="nowrap">
                <IconMessageCircle size={16} />
                <Text size="sm">{post.comment_count}</Text>
              </Group>
            </Group>
            <Text size="xs" c="dimmed">
              {new Date(post.created_at).toLocaleString()}
            </Text>
          </Group>
        </Stack>
      </Group>

      {expanded && (
        <Stack gap="xs" pl={68} pr="md" pb="md">
          {editing ? (
            <Stack>
              <TextInput label="Title" {...editForm.getInputProps('title')} />
              <Textarea label="Body" minRows={4} {...editForm.getInputProps('body')} />
              <Group>
                <Button
                  size="xs"
                  loading={updateMutation.isPending}
                  onClick={() => updateMutation.mutate(editForm.values)}
                >
                  Save
                </Button>
                <Button size="xs" variant="default" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              </Group>
            </Stack>
          ) : (
            (isAuthor || isAdmin) && (
              <Group>
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
              </Group>
            )
          )}

          <Divider label={`Replies (${comments?.length ?? 0})`} />
          {commentsLoading && <LoadingText />}
          <Stack gap="xs">
            {comments?.map((comment) => (
              <Paper key={comment.id} withBorder p="sm">
                <Text size="sm">{comment.body}</Text>
                <Group mt="xs">
                  <VoteButtons
                    size="sm"
                    likes={comment.likes}
                    dislikes={comment.dislikes}
                    myVote={comment.my_vote}
                    onVote={(value) => voteCommentMutation.mutate({ commentId: comment.id, value })}
                    onRemoveVote={() => removeCommentVoteMutation.mutate(comment.id)}
                    loading={voteCommentMutation.isPending || removeCommentVoteMutation.isPending}
                  />
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
            <Group align="flex-end" onClick={(e) => e.stopPropagation()}>
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
      )}
    </Stack>
  )
}
