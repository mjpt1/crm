/**
 * CRM Application — core JavaScript utilities.
 */

const CRM = (() => {
  const API_BASE = '/api/v1';

  // ── Token management ─────────────────────────────────────────────────────
  function getToken() {
    return localStorage.getItem('access_token');
  }

  function getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  // ── Authenticated fetch with auto-refresh ────────────────────────────────
  async function apiFetch(path, options = {}) {
    const token = getToken();
    const method = (options.method || 'GET').toUpperCase();
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    // Always include CSRF for unsafe methods (needed for SessionAuthentication)
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      const csrf = getCsrfToken();
      if (csrf) headers['X-CSRFToken'] = csrf;
    }

    let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    // Attempt token refresh on 401 (only for JWT users)
    if (res.status === 401 && token) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${getToken()}`;
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } else {
        clearTokens();
        window.location.href = '/login/';
        return null;
      }
    }
    return res;
  }

  async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('access_token', data.access);
        return true;
      }
    } catch (e) {
      console.error('Token refresh failed:', e);
    }
    return false;
  }

  // ── UI Helpers ────────────────────────────────────────────────────────────
  function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container') || (() => {
      const el = document.createElement('div');
      el.id = 'toast-container';
      el.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      el.style.zIndex = '9999';
      document.body.appendChild(el);
      return el;
    })();

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0 show`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    container.appendChild(toastEl);
    setTimeout(() => toastEl.remove(), 4000);
  }

  function formatCurrency(amount) {
    return new Intl.NumberFormat('fa-IR').format(amount) + ' تومان';
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      if (Number.isNaN(d.getTime())) return '—';

      const jLib = window.jalaali || (typeof jalaali !== 'undefined' ? jalaali : null);
      if (jLib) {
        const j = jLib.toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate());
        const months = [
          'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
          'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
        ];
        const toFa = (n) => String(n).replace(/\d/g, (x) => '۰۱۲۳۴۵۶۷۸۹'[Number(x)]);
        return `${toFa(String(j.jd).padStart(2, '0'))} ${months[j.jm - 1]} ${toFa(j.jy)}`;
      }

      return d.toLocaleDateString('fa-IR-u-ca-persian', {
        day: '2-digit', month: 'long', year: 'numeric',
      });
    } catch (e) {
      return '—';
    }
  }

  // ── Jalali → ISO (YYYY-MM-DD) ─────────────────────────────────────────────
  function toISO(jalaliStr) {
    if (!jalaliStr || !jalaliStr.trim()) return '';
    // نرمال‌سازی اعداد فارسی به لاتین و جداکننده‌ها
    const s = jalaliStr.trim()
      .replace(/[۰-۹]/g, d => String.fromCharCode(d.charCodeAt(0) - 1728))
      .replace(/[-\.]/g, '/');
    const parts = s.split('/');
    if (parts.length !== 3) return '';
    const [jy, jm, jd] = parts.map(Number);
    if (!jy || !jm || !jd || jm > 12 || jd > 31) return '';
    try {
      const g = window.jalaali ? window.jalaali.toGregorian(jy, jm, jd)
                               : jalaali.toGregorian(jy, jm, jd);
      return `${g.gy}-${String(g.gm).padStart(2,'0')}-${String(g.gd).padStart(2,'0')}`;
    } catch (e) { return ''; }
  }

  function statusBadge(status, prefix = '') {
    const labels = {
      // وضعیت سرنخ
      new: ['جدید', 'info'],
      contacted: ['تماس‌گرفته‌شده', 'warning'],
      qualified: ['واجد شرایط', 'primary'],
      negotiation: ['در مذاکره', 'warning'],
      won: ['برنده', 'success'],
      lost: ['از دست‌رفته', 'danger'],
      // وضعیت فاکتور
      draft: ['پیش‌نویس', 'secondary'],
      pending_approval: ['در انتظار تایید', 'warning'],
      approved: ['تایید شده', 'primary'],
      paid: ['پرداخت‌شده', 'success'],
      partially_paid: ['پرداخت جزئی', 'info'],
      cancelled: ['لغو شده', 'danger'],
      overdue: ['معوق', 'danger'],
      refunded: ['بازگشت وجه', 'dark'],
      // وضعیت مرخصی
      pending: ['در انتظار', 'warning'],
      rejected: ['رد شده', 'danger'],
      // وضعیت پرداخت آنلاین
      initiated: ['در انتظار پرداخت', 'info'],
      verified: ['موفق', 'success'],
      success: ['موفق', 'success'],
      failed: ['ناموفق', 'danger'],
      // وضعیت تماس
      answered: ['پاسخ داده شده', 'success'],
      missed: ['بی‌پاسخ', 'danger'],
      busy: ['مشغول', 'warning'],
      no_answer: ['عدم پاسخ', 'secondary'],
      dialing: ['در حال شماره‌گیری', 'info'],
    };
    const [label, color] = labels[status] || [status, 'secondary'];
    return `<span class="badge bg-${color}">${label}</span>`;
  }

  // Public API
  return { apiFetch, showToast, formatCurrency, formatDate, statusBadge, toISO };
})();

// ── CSRF Token helper for Django template-based forms ────────────────────────
function getCsrfToken() {
  const name = 'csrftoken';
  const cookies = document.cookie.split(';');
  for (const c of cookies) {
    const [key, val] = c.trim().split('=');
    if (key === name) return decodeURIComponent(val);
  }
  return '';
}
