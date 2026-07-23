export function initTilt(selector, opts) {
  var config = Object.assign({ max: 8, scale: 1.02, perspective: 800 }, opts);
  var els = document.querySelectorAll(selector);
  els.forEach(function (el) {
    el.addEventListener('mousemove', function (e) {
      var rect = el.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;
      var cx = rect.width / 2;
      var cy = rect.height / 2;
      var rotX = ((y - cy) / cy) * -config.max;
      var rotY = ((x - cx) / cx) * config.max;
      el.style.transform = 'perspective(' + config.perspective + 'px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) scale' + (config.scale !== 1 ? '(' + config.scale + ')' : '');
    });
    el.addEventListener('mouseleave', function () {
      el.style.transform = '';
    });
  });
}

export function initFloating(selector) {
  var els = document.querySelectorAll(selector);
  els.forEach(function (el, i) {
    var duration = 4 + (i % 3) * 2;
    var delay = (i * 0.8) % 4;
    el.style.setProperty('--float-duration', duration + 's');
    el.style.setProperty('--float-delay', delay + 's');
  });
}
