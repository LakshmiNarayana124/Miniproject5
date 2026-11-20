// IntelliWatch Service Worker — v3
// Strategy:
//   - HTML navigation requests: always network-first, never serve stale shell
//   - API routes: always network-only (never cached)
//   - Static assets (/assets/*, icons, manifest): cache-first with
//     network fallback (assets are content-hashed by Vite, so safe to cache)

const CACHE = 'intelliwatch-v3'

// On install, do NOT pre-cache anything — let the browser's normal HTTP cache
// handle index.html. This prevents stale shell being served on hard-refresh.
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', e => {
  // Delete every old cache version
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return

  const url = new URL(e.request.url)
  const path = url.pathname

  // ── 1. API calls: always network-only ───────────────────────────────────
  const API_PREFIXES = [
    '/auth', '/stream', '/control', '/models', '/learning',
    '/explorer', '/iot', '/audit', '/sensors', '/chatbot',
    '/vision', '/leaderboard', '/docs', '/openapi.json',
  ]
  if (API_PREFIXES.some(p => path.startsWith(p))) return

  // ── 2. HTML navigation (index.html / any page route): network-first ─────
  // If network fails, return a simple offline notice rather than a stale shell.
  if (e.request.mode === 'navigate' || path === '/' || path.endsWith('.html')) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).catch(() =>
        new Response(
          '<!doctype html><html><head><meta charset="utf-8"><title>IntelliWatch – Offline</title></head>' +
          '<body style="font-family:sans-serif;padding:40px;background:#0d0f14;color:#a0a8c0">' +
          '<h1>IntelliWatch</h1><p>You are offline. Please reconnect and reload.</p></body></html>',
          { headers: { 'Content-Type': 'text/html' } }
        )
      )
    )
    return
  }

  // ── 3. Vite-hashed static assets (/assets/*): cache-first ───────────────
  // These filenames contain a content hash so it is always safe to cache them.
  if (path.startsWith('/assets/') || path.startsWith('/icons/') || path === '/favicon.svg' || path === '/manifest.json') {
    e.respondWith(
      caches.open(CACHE).then(cache =>
        cache.match(e.request).then(cached => {
          if (cached) return cached
          return fetch(e.request).then(resp => {
            if (resp.ok) cache.put(e.request, resp.clone())
            return resp
          })
        })
      )
    )
    return
  }

  // ── 4. Everything else: network with no caching ──────────────────────────
})
