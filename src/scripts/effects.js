/* ── 3D Tilt ── */
export function initTilt(selector, opts) {
  if (matchMedia('(pointer: coarse)').matches) return;
  var config = Object.assign({ max: 12, scale: 1.03, perspective: 600 }, opts);
  var els = document.querySelectorAll(selector);
  var raf = null;
  els.forEach(function (el) {
    el.addEventListener('mousemove', function (e) {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () {
        var rect = el.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        var cx = rect.width / 2;
        var cy = rect.height / 2;
        var rotX = ((y - cy) / cy) * -config.max;
        var rotY = ((x - cx) / cx) * config.max;
        el.style.transform = 'perspective(' + config.perspective + 'px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) scale' + (config.scale !== 1 ? '(' + config.scale + ')' : '');
      });
    });
    el.addEventListener('mouseleave', function () {
      el.style.transform = '';
    });
  });
}

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

/* ── Cursor Glow ── */
export function initCursorGlow() {
  if (matchMedia('(pointer: coarse)').matches || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var el = document.createElement('div');
  el.id = 'fd-cursor-glow';
  document.body.appendChild(el);
  var raf = null;
  var ticking = false;
  document.addEventListener('mousemove', function (e) {
    if (!ticking) {
      ticking = true;
      raf = requestAnimationFrame(function () {
        el.style.transform = 'translate(' + (e.clientX) + 'px, ' + (e.clientY) + 'px) translate(-50%, -50%)';
        ticking = false;
      });
    }
  });
  document.addEventListener('mouseleave', function () {
    el.style.opacity = '0';
  });
  document.addEventListener('mouseenter', function () {
    el.style.opacity = '1';
  });
}

/* ── Particle Background ── */
export function initParticles(canvasId, opts) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var isMobile = matchMedia('(max-width: 768px)').matches;
  var config = Object.assign({
    count: isMobile ? 20 : 40,
    color: '37, 99, 235',
    maxSpeed: isMobile ? 0.2 : 0.4,
    radius: isMobile ? 1.2 : 1.8
  }, opts);

  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var particles = [];
  var w, h;

  function resize() {
    w = canvas.width = canvas.offsetWidth;
    h = canvas.height = canvas.offsetHeight;
  }

  function createParticle() {
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * config.maxSpeed * 2,
      vy: (Math.random() - 0.5) * config.maxSpeed * 2,
      r: config.radius + Math.random() * 0.8
    };
  }

  function init() {
    resize();
    particles = [];
    for (var i = 0; i < config.count; i++) particles.push(createParticle());
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(' + config.color + ', 0.35)';
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }

  init();
  window.addEventListener('resize', init);
  draw();
}


