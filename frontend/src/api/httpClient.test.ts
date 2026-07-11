import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from './httpClient'

function mockFetchOnce(status: number, body: unknown, statusText = 'Error') {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText,
      json: async () => body,
    }),
  )
}

describe('request error handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('extracts a plain string detail (HTTPException-style errors)', async () => {
    mockFetchOnce(401, { detail: 'Incorrect email or password' })

    await expect(request('/auth/login')).rejects.toMatchObject({
      status: 401,
      message: 'Incorrect email or password',
    })
  })

  it('extracts a readable message from FastAPI/Pydantic 422 array-format errors', async () => {
    mockFetchOnce(422, {
      detail: [
        {
          type: 'string_too_short',
          loc: ['body', 'password'],
          msg: 'String should have at least 8 characters',
        },
      ],
    })

    await expect(request('/patients/1/credentials')).rejects.toBeInstanceOf(ApiError)
    try {
      await request('/patients/1/credentials')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).message).toContain('password')
      expect((err as ApiError).message).toContain('String should have at least 8 characters')
    }
  })

  it('falls back to statusText when the body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => {
          throw new Error('not json')
        },
      }),
    )

    await expect(request('/health')).rejects.toMatchObject({
      status: 500,
      message: 'Internal Server Error',
    })
  })
})
