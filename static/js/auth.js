/* auth.js — Form validation for signup and login */
'use strict';

document.addEventListener('DOMContentLoaded', function () {

  // ── Password visibility toggles ──────────────────────────
  document.querySelectorAll('.password-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;
      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      this.querySelector('i').className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
  });

  // ── Sign-up form ─────────────────────────────────────────
  const signupForm = document.getElementById('signupForm');
  if (signupForm) {
    signupForm.addEventListener('submit', function (e) {
      let valid = true;

      // Required text fields
      ['first_name', 'last_name', 'email'].forEach(function (id) {
        const el = document.getElementById(id);
        if (!el) return;
        if (!el.value.trim()) {
          el.classList.add('is-invalid');
          valid = false;
        } else {
          el.classList.remove('is-invalid');
        }
      });

      // Email format
      const emailEl = document.getElementById('email');
      if (emailEl && emailEl.value && !emailEl.value.includes('@')) {
        emailEl.classList.add('is-invalid');
        valid = false;
      }

      // Password length
      const pw = document.getElementById('password');
      if (pw && pw.value.length < 8) {
        pw.classList.add('is-invalid');
        valid = false;
      } else if (pw) {
        pw.classList.remove('is-invalid');
      }

      // Confirm password match
      const pw2 = document.getElementById('confirm_password');
      const feedback = document.getElementById('confirmFeedback');
      if (pw && pw2) {
        if (pw.value !== pw2.value) {
          pw2.classList.add('is-invalid');
          if (feedback) feedback.textContent = 'Passwords do not match.';
          valid = false;
        } else {
          pw2.classList.remove('is-invalid');
        }
      }

      if (!valid) {
        e.preventDefault();
        // Scroll to first error
        const first = signupForm.querySelector('.is-invalid');
        if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        // Disable submit button to prevent double submission
        const btn = document.getElementById('signupBtn');
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating account…';
        }
      }
    });

    // Live validation on blur
    signupForm.querySelectorAll('input[required]').forEach(function (input) {
      input.addEventListener('blur', function () {
        if (!this.value.trim()) {
          this.classList.add('is-invalid');
        } else {
          this.classList.remove('is-invalid');
        }
      });
    });
  }

  // ── Login form ───────────────────────────────────────────
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      let valid = true;
      ['email', 'password'].forEach(function (id) {
        const el = document.getElementById(id);
        if (!el) return;
        if (!el.value.trim()) {
          el.classList.add('is-invalid');
          valid = false;
        } else {
          el.classList.remove('is-invalid');
        }
      });
      if (!valid) e.preventDefault();
    });
  }

});
