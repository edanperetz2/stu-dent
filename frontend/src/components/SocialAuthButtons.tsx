import { Button, Divider, Stack } from '@mantine/core'
import { API_BASE_URL } from '../api/httpClient'
import type { Role } from '../api/types'

interface SocialAuthButtonsProps {
  flow: 'login' | 'register'
  role?: Role
  ownerStudentId?: string
  fullName?: string
  next?: string
}

export function SocialAuthButtons({
  flow,
  role,
  ownerStudentId,
  fullName,
  next = '/appointments',
}: SocialAuthButtonsProps) {
  function googleHref(): string {
    const url = new URL(`${API_BASE_URL}/auth/oauth/google/start`)
    url.searchParams.set('flow', flow)
    url.searchParams.set('next', next)
    if (flow === 'register' && role) url.searchParams.set('role', role)
    if (flow === 'register' && ownerStudentId) {
      url.searchParams.set('owner_student_id', ownerStudentId)
    }
    if (flow === 'register' && fullName?.trim()) {
      url.searchParams.set('full_name', fullName.trim())
    }
    return url.toString()
  }

  const label = flow === 'login' ? 'Sign in with Google' : 'Sign up with Google'

  return (
    <Stack gap="sm">
      <Button
        component="a"
        href={googleHref()}
        variant="default"
        className="google-auth-button"
        aria-label={label}
        fullWidth
      >
        <span className="google-auth-button__content">
          <GoogleLogo />
          <span>{label}</span>
          <span aria-hidden="true" />
        </span>
      </Button>
      <Divider label="or continue with email" labelPosition="center" />
    </Stack>
  )
}

function GoogleLogo() {
  return (
    <svg
      aria-hidden="true"
      className="google-auth-button__logo"
      viewBox="0 0 18 18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fill="#4285F4"
        d="M17.64 9.205c0-.638-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.797 2.716v2.259h2.909c1.702-1.567 2.684-3.875 2.684-6.615Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.909-2.259c-.806.54-1.836.859-3.047.859-2.344 0-4.328-1.585-5.037-3.714H.956v2.333A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.963 12.706A5.41 5.41 0 0 1 3.682 11c0-.592.102-1.168.281-1.706V6.961H.956A9 9 0 0 0 0 11c0 1.452.347 2.827.956 4.039l3.007-2.333Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.321 0 2.507.454 3.441 1.346l2.581-2.581C13.463.892 11.43 0 9 0A9 9 0 0 0 .956 4.961l3.007 2.333C4.672 5.165 6.656 3.58 9 3.58Z"
      />
    </svg>
  )
}
