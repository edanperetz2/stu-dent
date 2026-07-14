import { Button, Group } from '@mantine/core'
import { IconThumbDown, IconThumbUp } from '@tabler/icons-react'

interface VoteButtonsProps {
  likes: number
  dislikes: number
  myVote: 1 | -1 | null
  onVote: (value: 1 | -1) => void
  onRemoveVote: () => void
  size?: 'sm' | 'md'
  loading?: boolean
}

/** A single combined like/dislike control per direction -- the icon and its
 * count live in the same clickable button, no separate static badge.
 * Clicking the already-active direction removes the vote instead of
 * re-voting it (toggle behavior), clicking the other direction switches it. */
export function VoteButtons({
  likes,
  dislikes,
  myVote,
  onVote,
  onRemoveVote,
  size = 'md',
  loading,
}: VoteButtonsProps) {
  const iconSize = size === 'sm' ? 14 : 16
  const buttonSize = size === 'sm' ? 'compact-xs' : 'compact-sm'

  const handleClick = (value: 1 | -1) => (event: React.MouseEvent) => {
    event.stopPropagation()
    if (myVote === value) {
      onRemoveVote()
    } else {
      onVote(value)
    }
  }

  return (
    <Group gap={6} onClick={(event) => event.stopPropagation()} wrap="nowrap">
      <Button
        size={buttonSize}
        variant={myVote === 1 ? 'filled' : 'light'}
        color="green"
        aria-label="Like"
        aria-pressed={myVote === 1}
        leftSection={<IconThumbUp size={iconSize} />}
        onClick={handleClick(1)}
        loading={loading}
      >
        {likes}
      </Button>
      <Button
        size={buttonSize}
        variant={myVote === -1 ? 'filled' : 'light'}
        color="red"
        aria-label="Dislike"
        aria-pressed={myVote === -1}
        leftSection={<IconThumbDown size={iconSize} />}
        onClick={handleClick(-1)}
        loading={loading}
      >
        {dislikes}
      </Button>
    </Group>
  )
}
