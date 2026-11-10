/* 拾光相册 Service Worker
 * 1. 静态资源缓存（/assets 指纹文件 cache-first）
 * 2. Web Share Target：接收系统分享的图片/视频，暂存 Cache 后打开应用
 *    （POST /share-receive → 暂存 → 303 跳首页 → 应用启动时取走并自动上传）
 */
const STATIC_CACHE = 'static-v2'
const SHARE_CACHE = 'share-target'

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => ![STATIC_CACHE, SHARE_CACHE].includes(k)).map((k) => caches.delete(k))
      )
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Web Share Target：系统分享 POST
  if (event.request.method === 'POST' && url.pathname === '/share-receive') {
    event.respondWith(handleShare(event.request))
    return
  }

  if (event.request.method !== 'GET') return

  // 指纹静态资源：cache-first
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icon-')) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(async (cache) => {
        const hit = await cache.match(event.request)
        if (hit) return hit
        const res = await fetch(event.request)
        if (res.ok) cache.put(event.request, res.clone())
        return res
      })
    )
    return
  }

  // 页面导航与 API：network-first（API 不缓存，保证数据新鲜）
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/'))
    )
  }
})

async function handleShare(request) {
  try {
    const formData = await request.formData()
    const files = formData.getAll('media').filter((f) => f && f.size > 0)
    const cache = await caches.open(SHARE_CACHE)
    await cache.put('share-count', new Response(String(files.length)))
    await Promise.all(
      files.map((f, i) =>
        cache.put(
          `share-file-${i}`,
          new Response(f, {
            headers: {
              'X-File-Name': encodeURIComponent(f.name || `shared_${i}`),
              'Content-Type': f.type || 'application/octet-stream',
            },
          })
        )
      )
    )
    return Response.redirect('/?from-share=1', 303)
  } catch (e) {
    return new Response('share receive error', { status: 500 })
  }
}
