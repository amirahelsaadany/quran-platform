// Service Worker بسيط لتفعيل تثبيت المنصة كتطبيق (PWA) على الجوال/الكمبيوتر/الآيباد.
// لا يقوم بأي تخزين مؤقت (offline caching) حالياً حتى لا يؤثر على أي محتوى ديناميكي.
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // تمرير الطلبات مباشرة للشبكة (بدون كاش) - يمكن تطويره لاحقاً لدعم العمل بدون إنترنت
  event.respondWith(fetch(event.request));
});
