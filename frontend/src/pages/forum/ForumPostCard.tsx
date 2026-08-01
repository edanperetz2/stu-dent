import {
  Avatar,
  Button,
  Collapse,
  Divider,
  Group,
  Paper,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { IconMessageCircle, IconUser } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { memo, useEffect, useState } from 'react'
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
import { CardListSkeleton } from '../../components/Skeletons'
import { ErrorText } from '../../components/StateText'
import { VoteButtons } from '../../components/VoteButtons'
import { formatDateTime } from '../../utils/dates'

interface ForumPostCardProps {
  post: ForumPost
  expanded: boolean
  onToggleExpand: (postId: string) => void
}

/** A single feed card: collapsed shows a tweet-like preview (avatar, title,
 * truncated body, vote counters, reply count); expanded (in place, no route
 * change) reveals the full body plus the reply thread inline underneath.
 * Memoized -- `onToggleExpand` is a stable callback (see ForumListPage), so
 * expanding one post no longer re-renders every other card in the feed. */
export const ForumPostCard = memo(function ForumPostCard({
  post,
  expanded,
  onToggleExpand,
}: ForumPostCardProps) {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [commentBody, setCommentBody] = useState('')

  const isAdmin = principal?.role === 'admin'
  const isAuthor = principal?.id === post.author_student_id

  const editForm = useForm({
    initialValues: { title: post.title, body: post.body },
    validate: {
      title: (value) => (value.trim().length > 0 ? null : 'Title is required'),
      body: (value) => (value.trim().length > 0 ? null : 'Body is required'),
    },
  })

  useEffect(() => {
    editForm.setValues({ title: post.title, body: post.body })
    // Re-sync only when the post's own title/body change (e.g. after a
    // successful edit), not on every refetch triggered by unrelated vote or
    // comment-count updates, which would otherwise clobber an in-progress edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [post.title, post.body])

  const {
    data: comments,
    isLoading: commentsLoading,
    isError: commentsError,
    error: commentsErrorValue,
    refetch: refetchComments,
  } = useQuery({
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
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to delete comment'), color: 'red' }),
  })

  const voteCommentMutation = useMutation({
    mutationFn: ({ commentId, value }: { commentId: string; value: 1 | -1 }) =>
      voteComment(token, commentId, value),
    onSuccess: invalidateComments,
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to vote'), color: 'red' }),
  })
  const removeCommentVoteMutation = useMutation({
    mutationFn: (commentId: string) => removeCommentVote(token, commentId),
    onSuccess: invalidateComments,
    onError: (err) =>
      notifications.show({ message: apiErrorMessage(err, 'Failed to remove vote'), color: 'red' }),
  })

  return (
    <Stack
      gap={0}
      className="list-item-enter"
      // No Mantine shorthand for a single border side (`bd` sets all four).
      style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
    >
      <Group
        align="flex-start"
        wrap="nowrap"
        p="md"
        className="cursor-pointer"
        onClick={() => onToggleExpand(post.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggleExpand(post.id)
          }
        }}
        tabIndex={0}
        role="button"
        aria-expanded={expanded}
      >
        <Avatar radius="xl" color="blue">
          <IconUser size={20} />
        </Avatar>
        <Stack gap={4} flex={1} miw={0}>
          <Text fw={700}>{post.title}</Text>
          <Text
            size="sm"
            c="dimmed"
            lineClamp={expanded ? undefined : 3}
            className="text-pre-wrap"
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
              {formatDateTime(post.created_at)}
            </Text>
          </Group>
        </Stack>
      </Group>

      <Collapse expanded={expanded} keepMounted={false}>
        <Stack gap="xs" pl={68} pr="md" pb="md">
          {editing ? (
            <Stack>
              <TextInput label="Title" {...editForm.getInputProps('title')} />
              <Textarea label="Body" minRows={4} {...editForm.getInputProps('body')} />
              <Group>
                <Button
                  size="xs"
                  loading={updateMutation.isPending}
                  onClick={() => {
                    if (editForm.validate().hasErrors) return
                    updateMutation.mutate(editForm.values)
                  }}
                >
                  Save
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  onClick={() => {
                    // Otherwise a discarded draft (typed, then Cancelled)
                    // was still sitting in the form next time Edit reopened
                    // -- the sync effect above only re-runs after a real
                    // save, not on Cancel.
                    editForm.setValues({ title: post.title, body: post.body })
                    setEditing(false)
                  }}
                >
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
          {commentsError ? (
            <ErrorText onRetry={() => refetchComments()}>
              {apiErrorMessage(commentsErrorValue, 'Failed to load replies.')}
            </ErrorText>
          ) : (
            commentsLoading && <CardListSkeleton count={2} />
          )}
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
                    <ConfirmButton
                      label="Delete"
                      variant="subtle"
                      message="This will delete the comment. This can't be undone."
                      onConfirm={() => deleteCommentMutation.mutate(comment.id)}
                      loading={deleteCommentMutation.isPending}
                    />
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
      </Collapse>
    </Stack>
  )
})
