const TYPE_LABELS = {
  tech_media:      "Tech media",
  news:            "News",
  blog:            "Blog",
  social_x:        "X / Twitter",
  social_linkedin: "LinkedIn",
  social_facebook: "Facebook",
  social_reddit:   "Reddit",
  video_youtube:   "YouTube",
};

const ITEMS_PER_PAGE = 20;
let activeFilter = 'all';
let currentPage = 1;
let currentFiltered = [];

function setFilter(type, btn) {
  activeFilter = type;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}

function applyFilters() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  currentFiltered = MENTIONS.filter(m => {
    const matchType =
      activeFilter === 'all'
      || m.source_type === activeFilter
      || (activeFilter === 'social' && m.source_type.startsWith('social_'));
    const matchQ =
      !q
      || m.title.toLowerCase().includes(q)
      || m.snippet.toLowerCase().includes(q)
      || m.source.toLowerCase().includes(q);
    return matchType && matchQ;
  });
  currentFiltered.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  currentPage = 1;
  document.getElementById('emptyState').style.display = currentFiltered.length ? 'none' : 'block';
  render();
}

function render() {
  const totalPages = Math.max(1, Math.ceil(currentFiltered.length / ITEMS_PER_PAGE));
  currentPage = Math.min(currentPage, totalPages);
  const start = (currentPage - 1) * ITEMS_PER_PAGE;
  renderTimeline(currentFiltered.slice(start, start + ITEMS_PER_PAGE));
  renderPagination(totalPages);
}

function goToPage(page) {
  currentPage = page;
  render();
  document.getElementById('timeline').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderPagination(totalPages) {
  const container = document.getElementById('pagination');
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  const range = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) range.push(i);
  } else {
    range.push(1);
    if (currentPage > 3) range.push('...');
    for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) range.push(i);
    if (currentPage < totalPages - 2) range.push('...');
    range.push(totalPages);
  }

  const numBtn = (n) => {
    const active = n === currentPage ? ' pg-active' : '';
    return `<button class="pg-btn${active}" onclick="goToPage(${n})">${n}</button>`;
  };

  let html = `<button class="pg-btn pg-arrow" onclick="goToPage(${currentPage - 1})"${currentPage === 1 ? ' disabled' : ''}>&lsaquo; <span class="pg-label">Previous</span></button>`;
  for (const p of range) {
    html += p === '...' ? `<span class="pg-ellipsis">…</span>` : numBtn(p);
  }
  html += `<button class="pg-btn pg-arrow" onclick="goToPage(${currentPage + 1})"${currentPage === totalPages ? ' disabled' : ''}><span class="pg-label">Next</span> &rsaquo;</button>`;

  container.innerHTML = html;
}

function groupByMonth(mentions) {
  const groups = {};
  mentions.forEach(m => {
    const key = m.date ? m.date.slice(0, 7) : 'undated';
    const label = key === 'undated'
      ? 'Undated'
      : new Date(key + '-01').toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    if (!groups[key]) groups[key] = { label, items: [] };
    groups[key].items.push(m);
  });
  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([, g]) => g);
}

function renderTimeline(mentions) {
  const timeline = document.getElementById('timeline');
  const groups = groupByMonth(mentions);
  timeline.innerHTML = '';
  groups.forEach(g => {
    const group = document.createElement('div');
    group.className = 'timeline-group';

    const monthLabel = document.createElement('div');
    monthLabel.className = 'timeline-month';
    monthLabel.textContent = g.label;
    group.appendChild(monthLabel);

    const grid = document.createElement('div');
    grid.className = 'card-grid';

    g.items.forEach(m => {
      const card = document.createElement('a');
      card.className = 'mention-card';
      card.href = m.url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
      const LANG_BCP47 = { JP: 'ja', JA: 'ja', ZH: 'zh', KO: 'ko' };
      if (m.language && m.language !== 'EN') {
        card.lang = LANG_BCP47[m.language] || m.language.toLowerCase();
        card.setAttribute('translate', 'no');
      }
      card.innerHTML = `
        <div class="card-header">
          <span class="source-badge">${TYPE_LABELS[m.source_type] || m.source_type}</span>
          ${m.language && m.language !== 'EN' ? `<span class="lang-tag">${m.language}</span>` : ''}
        </div>
        <div class="card-title">${m.title}</div>
        <div class="card-snippet">${m.snippet}</div>
        <div class="card-footer">
          <span class="card-source">${m.source}</span>
          <span class="card-arrow">Read more →</span>
        </div>`;
      grid.appendChild(card);
    });

    group.appendChild(grid);
    timeline.appendChild(group);
  });
}

applyFilters();

// Theme toggle
(function () {
  const html = document.documentElement;
  const btn  = document.getElementById('themeToggle');
  const sun  = btn.querySelector('.icon-sun');
  const moon = btn.querySelector('.icon-moon');

  function applyTheme(isLight) {
    html.classList.toggle('light', isLight);
    sun.style.display  = isLight ? ''     : 'none';
    moon.style.display = isLight ? 'none' : '';
    btn.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
  }

  btn.addEventListener('click', () => applyTheme(!html.classList.contains('light')));
  applyTheme(localStorage.getItem('theme') === 'light');
})();
