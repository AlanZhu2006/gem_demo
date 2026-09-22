'use strict';

const $ = (selector) => document.querySelector(selector);
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

function initializeTabs(selector, update) {
  const tabs = [...document.querySelectorAll(`${selector} [role="tab"]`)];
  const activate = (tab) => {
    for (const item of tabs) {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.tabIndex = selected ? 0 : -1;
    }
    update(tab);
  };
  for (const tab of tabs) {
    tab.addEventListener('click', () => activate(tab));
    tab.addEventListener('keydown', (event) => {
      const index = tabs.indexOf(tab);
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        tabs[next].focus();
        activate(tabs[next]);
      }
    });
  }
}

const demonstrations = {
  indoor: {
    label: 'Indoor revisit: GEM and the baseline',
    description: 'After the same initial survey, GEM returns to the image goal while the baseline stops before a glass wall. Both runs use frozen NavDP and share the starting pose and goal image.'
  },
  outdoor: {
    label: 'Outdoor revisit: GEM and the baseline',
    description: 'GEM recalls a surveyed goal in an outdoor environment and updates the goal bearing as the robot moves. Frozen NavDP plans the local motion; the baseline does not reach the goal.'
  },
  simulation: {
    label: 'Simulation: two novel goals followed by a revisit',
    description: 'Both methods first reach two novel goals. The third goal revisits an earlier location: GEM uses the accumulated history to complete the sequence, while the baseline fails.'
  }
};
const demo = $('#demo-video');
initializeTabs('.demo-tabs', (tab) => {
  const name = tab.dataset.demo;
  demo.pause();
  demo.poster = `assets/${name}.jpg`;
  demo.src = `assets/${name}.mp4`;
  demo.setAttribute('aria-label', demonstrations[name].label);
  demo.load();
  $('#demo-description').textContent = demonstrations[name].description;
  $('#demo-panel').setAttribute('aria-labelledby', tab.id);
});

const methods = {
  full: {image: 'architecture', width: 2048, height: 1019, label: 'Figure 1 / System architecture', title: 'One memory, two readouts',
    text: 'Sparse readout supplies verified recall for goal conditioning. Dense readout supplies current monocular depth for local control. The geometry model and navigation policies remain frozen.',
    alt: 'Complete GEM architecture, including streaming geometric memory, verified goal readout, and adapters for frozen navigation controllers.'},
  overview: {image: 'overview', width: 2048, height: 325, label: 'Figure 1(a) / System overview', title: 'Memory outside the controller’s short context',
    text: 'Incoming RGB images update a streaming geometric state and an episodic archive. A goal query reads from that history, while controller-specific adapters preserve the existing NavDP, ViNT, or NoMaD interface.',
    alt: 'System overview: RGB images feed a streaming geometry model, whose working state and archive support dense and sparse readouts for a frozen controller.'},
  memory: {image: 'memory', width: 605, height: 679, label: 'Figure 1(b) / Episodic memory', title: 'Retained across successive goals',
    text: 'The working state maintains context for streaming pose and depth estimation. The indexed archive links each historical image and descriptor to its pose, depth, and confidence. Both persist across goal changes and are reset at the episode boundary.',
    alt: 'Episodic memory: a persistent neural working state and a frame-indexed archive of RGB images, descriptors, poses, depth, and confidence.'},
  readout: {image: 'readout', width: 1428, height: 679, label: 'Figure 1(c) / Goal readout', title: 'From a recalled view to the current camera',
    text: 'GEM retrieves a historical view, uses its depth and image correspondences to estimate and verify the goal pose, then connects that pose to the current camera through the geometry stream. No direct overlap between the goal and current images is required.',
    alt: 'Goal readout: match goal to history, localize with PnP-RANSAC, verify geometry, cache the goal pose, and read a current-relative goal bearing.'}
};
let activeMethod = methods.full;
initializeTabs('.method-tabs', (tab) => {
  const view = tab.dataset.method;
  activeMethod = methods[view];
  const image = $('#method-image');
  image.src = `assets/${activeMethod.image}.webp`;
  image.alt = activeMethod.alt;
  image.width = activeMethod.width;
  image.height = activeMethod.height;
  $('#method-panel').dataset.view = view;
  $('#method-panel').setAttribute('aria-labelledby', tab.id);
  $('#method-kicker').textContent = activeMethod.label;
  $('#method-detail-title').textContent = activeMethod.title;
  $('#method-description').textContent = activeMethod.text;
});

const figureDialog = $('#figure-dialog');
$('#expand-figure').addEventListener('click', () => {
  $('#large-figure').src = `assets/${activeMethod.image}.webp`;
  $('#large-figure').alt = activeMethod.alt;
  $('#figure-original').href = `assets/${activeMethod.image}.webp`;
  $('#figure-dialog-title').textContent = activeMethod.label;
  figureDialog.showModal();
});
$('#close-figure').addEventListener('click', () => figureDialog.close());
figureDialog.addEventListener('click', (event) => {
  const rect = figureDialog.getBoundingClientRect();
  if (event.target === figureDialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) figureDialog.close();
});

