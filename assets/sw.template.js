// 모닝테이프 서비스 워커 (build.py가 __VERSION__ 을 채워 sw.js로 만든다)
// 페이지·피드: 네트워크 우선(항상 최신 판), 실패하면 저장본
// CSS·JS·아이콘: 저장본 우선 (주소에 버전이 붙어 있어 바뀌면 새로 받음)
var CACHE = 'mt-__VERSION__';
var CORE = [
  './',
  './archive.html',
  './assets/style.css?v=__VERSION__',
  './assets/app.js?v=__VERSION__',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/favicon-32.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('mt-') === 0 && k !== CACHE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (/latest\.json$/.test(url.pathname)) return;

  var isPage = req.mode === 'navigate' || /\.(html|xml)$/.test(url.pathname) || /\/$/.test(url.pathname);
  if (isPage) {
    e.respondWith(
      fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' }).then(function (res) {
        if (res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req.url, copy); });
        }
        return res;
      }).catch(function () {
        return caches.match(req.url).then(function (r) { return r || caches.match('./'); });
      })
    );
    return;
  }
  e.respondWith(
    caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        if (res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    })
  );
});
