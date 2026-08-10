/* map.js — Clinic Locator with Leaflet + OpenStreetMap */
'use strict';

(function () {

  // Clinic data injected by the template
  const ALL_CLINICS = window.CLINICS_DATA || [];

  // Siniloan / Santa Maria, Laguna centre
  const DEFAULT_CENTER = [14.450, 121.443];
  const DEFAULT_ZOOM = 13;

  let map;
  let markers = {};   // clinic.id -> L.Marker
  let activeClinicId = null;

  // ── Initialise Map ───────────────────────────────────────
  function initMap() {
    map = L.map('clinicMap', {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(map);

    // Try geolocation to centre on user
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (pos) {
        map.setView([pos.coords.latitude, pos.coords.longitude], 12);
      }, null, { timeout: 5000 });
    }

    renderClinics(ALL_CLINICS);

    // Force Leaflet to recalculate size after layout settles
    setTimeout(function () { map.invalidateSize(); }, 200);
  }

  // ── Custom Marker Icons ──────────────────────────────────
  function makeIcon(acceptsSN, hasAnnouncement) {
    const color = acceptsSN ? '#9B59B6' : '#4E97D9';
    const badge = hasAnnouncement
      ? `<circle cx="28" cy="6" r="7" fill="#FF6B35" stroke="white" stroke-width="2"/>
         <text x="28" y="10" text-anchor="middle" fill="white" font-size="9" font-family="Arial" font-weight="bold">!</text>`
      : '';
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="36" height="42" viewBox="0 0 36 42">
        <path d="M16 0C7.163 0 0 7.163 0 16c0 9.941 12.706 22.672 15.317 25.186a.944.944 0 0 0 1.366 0C19.294 38.672 32 25.94 32 16 32 7.163 24.837 0 16 0z"
              fill="${color}"/>
        <text x="16" y="22" text-anchor="middle" fill="white" font-size="14" font-family="Arial" font-weight="bold">+</text>
        ${badge}
      </svg>`;
    return L.divIcon({
      html: svg,
      className: '',
      iconSize: [36, 42],
      iconAnchor: [16, 42],
      popupAnchor: [0, -44]
    });
  }

  // ── Render Clinics ───────────────────────────────────────
  function renderClinics(clinics) {
    // Clear existing markers
    Object.values(markers).forEach(function (m) { m.remove(); });
    markers = {};

    renderList(clinics);

    clinics.forEach(function (c) {
      if (!c.latitude || !c.longitude) return;

      const marker = L.marker([c.latitude, c.longitude], {
        icon: makeIcon(c.accepts_special_needs, c.has_announcement)
      }).addTo(map);

      const typeLabel = c.clinic_type
        ? c.clinic_type.charAt(0).toUpperCase() + c.clinic_type.slice(1)
        : 'Clinic';
      const snLabel = c.accepts_special_needs
        ? '<span style="color:#9B59B6;font-weight:700;">⭐ Accepts Special Needs</span><br>'
        : '';
      const annLabel = c.has_announcement && c.announcement_preview
        ? `<div style="margin:6px 0 4px;padding:6px 8px;background:#fff3ee;border-left:3px solid #FF6B35;border-radius:4px;font-size:.8rem;"><span style="color:#FF6B35;">📢</span> <strong>${escHtml(c.announcement_preview)}</strong></div>`
        : '';

      marker.bindPopup(`
        <div style="min-width:200px; font-family:'Segoe UI',sans-serif;">
          <strong style="font-size:1rem;">${escHtml(c.name)}</strong><br>
          <small style="color:#718096;">${escHtml(typeLabel)}</small><br>
          ${snLabel}
          ${annLabel}
          <small>${escHtml(c.address || '')}</small><br>
          ${c.phone ? '<small><a href="tel:' + escHtml(c.phone) + '">' + escHtml(c.phone) + '</a></small><br>' : ''}
          <a href="/clinics/${c.id}" style="color:#4E97D9;font-weight:700;font-size:.85rem;">
            View Details &amp; Availability →
          </a>
        </div>
      `);

      marker.on('click', function () {
        highlightListItem(c.id);
        activeClinicId = c.id;
      });

      markers[c.id] = marker;
    });

    updateCount(clinics.length);
  }

  // ── Render List Panel ────────────────────────────────────
  function renderList(clinics) {
    const listEl = document.getElementById('clinicList');
    const loadingEl = document.getElementById('clinicListLoading');
    if (!listEl) return;

    if (loadingEl) loadingEl.remove();

    if (clinics.length === 0) {
      listEl.innerHTML =
        '<div class="text-center py-5 text-muted"><i class="bi bi-geo-alt fs-2"></i><p class="mt-2">No clinics found</p></div>';
      return;
    }

    listEl.innerHTML = clinics.map(function (c) {
      const typeLabel = c.clinic_type || 'general';
      return `
        <div class="clinic-card" data-id="${c.id}" onclick="focusClinic(${c.id})">
          <div class="clinic-card-name">${escHtml(c.name)}</div>
          <div class="clinic-card-city">
            <i class="bi bi-geo-alt me-1"></i>${escHtml(c.city || c.address || '')}
          </div>
          <div class="clinic-card-badges mt-1">
            <span class="badge-type badge-type--${escHtml(typeLabel)}">${escHtml(typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1))}</span>
            ${c.accepts_special_needs ? '<span class="badge-sn-sm"><i class="bi bi-person-heart me-1"></i>SN Friendly</span>' : ''}
            ${c.has_announcement ? '<span style="background:#FF6B35;color:#fff;font-size:10px;padding:2px 7px;border-radius:20px;font-weight:700;"><i class="bi bi-megaphone-fill me-1"></i>Announcement</span>' : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // ── Focus on a clinic (from list click) ─────────────────
  window.focusClinic = function (id) {
    const marker = markers[id];
    if (marker) {
      map.flyTo(marker.getLatLng(), 15, { duration: 1 });
      marker.openPopup();
    }
    highlightListItem(id);
    activeClinicId = id;
  };

  function highlightListItem(id) {
    document.querySelectorAll('.clinic-card').forEach(function (card) {
      card.classList.toggle('active', parseInt(card.dataset.id, 10) === id);
    });
    const card = document.querySelector('.clinic-card[data-id="' + id + '"]');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function updateCount(n) {
    const el = document.getElementById('clinicCount');
    if (el) el.textContent = n + ' clinic' + (n !== 1 ? 's' : '') + ' shown';
  }

  // ── Filtering ────────────────────────────────────────────
  function getFiltered() {
    const q = (document.getElementById('clinicSearch') || {}).value || '';
    const typeFilter = (document.getElementById('typeFilter') || {}).value || '';
    const snFilter = (document.getElementById('snFilter') || {}).checked || false;

    return ALL_CLINICS.filter(function (c) {
      const matchQ = !q ||
        (c.name && c.name.toLowerCase().includes(q.toLowerCase())) ||
        (c.city && c.city.toLowerCase().includes(q.toLowerCase())) ||
        (c.address && c.address.toLowerCase().includes(q.toLowerCase()));
      const matchType = !typeFilter || c.clinic_type === typeFilter;
      const matchSN = !snFilter || c.accepts_special_needs;
      return matchQ && matchType && matchSN;
    });
  }

  function applyFilters() {
    renderClinics(getFiltered());
  }

  // ── Event Listeners ──────────────────────────────────────
  const searchEl = document.getElementById('clinicSearch');
  if (searchEl) {
    let debounceTimer;
    searchEl.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(applyFilters, 250);
    });
  }

  const typeFilter = document.getElementById('typeFilter');
  if (typeFilter) typeFilter.addEventListener('change', applyFilters);

  const snFilter = document.getElementById('snFilter');
  if (snFilter) snFilter.addEventListener('change', applyFilters);

  // Handle ?special_needs=1 in URL
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('special_needs') === '1' && snFilter) {
    snFilter.checked = true;
  }

  // ── Helpers ──────────────────────────────────────────────
  function escHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ── Boot ────────────────────────────────────────────────
  if (document.getElementById('clinicMap')) {
    if (typeof L === 'undefined') {
      document.getElementById('clinicMap').innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#718096;"><p>Map could not load. Please check your internet connection.</p></div>';
      renderList(ALL_CLINICS);
      updateCount(ALL_CLINICS.length);
    } else {
      initMap();
      if (urlParams.get('special_needs') === '1') {
        applyFilters();
      }
    }
  }

})();
