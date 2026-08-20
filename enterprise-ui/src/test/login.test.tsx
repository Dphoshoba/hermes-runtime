import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import LoginPage from '../pages/LoginPage'
import { AuthContext } from '../App'

const navigateSpy = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  }
})

function renderLogin() {
  const login = vi.fn()
  const logout = vi.fn()
  const user = null
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthContext.Provider value={{ user, login, logout }}>
        <LoginPage />
      </AuthContext.Provider>
    </MemoryRouter>
  )
  return { login }
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('LoginPage redirect', () => {
  it('redirects to /guided after successful login', async () => {
    const { login } = renderLogin()
    login.mockResolvedValueOnce(undefined)

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@local' },
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'pw' },
    })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(login).toHaveBeenCalled())
    expect(navigateSpy).toHaveBeenCalledWith('/guided', { replace: true })
  })

  it('stays on /login and shows error on failed login', async () => {
    const { login } = renderLogin()
    login.mockRejectedValueOnce(new Error('Invalid credentials'))

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@local' },
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'pw' },
    })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(login).toHaveBeenCalled())
    expect(screen.getByText(/invalid credentials/i)).toBeTruthy()
    expect(navigateSpy).not.toHaveBeenCalled()
  })
})
