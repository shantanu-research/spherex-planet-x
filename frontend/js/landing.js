// Old share and embed links point at "/?q=..."; the viewer now lives at /viewer.html, so forward them.
if (location.search) location.replace('viewer.html' + location.search + location.hash);

document.documentElement.classList.add('js');
const targets = document.querySelectorAll('main > section .band-head, main > .closing h2');
targets.forEach(el => el.classList.add('reveal'));
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  targets.forEach(el => io.observe(el));
} else {
  targets.forEach(el => el.classList.add('in'));
}

// Intro: remove the overlay when it has lifted (or on skip), and remember it for this session.
(function () {
  const root = document.documentElement;
  if (!root.classList.contains('intro-on')) return;
  const el = document.getElementById('intro');
  let ended = false;
  function end() {
    if (ended) return; ended = true;
    root.classList.remove('intro-on');
    if (el) el.remove();
  }
  setTimeout(end, 7100);
  document.getElementById('introSkip').addEventListener('click', end);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') end(); });
})();
