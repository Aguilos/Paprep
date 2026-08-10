/* symptom_checker.js — Symptom selection and DSS results */
'use strict';

(function () {

  const CSRF_TOKEN = (document.getElementById('csrfToken') || {}).dataset.token || '';

  let selectedIds = new Set();

  const checkBtn = document.getElementById('checkSymptomsBtn');
  const clearBtn = document.getElementById('clearAllBtn');
  const countEl = document.getElementById('selectedCount');
  const resultsContent = document.getElementById('resultsContent');
  const resultsPlaceholder = document.getElementById('resultsPlaceholder');

  // ── Symptom checkbox handling ─────────────────────────────
  document.querySelectorAll('.symptom-item').forEach(function (item) {
    item.addEventListener('click', function () {
      const checkbox = this.querySelector('.symptom-checkbox');
      if (!checkbox) return;
      checkbox.checked = !checkbox.checked;
      const id = parseInt(checkbox.value, 10);
      if (checkbox.checked) {
        selectedIds.add(id);
        this.classList.add('selected');
      } else {
        selectedIds.delete(id);
        this.classList.remove('selected');
      }
      updateCount();
    });
  });

  function updateCount() {
    const n = selectedIds.size;
    if (countEl) {
      countEl.textContent = n + ' symptom' + (n !== 1 ? 's' : '') + ' selected';
    }
    if (checkBtn) {
      checkBtn.disabled = n === 0;
    }
  }

  // ── Clear all ────────────────────────────────────────────
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      selectedIds.clear();
      document.querySelectorAll('.symptom-item').forEach(function (item) {
        item.classList.remove('selected');
        const cb = item.querySelector('.symptom-checkbox');
        if (cb) cb.checked = false;
      });
      updateCount();
      showPlaceholder();
    });
  }

  // ── Check symptoms ───────────────────────────────────────
  if (checkBtn) {
    checkBtn.addEventListener('click', function () {
      if (selectedIds.size === 0) return;
      checkBtn.disabled = true;
      checkBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Analysing…';

      fetch('/api/symptoms/check', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({ symptom_ids: Array.from(selectedIds) })
      })
        .then(function (r) {
          if (!r.ok) throw new Error('Server error: ' + r.status);
          return r.json();
        })
        .then(function (data) {
          renderResults(data);
        })
        .catch(function (err) {
          showError('Unable to retrieve recommendations. Please try again.');
          console.error(err);
        })
        .finally(function () {
          checkBtn.disabled = false;
          checkBtn.innerHTML = '<i class="bi bi-search-heart me-2"></i>Check Symptoms';
        });
    });
  }

  // ── Render Results ───────────────────────────────────────
  function renderResults(data) {
    if (!resultsContent) return;

    const severity = data.severity || 'low';
    const recs = data.recommendations || [];
    const disclaimer = data.disclaimer || '';

    const severityLabels = {
      emergency: '🚨 EMERGENCY',
      high: '⚠️ High Priority',
      medium: '⚡ Monitor Closely',
      low: '✅ General Care'
    };

    let html = '<div class="rec-header">';
    html += '<span class="severity-badge severity-' + severity + '">';
    html += (severityLabels[severity] || 'Results') + '</span>';
    html += '<div class="text-muted small mt-1">';
    html += data.symptom_count + ' symptom' + (data.symptom_count !== 1 ? 's' : '') + ' analysed';
    html += '</div></div>';

    recs.forEach(function (rec) {
      const type = rec.type || 'info';
      html += '<div class="rec-card rec-card--' + type + '">';
      html += '<div class="rec-card-header">';
      html += getRecIcon(type);
      html += ' ' + escHtml(rec.title);
      html += '</div>';
      html += '<div class="rec-card-body">';
      html += '<p class="mb-0">' + escHtml(rec.content) + '</p>';
      html += '</div>';
      if (rec.actions && rec.actions.length) {
        html += '<ul class="rec-actions">';
        rec.actions.forEach(function (action) {
          html += '<li>' + escHtml(action) + '</li>';
        });
        html += '</ul>';
      }
      html += '</div>';
    });

    // Disclaimer (always shown)
    if (disclaimer) {
      html += '<div class="rec-disclaimer">';
      html += '<strong>⚠️ Medical Disclaimer:</strong> ';
      html += escHtml(disclaimer);
      html += '</div>';
    }

    resultsContent.innerHTML = html;
    resultsContent.style.display = 'block';
    if (resultsPlaceholder) resultsPlaceholder.style.display = 'none';

    // Scroll results into view on mobile
    if (window.innerWidth < 992) {
      resultsContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function showPlaceholder() {
    if (resultsContent) resultsContent.style.display = 'none';
    if (resultsPlaceholder) resultsPlaceholder.style.display = 'flex';
  }

  function showError(msg) {
    if (!resultsContent) return;
    resultsContent.innerHTML =
      '<div class="p-4"><div class="alert alert-danger">' +
      '<i class="bi bi-exclamation-circle-fill me-2"></i>' + escHtml(msg) +
      '</div></div>';
    resultsContent.style.display = 'block';
    if (resultsPlaceholder) resultsPlaceholder.style.display = 'none';
  }

  function getRecIcon(type) {
    const icons = {
      emergency: '<i class="bi bi-exclamation-octagon-fill"></i>',
      danger: '<i class="bi bi-exclamation-triangle-fill"></i>',
      warning: '<i class="bi bi-exclamation-circle-fill"></i>',
      info: '<i class="bi bi-info-circle-fill"></i>'
    };
    return icons[type] || icons.info;
  }

  function escHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

})();
