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
