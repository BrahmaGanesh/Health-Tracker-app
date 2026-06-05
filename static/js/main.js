/* ============================================================
   ADAPTIVE HEALTH MANAGEMENT PLATFORM
   main.js — Global JavaScript
   ============================================================ */

'use strict';

// ════════════════════════════════════════════════════════════
// CSRF TOKEN HELPER
// ════════════════════════════════════════════════════════════

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.content;
  const inp = document.querySelector('input[name="csrf_token"]');
  return inp ? inp.value : '';
}


// ════════════════════════════════════════════════════════════
// TOAST NOTIFICATION SYSTEM
// ════════════════════════════════════════════════════════════

const Toast = {
  container: null,

  init() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', duration = 4000) {
    this.init();

    const icons = {
      success: '✅',
      danger:  '⚠️',
      warning: '🟡',
      info:    'ℹ️'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span style="font-size:16px;flex-shrink:0;">${icons[type] || 'ℹ️'}</span>
      <span style="flex:1;">${message}</span>
      <button onclick="this.parentElement.remove()"
              style="background:none;border:none;cursor:pointer;font-size:14px;color:var(--text-muted);flex-shrink:0;">✕</button>
    `;

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      toast.style.opacity    = '0';
      toast.style.transform  = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg)   { this.show(msg, 'danger');  },
  warning(msg) { this.show(msg, 'warning'); },
  info(msg)    { this.show(msg, 'info');    },
};


// ════════════════════════════════════════════════════════════
// DARK MODE
// ════════════════════════════════════════════════════════════

const DarkMode = {
  async toggle() {
    try {
      const resp = await fetch('/auth/toggle-dark-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken':   getCsrfToken()
        }
      });
      const data = await resp.json();
      if (data.success) {
        this.apply(data.dark_mode);
      }
    } catch (e) {
      // Fallback: toggle locally
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      this.apply(!isDark);
    }
  },

  apply(isDark) {
    const html   = document.documentElement;
    const toggle = document.getElementById('darkToggle');
    const thumb  = toggle?.querySelector('.dark-toggle-thumb');

    if (isDark) {
      html.setAttribute('data-theme', 'dark');
      toggle?.classList.add('on');
      if (thumb) thumb.textContent = '🌙';
    } else {
      html.setAttribute('data-theme', 'light');
      toggle?.classList.remove('on');
      if (thumb) thumb.textContent = '☀️';
    }

    // Persist locally for instant load next time
    localStorage.setItem('darkMode', isDark ? '1' : '0');
  },

  init() {
    // Apply saved preference immediately to prevent flash
    const saved = localStorage.getItem('darkMode');
    if (saved === '1') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  }
};

// Apply dark mode before DOM paint
DarkMode.init();

// Global toggle function (called from base.html button)
function toggleDarkMode() {
  DarkMode.toggle();
}


// ════════════════════════════════════════════════════════════
// SIDEBAR
// ════════════════════════════════════════════════════════════

const Sidebar = {
  toggle() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;

    const isMobile = window.innerWidth <= 1024;

    if (isMobile) {
      sidebar.classList.toggle('mobile-open');
      overlay?.classList.toggle('active');
    } else {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    }
  },

  close() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar?.classList.remove('mobile-open');
    overlay?.classList.remove('active');
  },

  init() {
    const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (collapsed && window.innerWidth > 1024) {
      document.getElementById('sidebar')?.classList.add('collapsed');
    }

    // Close sidebar on escape
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') this.close();
    });
  }
};

// Global functions (called from base.html)
function toggleSidebar() { Sidebar.toggle(); }
function closeSidebar()  { Sidebar.close();  }


// ════════════════════════════════════════════════════════════
// SCROLL ANIMATIONS
// ════════════════════════════════════════════════════════════

const ScrollAnimator = {
  observer: null,

  init() {
    if (!('IntersectionObserver' in window)) return;

    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.style.opacity    = '1';
            entry.target.style.transform  = 'translateY(0)';
            this.observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: '0px 0px -30px 0px' }
    );

    document.querySelectorAll('.animate-on-scroll').forEach(el => {
      el.style.opacity    = '0';
      el.style.transform  = 'translateY(22px)';
      el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      this.observer.observe(el);
    });
  }
};


// ════════════════════════════════════════════════════════════
// PROGRESS BAR ANIMATIONS
// ════════════════════════════════════════════════════════════

const ProgressAnimator = {
  init() {
    if (!('IntersectionObserver' in window)) {
      this.animate();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const fill = entry.target;
            const target = fill.getAttribute('data-target') || fill.style.width;
            fill.style.width = '0%';
            requestAnimationFrame(() => {
              setTimeout(() => { fill.style.width = target; }, 100);
            });
            observer.unobserve(fill);
          }
        });
      },
      { threshold: 0.1 }
    );

    document.querySelectorAll('.prog-fill').forEach(el => {
      const w = el.style.width;
      if (w && w !== '0%') {
        el.setAttribute('data-target', w);
        el.style.width = '0%';
        observer.observe(el);
      }
    });
  },

  animate() {
    document.querySelectorAll('.prog-fill[data-target]').forEach(el => {
      el.style.width = el.getAttribute('data-target');
    });
  }
};


// ════════════════════════════════════════════════════════════
// GLOBAL SEARCH
// ════════════════════════════════════════════════════════════

const GlobalSearch = {
  init() {
    const input = document.getElementById('globalSearch');
    if (!input) return;

    // Focus on / key
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        input.focus();
        input.select();
      }
      if (e.key === 'Escape' && document.activeElement === input) {
        input.blur();
        input.value = '';
      }
    });

    // Navigate on Enter
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && input.value.trim()) {
        window.location.href = `/meal/recipes?search=${encodeURIComponent(input.value.trim())}`;
      }
    });
  }
};


// ════════════════════════════════════════════════════════════
// AUTO-DISMISS FLASH MESSAGES
// ════════════════════════════════════════════════════════════

function initFlashMessages() {
  document.querySelectorAll('.alert-banner').forEach((el, i) => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s ease, transform 0.4s ease, max-height 0.4s ease';
      el.style.opacity    = '0';
      el.style.transform  = 'translateY(-8px)';
      el.style.maxHeight  = '0';
      el.style.overflow   = 'hidden';
      el.style.padding    = '0';
      el.style.margin     = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000 + i * 300);
  });
}


// ════════════════════════════════════════════════════════════
// CONFIRM DELETE UTILITY
// ════════════════════════════════════════════════════════════

function confirmDelete(message, href) {
  if (confirm(message || 'Are you sure you want to delete this?')) {
    window.location.href = href;
  }
}


// ════════════════════════════════════════════════════════════
// AJAX HELPER
// ════════════════════════════════════════════════════════════

async function httpPost(url, data = {}) {
  const resp = await fetch(url, {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken':   getCsrfToken()
    },
    body: JSON.stringify(data)
  });
  return resp.json();
}

async function httpGet(url) {
  const resp = await fetch(url, {
    headers: { 'X-CSRFToken': getCsrfToken() }
  });
  return resp.json();
}


// ════════════════════════════════════════════════════════════
// COUNTER ANIMATION (for stat numbers)
// ════════════════════════════════════════════════════════════

function animateCounter(el, target, duration = 1000) {
  const start     = performance.now();
  const startVal  = parseFloat(el.textContent) || 0;
  const isFloat   = String(target).includes('.');
  const decimals  = isFloat ? (String(target).split('.')[1]?.length || 1) : 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased    = 1 - Math.pow(1 - progress, 3);  // ease-out-cubic
    const current  = startVal + (target - startVal) * eased;

    el.textContent = isFloat
      ? current.toFixed(decimals)
      : Math.round(current).toString();

    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

function initCounters() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el     = entry.target;
          const target = parseFloat(el.getAttribute('data-count'));
          if (!isNaN(target)) {
            animateCounter(el, target);
            observer.unobserve(el);
          }
        }
      });
    },
    { threshold: 0.3 }
  );

  document.querySelectorAll('[data-count]').forEach(el => {
    observer.observe(el);
  });
}


// ════════════════════════════════════════════════════════════
// PAGE LOADER
// ════════════════════════════════════════════════════════════

function hidePageLoader() {
  const loader = document.getElementById('pageLoader');
  if (loader) {
    loader.classList.add('hidden');
    setTimeout(() => loader.remove(), 400);
  }
}


// ════════════════════════════════════════════════════════════
// ACTIVE NAV ITEM DETECTION
// ════════════════════════════════════════════════════════════

function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      item.classList.add('active');
    }
  });
}


// ════════════════════════════════════════════════════════════
// DOM READY — INIT ALL
// ════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  // Core
  Sidebar.init();
  GlobalSearch.init();
  initFlashMessages();

  // Animations
  ScrollAnimator.init();
  ProgressAnimator.init();
  initCounters();

  // Hide loader
  hidePageLoader();
});

// Fallback: hide loader after window fully loads
window.addEventListener('load', hidePageLoader);