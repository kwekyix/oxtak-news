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

let activeFilter = 'all';

function setFilter(type, btn) {
  activeFilter = type;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}

function applyFilters() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = MENTIONS.filter(m => {
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
  renderTimeline(filtered);
  document.getElementById('emptyState').style.display = filtered.length ? 'none' : 'block';
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

renderTimeline(MENTIONS);

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
