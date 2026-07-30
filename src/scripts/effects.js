/* ── Floating ── */
export function initFloating(selector) {
  var els = document.querySelectorAll(selector);
  els.forEach(function (el, i) {
    var duration = 4 + (i % 3) * 2;
    var delay = (i * 0.8) % 4;
    el.style.setProperty('--float-duration', duration + 's');
    el.style.setProperty('--float-delay', delay + 's');
  });
}

/* ── Scroll Reveal ── */
export function initReveal() {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale').forEach(function (el) {
      el.classList.add('revealed');
    });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale').forEach(function (el) {
    observer.observe(el);
  });
}

/* ── Animated Counter ── */
export function initCounters() {
  if (!('IntersectionObserver' in window)) return;
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('[data-count-to]').forEach(function (el) {
    observer.observe(el);
  });
}

function animateCounter(el) {
  var target = parseFloat(el.getAttribute('data-count-to'));
  var suffix = el.getAttribute('data-count-suffix') || '';
  var prefix = el.getAttribute('data-count-prefix') || '';
  var duration = parseInt(el.getAttribute('data-count-duration')) || 1500;
  var start = performance.now();

  function step(now) {
    var elapsed = now - start;
    var progress = Math.min(elapsed / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    var current = eased * target;
    el.textContent = prefix + formatNumber(current) + suffix;
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = prefix + formatNumber(target) + suffix;
  }
  requestAnimationFrame(step);
}

function formatNumber(n) {
  if (Number.isInteger(n)) return n.toString();
  return n.toFixed(1);
}



