(function () {
  var docEl = document.documentElement;
  var root = docEl.getAttribute('data-root') || '';
  var current = docEl.getAttribute('data-edition') || '';

  // 섹션 탭
  var tabs = document.querySelectorAll('.tab');
  var items = document.querySelectorAll('[data-cat]');
  var empty = document.getElementById('empty');
  function apply(cat) {
    var shown = 0;
    items.forEach(function (el) {
      var on = cat === 'all' || el.getAttribute('data-cat') === cat;
      el.hidden = !on;
      if (on) shown++;
    });
    if (empty) empty.hidden = shown > 0;
    tabs.forEach(function (t) { t.setAttribute('aria-pressed', t.getAttribute('data-filter') === cat ? 'true' : 'false'); });
  }
  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      apply(t.getAttribute('data-filter'));
      try { localStorage.setItem('mt-tab', t.getAttribute('data-filter')); } catch (e) {}
    });
  });
  if (tabs.length) {
    var saved = 'all';
    try { saved = localStorage.getItem('mt-tab') || 'all'; } catch (e) {}
    if (document.querySelector('.tab[data-filter="' + saved + '"]')) apply(saved);
  }

  // 오프라인·설치용 서비스 워커
  if ('serviceWorker' in navigator && /^https?:/.test(location.protocol)) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(root + 'sw.js').catch(function () {});
    });
  }

  // 새 판이 나왔는지 확인 (열어 둔 앱으로 돌아올 때마다)
  var bar = document.getElementById('newer');
  function check() {
    if (!bar || !current || !window.fetch) return;
    fetch(root + 'latest.json?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.id && j.id !== current) {
          bar.querySelector('.bt').textContent = j.label + ' · ' + j.title;
          bar.hidden = false;
        }
      })
      .catch(function () {});
  }
  check();
  document.addEventListener('visibilitychange', function () { if (!document.hidden) check(); });

  // 앱 설치 버튼
  var btn = document.getElementById('install');
  var hint = document.getElementById('ioshint');
  var deferred = null;
  var standalone = window.navigator.standalone === true ||
    (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  window.addEventListener('beforeinstallprompt', function (ev) {
    ev.preventDefault();
    deferred = ev;
    if (btn) btn.hidden = false;
  });
  window.addEventListener('appinstalled', function () { if (btn) btn.hidden = true; });
  if (btn && isIOS && !standalone) btn.hidden = false;
  if (btn) {
    btn.addEventListener('click', function () {
      if (deferred) {
        deferred.prompt();
        deferred.userChoice.then(function () { btn.hidden = true; deferred = null; }, function () {});
      } else if (hint) {
        hint.hidden = !hint.hidden;
      }
    });
  }
})();
