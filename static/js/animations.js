/* ============================================================
   ADAPTIVE HEALTH MANAGEMENT PLATFORM
   animations.js — Smooth Animations (No External Library)
   Uses Web Animations API + CSS custom properties
   ============================================================ */

'use strict';

// ════════════════════════════════════════════════════════════
// ANIMATION UTILITIES
// ════════════════════════════════════════════════════════════

const Anim = {

  // ── Fade up entrance ──────────────────────────────────────
  fadeUp(el, options = {}) {
    const { delay = 0, duration = 400, distance = 20 } = options;
    return el.animate([
      { opacity: 0, transform: `translateY(${distance}px)` },
      { opacity: 1, transform: 'translateY(0)' }
    ], {
      duration,
      delay,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      fill: 'both'
    });
  },

  // ── Fade in ───────────────────────────────────────────────
  fadeIn(el, options = {}) {
    const { delay = 0, duration = 300 } = options;
    return el.animate([
      { opacity: 0 },
      { opacity: 1 }
    ], { duration, delay, easing: 'ease', fill: 'both' });
  },

  // ── Scale pop ─────────────────────────────────────────────
  scalePop(el, options = {}) {
    const { delay = 0, duration = 350 } = options;
    return el.animate([
      { opacity: 0, transform: 'scale(0.85)' },
      { opacity: 1, transform: 'scale(1)' }
    ], {
      duration,
      delay,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      fill: 'both'
    });
  },

  // ── Slide in from left ────────────────────────────────────
  slideInLeft(el, options = {}) {
    const { delay = 0, duration = 400 } = options;
    return el.animate([
      { opacity: 0, transform: 'translateX(-24px)' },
      { opacity: 1, transform: 'translateX(0)' }
    ], {
      duration, delay,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      fill: 'both'
    });
  },

  // ── Stagger a list of elements ────────────────────────────
  stagger(elements, animFn, staggerMs = 60) {
    elements.forEach((el, i) => {
      animFn(el, { delay: i * staggerMs });
    });
  },

  // ── Shake (for validation errors) ────────────────────────
  shake(el) {
    el.animate([
      { transform: 'translateX(0)' },
      { transform: 'translateX(-6px)' },
      { transform: 'translateX(6px)' },
      { transform: 'translateX(-4px)' },
      { transform: 'translateX(4px)' },
      { transform: 'translateX(0)' },
    ], { duration: 400, easing: 'ease' });
  },

  // ── Pulse (for important elements) ───────────────────────
  pulse(el, count = 2) {
    el.animate([
      { transform: 'scale(1)',    opacity: 1 },
      { transform: 'scale(1.05)', opacity: 0.85 },
      { transform: 'scale(1)',    opacity: 1 },
    ], { duration: 600, iterations: count, easing: 'ease-in-out' });
  },

  // ── Bounce checkmark (for completed actions) ─────────────
  bounceIn(el) {
    el.animate([
      { transform: 'scale(0)',   opacity: 0 },
      { transform: 'scale(1.2)', opacity: 1 },
      { transform: 'scale(0.95)' },
      { transform: 'scale(1)' },
    ], {
      duration: 500,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      fill: 'forwards'
    });
  },

  // ── Number count-up ───────────────────────────────────────
  countUp(el, targetVal, duration = 1200) {
    const start     = performance.now();
    const startVal  = 0;
    const isFloat   = String(targetVal).includes('.');
    const decimals  = isFloat ? 1 : 0;

    function step(now) {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased    = 1 - Math.pow(1 - progress, 3);
      const current  = startVal + (targetVal - startVal) * eased;

      el.textContent = isFloat
        ? current.toFixed(decimals)
        : Math.round(current).toString();

      if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
  },

  // ── Progress bar fill animation ───────────────────────────
  fillBar(el, targetPct, duration = 1200) {
    el.style.width = '0%';
    setTimeout(() => {
      el.style.transition = `width ${duration}ms cubic-bezier(0.34, 1.56, 0.64, 1)`;
      el.style.width      = targetPct + '%';
    }, 50);
  },

};


// ════════════════════════════════════════════════════════════
// PAGE ENTRANCE ANIMATIONS
// Run once when DOM is ready, animate cards in sequence
// ════════════════════════════════════════════════════════════

function runPageEntrance() {
  // Stat cards
  const statCards = document.querySelectorAll(
    '.stat-card, .bp-stat-card, .metric-card'
  );
  Anim.stagger(Array.from(statCards), (el, opts) => Anim.fadeUp(el, opts), 60);

  // Hero section
  const hero = document.querySelector(
    '.bp-hero, .dash-hero, .nutri-hero, .grocery-hero, .recipes-hero'
  );
  if (hero) Anim.fadeIn(hero, { duration: 500 });

  // Charts
  document.querySelectorAll('.chart-card, .chart-outer').forEach((el, i) => {
    Anim.fadeUp(el, { delay: 150 + i * 80, duration: 500 });
  });

  // Insight items
  document.querySelectorAll('.insight-item').forEach((el, i) => {
    Anim.slideInLeft(el, { delay: 100 + i * 70 });
  });

  // Form cards
  document.querySelectorAll('.add-form-card, .form-card').forEach((el, i) => {
    Anim.fadeUp(el, { delay: 200 + i * 60 });
  });

  // Table rows
  document.querySelectorAll('.bp-table tbody tr, .data-table tbody tr').forEach((el, i) => {
    Anim.fadeIn(el, { delay: 50 + i * 30, duration: 250 });
  });
}


// ════════════════════════════════════════════════════════════
// MEAL SLOT COMPLETION ANIMATION
// Called when a meal is marked done
// ════════════════════════════════════════════════════════════

function animateMealDone(itemEl) {
  if (!itemEl) return;
  itemEl.animate([
    { backgroundColor: 'transparent' },
    { backgroundColor: 'rgba(97,179,144,0.15)' },
    { backgroundColor: 'transparent' },
  ], { duration: 800, easing: 'ease' });
}


// ════════════════════════════════════════════════════════════
// WATER GLASS FILL ANIMATION
// ════════════════════════════════════════════════════════════

function animateWaterGlass(glassEl) {
  glassEl.animate([
    { transform: 'scale(1)', opacity: 0.3 },
    { transform: 'scale(1.3)', opacity: 1 },
    { transform: 'scale(1)', opacity: 1 },
  ], {
    duration: 400,
    easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
  });
}


// ════════════════════════════════════════════════════════════
// MEDICINE TOGGLE ANIMATION
// ════════════════════════════════════════════════════════════

function animateMedicineTaken(toggleBtn) {
  if (!toggleBtn) return;
  const thumb = toggleBtn.querySelector('.med-toggle-thumb');
  if (thumb) {
    Anim.bounceIn(thumb);
  }
}


// ════════════════════════════════════════════════════════════
// FORM SUBMIT ANIMATION
// ════════════════════════════════════════════════════════════

function animateFormSubmit(btn, loadingText = '⏳ Saving...') {
  const orig = btn.innerHTML;
  btn.innerHTML = loadingText;
  btn.style.opacity = '0.75';
  btn.style.pointerEvents = 'none';
  return () => {
    btn.innerHTML = orig;
    btn.style.opacity = '1';
    btn.style.pointerEvents = 'auto';
  };
}


// ════════════════════════════════════════════════════════════
// CARD HOVER TILT EFFECT (optional, for recipe cards)
// ════════════════════════════════════════════════════════════

function initTiltCards() {
  document.querySelectorAll('.recipe-card[data-tilt]').forEach(card => {
    card.addEventListener('mousemove', e => {
      const rect    = card.getBoundingClientRect();
      const x       = e.clientX - rect.left;
      const y       = e.clientY - rect.top;
      const centerX = rect.width  / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -4;
      const rotateY = ((x - centerX) / centerX) *  4;

      card.style.transform = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
      card.style.transition = 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
    });
  });
}


// ════════════════════════════════════════════════════════════
// PROGRESS RING (SVG — for stat display)
// ════════════════════════════════════════════════════════════

function drawProgressRing(canvasId, percentage, color = '#61b390') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx    = canvas.getContext('2d');
  const size   = canvas.width;
  const cx     = size / 2;
  const cy     = size / 2;
  const radius = (size - 8) / 2;
  const start  = -Math.PI / 2;
  const pct    = Math.min(100, Math.max(0, percentage)) / 100;

  ctx.clearRect(0, 0, size, size);

  // Background ring
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(0,0,0,0.08)';
  ctx.lineWidth   = 8;
  ctx.stroke();

  // Foreground arc — animated
  let current = 0;
  const target = pct * Math.PI * 2;
  const step   = target / 40;

  function draw() {
    ctx.clearRect(0, 0, size, size);

    // bg ring
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(0,0,0,0.06)';
    ctx.lineWidth   = 8;
    ctx.stroke();

    // progress arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + current);
    ctx.strokeStyle = color;
    ctx.lineWidth   = 8;
    ctx.lineCap     = 'round';
    ctx.stroke();

    // center text
    ctx.fillStyle = 'var(--text-primary, #1a1f2e)';
    ctx.font      = `700 ${size * 0.22}px "DM Mono", monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`${Math.round(pct * current / target * percentage)}%`, cx, cy);

    if (current < target) {
      current = Math.min(current + step, target);
      requestAnimationFrame(draw);
    }
  }

  requestAnimationFrame(draw);
}


// ════════════════════════════════════════════════════════════
// INIT ON DOM READY
// ════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  // Entrance animations — run after slight delay to avoid jank
  setTimeout(runPageEntrance, 100);

  // Optional: tilt on recipe cards
  initTiltCards();
});


// ════════════════════════════════════════════════════════════
// EXPORT GLOBALS
// ════════════════════════════════════════════════════════════

window.Anim               = Anim;
window.animateMealDone    = animateMealDone;
window.animateWaterGlass  = animateWaterGlass;
window.animateMedicineTaken = animateMedicineTaken;
window.animateFormSubmit  = animateFormSubmit;
window.drawProgressRing   = drawProgressRing;