// Exact Table I counts and scene-cluster confidence intervals. No pooled claims.
const results = {
  hm3d: {description: 'HM3D · 28 shared histories across 21 scenes', rows: [
    ['NavDP', '10/28', '27/28', '+60.7', '[38.7, 82.6]'],
    ['ViNT', '5/28', '25/28', '+71.4', '[51.7, 89.7]'],
    ['NoMaD', '7/28', '24/28', '+60.7', '[35.7, 81.2]']]},
  mp3d: {description: 'MP3D · 42 shared histories across 25 scenes', rows: [
    ['NavDP', '9/42', '41/42', '+76.2', '[60.9, 90.0]'],
    ['ViNT', '2/42', '36/42', '+81.0', '[69.4, 92.1]'],
    ['NoMaD', '8/42', '37/42', '+69.0', '[51.1, 86.1]']]}
};
initializeTabs('.dataset-tabs', (tab) => {
  const data = results[tab.dataset.dataset];
  $('#dataset-description').textContent = data.description;
  $('#results-panel').setAttribute('aria-labelledby', tab.id);
  const rows = data.rows.map((values) => {
    const row = document.createElement('tr');
    values.forEach((text, index) => {
      const cell = document.createElement(index === 0 ? 'th' : 'td');
      if (index === 0) cell.scope = 'row';
      if (index === 2) cell.className = 'gem-value';
      cell.textContent = text;
      row.append(cell);
    });
    return row;
  });
  $('#result-rows').replaceChildren(...rows);
});

const teaser = $('#teaser');
let teaserUserPaused = false;
let teaserVisible = false;
function syncTeaserButton() {
  const playing = !teaser.paused;
  $('#teaser-toggle').setAttribute('aria-label', `${playing ? 'Pause' : 'Play'} point-cloud animation`);
  $('#teaser-action').textContent = playing ? 'Pause' : 'Play';
  $('#teaser-icon').textContent = playing ? 'Ⅱ' : '▶';
}
function loadTeaser() {
  if (!teaser.getAttribute('src')) teaser.src = teaser.dataset.src;
}
async function playTeaser() {
  loadTeaser();
  try { await teaser.play(); } catch { syncTeaserButton(); }
}
function updateTeaser() {
  const otherPlaying = [demo, $('#presentation')].some((video) => !video.paused);
  if (teaserVisible && !document.hidden && !teaserUserPaused && !reduceMotion.matches && !otherPlaying) playTeaser();
  else teaser.pause();
}
$('#teaser-toggle').addEventListener('click', () => {
  if (teaser.paused) { teaserUserPaused = false; playTeaser(); }
  else { teaserUserPaused = true; teaser.pause(); }
});
teaser.addEventListener('play', syncTeaserButton);
teaser.addEventListener('pause', syncTeaserButton);
new IntersectionObserver(([entry]) => { teaserVisible = entry.isIntersecting; updateTeaser(); }, {threshold: .2}).observe(teaser);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) [demo, $('#presentation')].forEach((video) => video.pause());
  updateTeaser();
});
reduceMotion.addEventListener('change', updateTeaser);
for (const video of [demo, $('#presentation')]) {
  video.addEventListener('play', () => {
    for (const other of [demo, $('#presentation'), teaser]) if (other !== video) other.pause();
  });
}

function safeUrl(value) {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : ''; } catch { return ''; }
}
async function loadMetadata() {
  try {
    const response = await fetch('site.config.json');
    if (!response.ok) return;
    const config = await response.json();
    for (const [key, id] of [['arxiv_url', '#arxiv-link'], ['code_url', '#code-link']]) {
      const url = safeUrl(config[key]);
      if (url) { const link = $(id); link.href = url; link.hidden = false; link.target = '_blank'; link.rel = 'noopener'; }
    }
    if (Array.isArray(config.authors) && config.authors.length) {
      const nodes = config.authors.map((author, index) => {
        const item = document.createElement('span');
        if (index) item.append(document.createTextNode(' · '));
        const url = safeUrl(author.url);
        const name = document.createElement(url ? 'a' : 'span');
        name.textContent = author.name;
        if (url) name.href = url;
        item.append(name);
        if (author.affiliation) { const sup = document.createElement('sup'); sup.textContent = author.affiliation; item.append(sup); }
        return item;
      });
      $('#authors').replaceChildren(...nodes);
      $('#affiliations').textContent = (config.affiliations || []).join(' · ');
      $('#author-block').hidden = false;
    }
    if (config.bibtex?.trim()) { $('#bibtex').textContent = config.bibtex; $('#citation').hidden = false; }
    const site = safeUrl(config.project_url);
    if (site) {
      const canonical = $('link[rel="canonical"]') || document.createElement('link');
      canonical.rel = 'canonical'; canonical.href = site; document.head.append(canonical);
      $('meta[property="og:image"]').content = new URL('assets/teaser.jpg', site).href;
    }
  } catch (error) { console.warn('Optional project metadata could not be loaded.', error); }
}
loadMetadata();
$('#copy-citation').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('#bibtex').textContent);
    $('#copy-status').textContent = 'BibTeX copied.';
  } catch { $('#copy-status').textContent = 'Select the citation text above to copy it.'; }
});
