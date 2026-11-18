// IntelliWatch Service Worker — PWA mobile app support
const CACHE = 'intelliwatch-v1'
const APP_SHELL = ['/', '/index.html', '/manifest.json', '/favicon.svg']

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(APP_SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', e => {
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

  // Network-first for API calls, cache-first for everything else
  if (url.pathname.startsWith('/auth') || url.pathname.startsWith('/stream') ||
      url.pathname.startsWith('/control') || url.pathname.startsWith('/models') ||
      url.pathname.startsWith('/learning') || url.pathname.startsWith('/explorer') ||
      url.pathname.startsWith('/iot') || url.pathname.startsWith('/audit') ||
      url.pathname.startsWith('/sensors') || url.pathname.startsWith('/chatbot') ||
      url.pathname.startsWith('/vision')) {
    return // Don't cache API calls — let them go to network
  }

  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(resp => {
        if (resp.ok && url.origin === self.location.origin) {
          const clone = resp.clone()
          caches.open(CACHE).then(c => c.put(e.request, clone))
        }
        return resp
      }).catch(() => caches.match('/index.html'))
    )
  )
})
