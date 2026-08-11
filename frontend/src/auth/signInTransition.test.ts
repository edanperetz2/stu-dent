import { describe, expect, it } from 'vitest'
import {
  GOOGLE_MINIMUM_SIGN_IN_MS,
  MINIMUM_SIGN_IN_MS,
  remainingSignInTime,
} from './signInTransition'

describe('sign-in transition timing', () => {
  it('keeps the transition visible for at least one second', () => {
    expect(MINIMUM_SIGN_IN_MS).toBe(1000)
    expect(remainingSignInTime(250, 1249)).toBe(1)
    expect(remainingSignInTime(250, 1250)).toBe(0)
    expect(remainingSignInTime(250, 1500)).toBe(0)
  })

  it('keeps Google sign-in visible for one and a half seconds', () => {
    expect(GOOGLE_MINIMUM_SIGN_IN_MS).toBe(1500)
    expect(remainingSignInTime(250, 1249, GOOGLE_MINIMUM_SIGN_IN_MS)).toBe(501)
    expect(remainingSignInTime(250, 1750, GOOGLE_MINIMUM_SIGN_IN_MS)).toBe(0)
  })
})
