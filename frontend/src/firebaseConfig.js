/**
 * Firebase configuration — loaded from Vite env vars.
 * Set these in Vercel Environment Variables (and .env.local for dev).
 *
 * VITE_FIREBASE_API_KEY
 * VITE_FIREBASE_AUTH_DOMAIN
 * VITE_FIREBASE_PROJECT_ID
 * VITE_FIREBASE_STORAGE_BUCKET
 * VITE_FIREBASE_MESSAGING_SENDER_ID
 * VITE_FIREBASE_APP_ID
 */

export const FIREBASE_CONFIG = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY            || '',
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN        || '',
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID         || '',
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET     || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID|| '',
  appId:             import.meta.env.VITE_FIREBASE_APP_ID             || '',
}

export const FIREBASE_ENABLED = Boolean(FIREBASE_CONFIG.apiKey)

/**
 * Lazily initialise Firebase only when actually needed.
 * Returns { auth, GoogleAuthProvider, signInWithPopup,
 *           RecaptchaVerifier, signInWithPhoneNumber }
 * or null if env vars are missing.
 */
export async function getFirebaseAuth() {
  if (!FIREBASE_ENABLED) return null
  try {
    const { initializeApp, getApps } = await import('https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js')
    const {
      getAuth,
      GoogleAuthProvider,
      signInWithPopup,
      RecaptchaVerifier,
      signInWithPhoneNumber,
    } = await import('https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js')

    const app = getApps().length
      ? getApps()[0]
      : initializeApp(FIREBASE_CONFIG)

    const auth = getAuth(app)
    return { auth, GoogleAuthProvider, signInWithPopup, RecaptchaVerifier, signInWithPhoneNumber }
  } catch (e) {
    console.error('[Firebase] Init failed:', e)
    return null
  }
}
