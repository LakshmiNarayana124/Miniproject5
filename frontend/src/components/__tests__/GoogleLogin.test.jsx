// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'

const firebase = vi.hoisted(() => ({ popup: vi.fn(), redirect: vi.fn(), result: vi.fn() }))
vi.mock('../../firebase.js', () => ({ isFirebaseConfigured: true, firebaseAuth: {} }))
vi.mock('firebase/auth', () => ({
  GoogleAuthProvider: class { setCustomParameters() {} },
  signInWithPopup: firebase.popup,
  signInWithRedirect: firebase.redirect,
  getRedirectResult: firebase.result,
  RecaptchaVerifier: class {},
  signInWithPhoneNumber: vi.fn(),
}))
import LoginPage from '../LoginPage.jsx'

const firebaseUser = { getIdToken: vi.fn().mockResolvedValue('firebase-token') }
let returnedRole
let exchangeCalls
let adminLinkRequired
beforeEach(() => {
  sessionStorage.clear()
  firebase.popup.mockReset().mockResolvedValue({ user: firebaseUser })
  firebase.redirect.mockReset().mockResolvedValue(undefined)
  firebase.result.mockReset().mockResolvedValue(null)
  returnedRole = 'OPERATOR'
  exchangeCalls = []
  adminLinkRequired = false
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (String(url).includes('/auth/registration-status')) {
      return { ok: true, json: async () => ({ registration_enabled: true }) }
    }
    if (String(url).includes('/auth/firebase-login')) {
      exchangeCalls.push(JSON.parse(options.body))
      if (adminLinkRequired && !exchangeCalls.at(-1).admin_password) {
        return { ok: false, text: async () => JSON.stringify({ detail: { code: 'ADMIN_LINK_REQUIRED', message: 'Link your administrator account.' } }) }
      }
      return { ok: true, text: async () => JSON.stringify({
        access_token: 'token', username: 'user', role: returnedRole,
      }) }
    }
    return { ok: true }
  }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('Google login role', () => {
  it.each([
    ['OPERATOR', 'Operator'], ['MAINTENANCE_ENGINEER', 'Engineer'], ['ADMIN', 'Admin'],
  ])('restores the %s role after redirect', async (role, label) => {
    sessionStorage.setItem('iw_pending_google_role', role)
    firebase.result.mockResolvedValue({ user: firebaseUser })
    returnedRole = role
    const onLogin = vi.fn()
    render(<StrictMode><LoginPage onLogin={onLogin} /></StrictMode>)
    await waitFor(() => expect(onLogin).toHaveBeenCalledTimes(1))
    expect(exchangeCalls).toEqual([{ id_token: 'firebase-token', requested_role: role }])
    expect(onLogin.mock.calls[0][0].role).toBe(role)
    expect(screen.getByRole('button', { name: new RegExp(`Sign in as.*${label}`) })).toBeTruthy()
    expect(sessionStorage.getItem('iw_pending_google_role')).toBeNull()
  })

  it('stores the selected role before redirecting when the popup is blocked', async () => {
    firebase.popup.mockRejectedValue({ code: 'auth/popup-blocked' })
    render(<LoginPage onLogin={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: /Administrator/ }))
    fireEvent.click(await screen.findByRole('tab', { name: /Google/ }))
    fireEvent.click(screen.getByRole('button', { name: /Sign in as.*Admin/ }))
    await waitFor(() => expect(firebase.redirect).toHaveBeenCalledTimes(1))
    expect(sessionStorage.getItem('iw_pending_google_role')).toBe('ADMIN')
  })

  it('links an admin with credentials once and only stores the app session', async () => {
    adminLinkRequired = true
    returnedRole = 'ADMIN'
    const onLogin = vi.fn()
    render(<LoginPage onLogin={onLogin} />)
    fireEvent.click(await screen.findByRole('button', { name: /Administrator/ }))
    fireEvent.click(await screen.findByRole('tab', { name: /Google/ }))
    fireEvent.click(screen.getByRole('button', { name: /Sign in as.*Admin/ }))
    fireEvent.change(await screen.findByLabelText('Admin username'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Admin password'), { target: { value: 'secret-password' } })
    fireEvent.click(screen.getByRole('button', { name: /Link and sign in/ }))
    await waitFor(() => expect(onLogin).toHaveBeenCalledTimes(1))
    expect(exchangeCalls[1]).toMatchObject({ requested_role: 'ADMIN', admin_username: 'admin', admin_password: 'secret-password' })
    expect(JSON.stringify(sessionStorage)).not.toContain('secret-password')
  })

  it('rejects a response with a role different from the selected role', async () => {
    const onLogin = vi.fn()
    render(<LoginPage onLogin={onLogin} />)
    fireEvent.click(await screen.findByRole('button', { name: /Administrator/ }))
    fireEvent.click(await screen.findByRole('tab', { name: /Google/ }))
    fireEvent.click(screen.getByRole('button', { name: /Sign in as.*Admin/ }))
    await screen.findByText(/cannot sign in with the selected role/)
    expect(exchangeCalls[0].requested_role).toBe('ADMIN')
    expect(onLogin).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('iw_token')).toBeNull()
  })
})
