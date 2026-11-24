/**
 * PlayerSlayer's Sanctuary - Netflix Frontend Logic
 */

let catalog = {
  show: {},
  seasons: [6],
  episodes: [],
  continue_watching: [],
  next_up: null
};

let currentMainView = 'brokegirls';
let currentSeason = 6;
let currentFilter = 'all';
let searchQuery = '';
let activeModalEpisode = null;
let vlcPollInterval = null;
let browserPlayerSaveInterval = null;

// YouTube Hub State
let youtubeCatalog = {
  videos: [],
  categories: [],
  currentCategory: 'all'
};
let activeYouTubeVideo = null;

// Favorite Channels List (from user's subscriptions & regular watch history)
const FAVORITE_CHANNELS = [
  {
    name: "Coach Ali",
    handle: "@CoachAli",
    url: "https://www.youtube.com/@CoachAli",
    category: "Football Analysis & Predictions",
    initials: "CA",
    color: "#E50914"
  },
  {
    name: "Talk Football HD",
    handle: "@TalkFootballHD",
    url: "https://www.youtube.com/@TalkFootballHD",
    category: "European Football & Tactical News",
    initials: "TF",
    color: "#46D369"
  },
  {
    name: "NOT YOUR TYPE",
    handle: "@NOTYOURTYPE",
    url: "https://www.youtube.com/@NOTYOURTYPE",
    category: "Relatable Storytime & Animation",
    initials: "NY",
    color: "#FF9900"
  },
  {
    name: "The Infographics Show",
    handle: "@TheInfographicsShow",
    url: "https://www.youtube.com/@TheInfographicsShow",
    category: "Animated Facts & Documentaries",
    initials: "IS",
    color: "#00A8FF"
  },
  {
    name: "PodTalksFutbol",
    handle: "@PodTalksFutbol",
    url: "https://www.youtube.com/@PodTalksFutbol",
    category: "Football Podcast & Discussion",
    initials: "PF",
    color: "#9C27B0"
  },
  {
    name: "Sony Sports Network",
    handle: "@SonySportsNetwork",
    url: "https://www.youtube.com/@SonySportsNetwork",
    category: "Cricket & Live Sports Highlights",
    initials: "SS",
    color: "#D4AF37"
  },
  {
    name: "Abhi and Niyu",
    handle: "@AbhiandNiyu",
    url: "https://www.youtube.com/@AbhiandNiyu",
    category: "Positive News & Indian Stories",
    initials: "AN",
    color: "#FF5252"
  },
  {
    name: "Divyansh",
    handle: "@Divyansh",
    url: "https://www.youtube.com/@Divyansh",
    category: "Gaming, Streaming & Vlogs",
    initials: "DV",
    color: "#00E5FF"
  },
  {
    name: "Morc52G",
    handle: "@morc52g",
    url: "https://www.youtube.com/@morc52g",
    category: "Football Skills & Match Highlights",
    initials: "M5",
    color: "#76FF03"
  }
];

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  setupNavbarScroll();
  setupFullscreenListener();
  initDynamicBackdrops();
  fetchCatalog();
  startVlcStatusPolling();
  setupKeyboardShortcuts();
});

// Fullscreen capability functions
let isAppFullscreen = false;
let wasWindowFullscreenBeforePlayer = false;
let playerIdleTimer = null;

function resetPlayerIdle(wrapperId = "player-wrapper") {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;
  wrapper.classList.remove("idle");
  if (playerIdleTimer) clearTimeout(playerIdleTimer);
  playerIdleTimer = setTimeout(() => {
    const modalId = wrapperId === "player-wrapper" ? "player-modal" : "yt-player-modal";
    const modal = document.getElementById(modalId);
    if (modal && modal.classList.contains("open")) {
      wrapper.classList.add("idle");
    }
  }, 2500);
}

function updateFullscreenButtonUI(isFs) {
  isAppFullscreen = Boolean(isFs);
  const fsBtn = document.getElementById("fs-btn");
  const playerFsBtn = document.getElementById("player-fs-btn");
  const ytFsBtn = document.getElementById("yt-fs-btn");

  const iconHtml = isFs ? '<i class="fa-solid fa-compress"></i>' : '<i class="fa-solid fa-expand"></i>';
  const titleText = isFs ? "Exit Fullscreen (F11 / Esc)" : "Enter Fullscreen (F11 / F)";

  if (fsBtn) {
    fsBtn.innerHTML = iconHtml;
    fsBtn.title = titleText;
  }
  if (playerFsBtn) {
    playerFsBtn.innerHTML = iconHtml;
    playerFsBtn.title = titleText;
  }
  if (ytFsBtn) {
    ytFsBtn.innerHTML = iconHtml;
    ytFsBtn.title = titleText;
  }
  if (isFs) {
    showToast("⛶ Fullscreen Mode Active");
  } else {
    showToast("Exited Fullscreen");
  }
}

async function setAppFullscreen(enable) {
  enable = Boolean(enable);
  if (isAppFullscreen === enable) return;

  // 1. PyWebView JS API directly
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_fullscreen) {
    try {
      const isFs = await window.pywebview.api.set_fullscreen(enable);
      updateFullscreenButtonUI(Boolean(isFs));
      return;
    } catch (err) {
      console.warn("PyWebView API set_fullscreen error:", err);
    }
  }

  // 2. Server API fallback
  try {
    const res = await fetch(`/api/app/fullscreen/set?enable=${enable}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      if (data.handled) {
        updateFullscreenButtonUI(Boolean(data.is_fullscreen));
        return;
      }
    }
  } catch (err) {}

  // 3. Fallback to toggleAppFullscreen if state doesn't match
  if (isAppFullscreen !== enable) {
    await toggleAppFullscreen();
  }
}

async function toggleAppFullscreen() {
  // 1. Try PyWebView JS API directly
  if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) {
    try {
      const isFs = await window.pywebview.api.toggle_fullscreen();
      updateFullscreenButtonUI(Boolean(isFs));
      return;
    } catch (err) {
      console.warn("PyWebView API toggle error:", err);
    }
  }

  // 2. Try Server-Side Native Window Toggle Endpoint
  try {
    const res = await fetch("/api/app/fullscreen", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      if (data.handled) {
        updateFullscreenButtonUI(Boolean(data.is_fullscreen));
        return;
      }
    }
  } catch (err) {
    // ignore
  }

  // 3. Browser-level HTML5 Fullscreen (Fallback for Chrome/Edge/Firefox)
  const doc = document;
  const docEl = document.documentElement;
  const isHtmlFs = Boolean(
    doc.fullscreenElement ||
    doc.webkitFullscreenElement ||
    doc.mozFullScreenElement ||
    doc.msFullscreenElement
  );

  if (!isHtmlFs) {
    const enterFs =
      docEl.requestFullscreen ||
      docEl.webkitRequestFullscreen ||
      docEl.mozRequestFullScreen ||
      docEl.msRequestFullscreen;
    if (enterFs) {
      try {
        await enterFs.call(docEl);
        updateFullscreenButtonUI(true);
      } catch (e) {
        console.warn("Browser requestFullscreen error:", e);
      }
    }
  } else {
    const exitFs =
      doc.exitFullscreen ||
      doc.webkitExitFullscreen ||
      doc.mozCancelFullScreen ||
      doc.msExitFullscreen;
    if (exitFs) {
      try {
        await exitFs.call(doc);
        updateFullscreenButtonUI(false);
      } catch (e) {
        console.warn("Browser exitFullscreen error:", e);
      }
    }
  }
}

function setupFullscreenListener() {
  const events = ["fullscreenchange", "webkitfullscreenchange", "mozfullscreenchange", "MSFullscreenChange"];
  events.forEach(evt => {
    document.addEventListener(evt, () => {
      const isHtmlFs = Boolean(
        document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement ||
        document.msFullscreenElement
      );
      updateFullscreenButtonUI(isHtmlFs);
    });
  });
}

// Setup sticky blurred navbar on scroll
function setupNavbarScroll() {
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      navbar.classList.add("scrolled");
    } else {
      navbar.classList.remove("scrolled");
    }
  });
}

// Fetch catalog and enriched progress from server
async function fetchCatalog() {
  try {
    const res = await fetch("/api/catalog");
    if (!res.ok) throw new Error("Failed to load catalog");
    catalog = await res.json();

    updateSeasonCounts();
    renderHero();
    renderContinueWatching();
    renderEpisodes();
  } catch (err) {
    console.error("Error loading catalog:", err);
    showToast("Error loading episode data. Please check server.");
  }
}

// Update episode count pills on season tabs
function updateSeasonCounts() {
  const s6Count = catalog.episodes.filter(e => e.season === 6).length;
  const countS6 = document.getElementById("count-s6");
  if (countS6) countS6.innerText = s6Count;
  const countAll = document.getElementById("count-all");
  if (countAll) countAll.innerText = catalog.episodes.length;
}

// Dynamic Backdrop System (Fresh cinema backdrop every time the app opens!)
let dynamicBackdropPool = [];
let currentBackdropIndex = -1;
let backdropCycleInterval = null;

async function initDynamicBackdrops() {
  try {
    const res = await fetch("/api/backdrops");
    if (res.ok) {
      const data = await res.json();
      if (data.backdrops && data.backdrops.length > 0) {
        dynamicBackdropPool = data.backdrops;
      }
    }
  } catch (e) {
    console.warn("Failed to fetch backdrops list from API:", e);
  }

  if (dynamicBackdropPool.length === 0) {
    dynamicBackdropPool = Array.from({ length: 24 }, (_, i) => 
      `/static/backdrops/backdrop_${String(i + 1).padStart(2, '0')}.jpg`
    );
    dynamicBackdropPool.push("/static/assets/backdrop.jpg");
  }

  // Set random cinema backdrop immediately on open
  setNextDynamicBackdrop(true);

  // Smooth ambient rotation every 60s when viewing home screen
  if (backdropCycleInterval) clearInterval(backdropCycleInterval);
  backdropCycleInterval = setInterval(() => {
    if (currentMainView === 'brokegirls' && !document.hidden && window.scrollY < 300) {
      setNextDynamicBackdrop(false);
    }
  }, 60000);
}

function setNextDynamicBackdrop(random = true) {
  const backdropElem = document.getElementById("hero-backdrop");
  if (!backdropElem || dynamicBackdropPool.length === 0) return;

  let nextIdx;
  if (random) {
    do {
      nextIdx = Math.floor(Math.random() * dynamicBackdropPool.length);
    } while (dynamicBackdropPool.length > 1 && nextIdx === currentBackdropIndex);
  } else {
    nextIdx = (currentBackdropIndex + 1) % dynamicBackdropPool.length;
  }
  currentBackdropIndex = nextIdx;
  const chosenUrl = dynamicBackdropPool[nextIdx];

  const img = new Image();
  img.src = chosenUrl;
  img.onload = () => {
    backdropElem.style.opacity = "0.2";
    setTimeout(() => {
      backdropElem.style.backgroundImage = `url('${chosenUrl}')`;
      backdropElem.style.opacity = "1";
    }, 200);
  };
}

// Render the Hero Billboard
function renderHero() {
  const nextUp = catalog.next_up;
  const heroResumeBtn = document.getElementById("hero-resume-btn");
  const heroResumeText = document.getElementById("hero-resume-text");
  const heroPreview = document.getElementById("hero-next-preview");
  const heroPreviewTitle = document.getElementById("hero-preview-title");
  const heroSynopsis = document.getElementById("hero-synopsis");

  if (nextUp) {
    const prog = nextUp.progress;
    if (prog && prog.current_time > 15 && !prog.completed) {
      heroResumeText.innerText = `Resume ${nextUp.episode_label} (${prog.formatted_remaining})`;
    } else {
      heroResumeText.innerText = `Play ${nextUp.episode_label}`;
    }

    heroPreviewTitle.innerText = `${nextUp.episode_label} • ${nextUp.title}`;
    heroPreview.style.display = "inline-flex";

    if (nextUp.summary && nextUp.summary.length > 20) {
      heroSynopsis.innerText = nextUp.summary;
    }
  } else {
    heroResumeText.innerText = "Play Final Season";
    heroPreview.style.display = "none";
  }
}

function playHeroEpisode() {
  if (catalog.next_up) {
    playInVLC(catalog.next_up.id, true);
  } else if (catalog.episodes.length > 0) {
    playInVLC(catalog.episodes[0].id, true);
  }
}

function playHeroInBrowser() {
  if (catalog.next_up) {
    playInBrowser(catalog.next_up.id);
  } else if (catalog.episodes.length > 0) {
    playInBrowser(catalog.episodes[0].id);
  }
}

function openHeroDetails() {
  if (catalog.next_up) {
    openDetailsModal(catalog.next_up.id);
  } else if (catalog.episodes.length > 0) {
    openDetailsModal(catalog.episodes[0].id);
  }
}

// Render Continue Watching section (Pure 2 Broke Girls Sanctuary)
function renderContinueWatching() {
  const container = document.getElementById("continue-grid");
  const section = document.getElementById("continue-section");
  const navLink = document.getElementById("nav-continue-link");

  const bgList = catalog.continue_watching || [];

  if (bgList.length === 0) {
    section.style.display = "none";
    if (navLink) navLink.style.display = "none";
    return;
  }

  section.style.display = "block";
  if (navLink) navLink.style.display = "inline-block";

  container.innerHTML = bgList.map(item => {
    const prog = item.progress;
    return `
      <div class="continue-card" onclick="openDetailsModal('${item.id}')">
        <div class="continue-thumb-wrap">
          <img src="${item.thumbnail}" alt="${item.title}" loading="lazy" onerror="this.onerror=null; this.src='/static/assets/backdrop.jpg'">
          <div class="continue-play-overlay" onclick="event.stopPropagation(); playInVLC('${item.id}', true)">
            <div class="play-circle-icon"><i class="fa-solid fa-play"></i></div>
          </div>
          <div class="card-progress-bar">
            <div class="card-progress-fill" style="width: ${prog.progress_pct}%;"></div>
          </div>
        </div>
        <div class="continue-info">
          <div class="continue-header-line">
            <span class="continue-ep-tag">${item.episode_label}</span>
            <span class="continue-time-left">${prog.formatted_remaining}</span>
          </div>
          <h3 class="continue-title" title="${item.title}">${item.title}</h3>
          <div class="continue-card-actions">
            <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); playInVLC('${item.id}', true)">
              <i class="fa-solid fa-play"></i> Resume
            </button>
            <button class="btn-text" onclick="event.stopPropagation(); resetProgress('${item.id}')" title="Reset progress to beginning">
              ↺ Reset
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function resumeYouTubeVideo(id, url, time = 0) {
  let resumeUrl = url || `https://www.youtube.com/watch?v=${id}`;
  if (time > 0 && !resumeUrl.includes('&t=') && !resumeUrl.includes('?t=')) {
    resumeUrl += (resumeUrl.includes('?') ? '&' : '?') + 't=' + Math.floor(time) + 's';
  }
  openYouTubePortal('video', resumeUrl);
}

function resetYouTubeProgress(id) {
  const vid = (youtubeCatalog.videos || []).find(v => v.id === id);
  if (vid && vid.progress) {
    vid.progress.current_time = 0;
    vid.progress.progress_pct = 0;
    vid.progress.completed = false;
    renderContinueWatching();
    showToast("Progress reset");
  }
}

// Render Favorite Channels (Subscribed & Regular Channels)
function renderFavoriteChannels() {
  const grid = document.getElementById("channels-grid");
  if (!grid) return;

  grid.innerHTML = FAVORITE_CHANNELS.map(ch => `
    <div class="channel-card" onclick="openYouTubePortal('channel', '${ch.url}')" title="Open ${escapeHtml(ch.name)} on YouTube">
      <div class="channel-avatar-wrap">
        <div class="channel-avatar" style="border: 2px solid ${ch.color};">
          ${ch.initials}
        </div>
      </div>
      <h4 class="channel-name">
        <span>${escapeHtml(ch.name)}</span>
        <i class="fa-solid fa-circle-check"></i>
      </h4>
      <span class="channel-category">${escapeHtml(ch.category)}</span>
      <button class="channel-action-btn">
        <i class="fa-brands fa-youtube"></i> Visit Channel
      </button>
    </div>
  `).join("");
}

// Render Quick Channels List in the Consolidated YouTube Button Dropdown
function renderQuickChannels() {
  const list = document.getElementById("yt-channels-quick-list");
  if (!list) return;

  list.innerHTML = FAVORITE_CHANNELS.map(ch => `
    <div class="yt-quick-channel-item" onclick="openYouTubePortal('channel', '${ch.url}'); closeYtDropdown();" title="Open ${escapeHtml(ch.name)} on YouTube">
      <div class="yt-quick-channel-avatar" style="border-color: ${ch.color};">
        ${ch.initials}
      </div>
      <div class="yt-quick-channel-info">
        <span class="yt-quick-channel-name">${escapeHtml(ch.name)}</span>
        <span class="yt-quick-channel-sub">${escapeHtml(ch.category)}</span>
      </div>
      <i class="fa-solid fa-arrow-up-right-from-square yt-quick-channel-icon"></i>
    </div>
  `).join("");
}

// Dropdown Toggles for Single YouTube Hub Button
function toggleYtDropdown(e) {
  if (e) e.stopPropagation();
  const wrap = document.getElementById("yt-button-dropdown-wrap");
  if (wrap) wrap.classList.toggle("open");
}

function closeYtDropdown() {
  const wrap = document.getElementById("yt-button-dropdown-wrap");
  if (wrap) wrap.classList.remove("open");
}

// Close dropdown on click outside
document.addEventListener("click", (e) => {
  const wrap = document.getElementById("yt-button-dropdown-wrap");
  if (wrap && !wrap.contains(e.target)) {
    wrap.classList.remove("open");
  }
});

// Render Episodes Grid
function renderEpisodes() {
  const grid = document.getElementById("episodes-grid");

  let filtered = catalog.episodes;

  // Filter by season
  if (currentSeason !== 'all') {
    filtered = filtered.filter(e => e.season === currentSeason);
  }

  // Filter by search query
  if (searchQuery.trim() !== '') {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter(e => 
      e.title.toLowerCase().includes(q) ||
      e.summary.toLowerCase().includes(q) ||
      e.episode_label.toLowerCase().includes(q)
    );
  }

  // Filter by watch status
  if (currentFilter === 'in_progress') {
    filtered = filtered.filter(e => e.progress.current_time >= 15 && !e.progress.completed);
  } else if (currentFilter === 'unwatched') {
    filtered = filtered.filter(e => !e.progress.completed && e.progress.current_time < 15);
  } else if (currentFilter === 'watched') {
    filtered = filtered.filter(e => e.progress.completed);
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: var(--text-muted);">
        <i class="fa-solid fa-film" style="font-size: 40px; margin-bottom: 14px;"></i>
        <p style="font-size: 16px;">No episodes matched your filter or search query.</p>
        <button class="btn btn-secondary btn-sm" style="margin-top: 14px;" onclick="clearSearch()">Clear Filters</button>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(ep => {
    const prog = ep.progress;
    const hasProgress = prog.current_time > 15;
    const isCompleted = prog.completed;

    return `
      <div class="episode-card" onclick="openDetailsModal('${ep.id}')">
        <div class="episode-thumb-container">
          <img src="${ep.thumbnail}" alt="${ep.title}" loading="lazy" onerror="this.onerror=null; this.src='/static/assets/backdrop.jpg'">
          <span class="ep-badge-overlay">${ep.episode_label}</span>
          <span class="ep-duration-overlay">${ep.runtime}</span>
          ${isCompleted ? '<span class="ep-watched-checkmark" title="Watched"><i class="fa-solid fa-check"></i></span>' : ''}
          ${hasProgress && !isCompleted ? `
            <div class="card-progress-bar">
              <div class="card-progress-fill" style="width: ${prog.progress_pct}%;"></div>
            </div>
          ` : ''}
        </div>

        <div class="ep-card-body">
          <div class="ep-card-title-row">
            <h3 class="ep-card-title">${ep.title}</h3>
          </div>

          <div style="display: flex; gap: 8px; margin-bottom: 8px; font-size: 11px;">
            <span style="color: #46D369;"><i class="fa-solid fa-closed-captioning"></i> Subtitles Auto-Loaded</span>
            <span style="color: var(--text-muted);">•</span>
            <span style="color: var(--text-muted);">${ep.filesize_mb} MB</span>
          </div>

          <p class="ep-card-summary">${ep.summary}</p>

          <div class="ep-card-actions">
            <button class="btn btn-primary" onclick="event.stopPropagation(); playInVLC('${ep.id}', true)" title="Play in VLC Media Player with hardware codecs & auto-subtitles">
              <i class="fa-solid fa-play"></i> ${hasProgress && !isCompleted ? 'Resume VLC' : 'Play VLC'}
            </button>
            <button class="icon-action-btn" onclick="event.stopPropagation(); playInBrowser('${ep.id}')" title="Play In-Browser Player">
              <i class="fa-solid fa-laptop"></i>
            </button>
            <button class="icon-action-btn" onclick="event.stopPropagation(); toggleWatched('${ep.id}', ${!isCompleted})" title="${isCompleted ? 'Mark as Unwatched' : 'Mark as Watched'}">
              <i class="fa-solid ${isCompleted ? 'fa-eye-slash' : 'fa-check'}"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Season Tab Switching
function selectSeason(season, navElem = null) {
  currentSeason = season;

  document.querySelectorAll(".season-tab").forEach(tab => tab.classList.remove("active"));
  const tabS6 = document.getElementById("tab-s6");
  const tabAll = document.getElementById("tab-all");
  if (season === 6 && tabS6) tabS6.classList.add("active");
  else if (tabAll) tabAll.classList.add("active");

  if (navElem) {
    setActiveNav(navElem);
  }

  renderEpisodes();
  const epSection = document.getElementById("episodes-section");
  if (epSection && window.scrollY > 300) {
    epSection.scrollIntoView({ behavior: 'smooth' });
  }
}

function setActiveNav(element) {
  if (!element) return;
  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
  element.classList.add("active");
}

// Switch between 2 Broke Girls and direct YouTube feed
function switchMainView(viewName) {
  if (viewName === 'youtube') {
    openYouTubePortal('home');
    return;
  }
  currentMainView = 'brokegirls';
  const bgContainer = document.getElementById("brokegirls-container");
  const ytContainer = document.getElementById("youtube-container");
  const btnBg = document.getElementById("view-btn-brokegirls");
  const btnYt = document.getElementById("view-btn-youtube");
  const searchInput = document.getElementById("search-input");

  if (ytContainer) ytContainer.classList.add("hidden");
  if (bgContainer) bgContainer.classList.remove("hidden");
  if (btnYt) btnYt.classList.remove("active");
  if (btnBg) btnBg.classList.add("active");
  if (searchInput) searchInput.placeholder = "Search episodes...";
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function handleSearchEnter() {
  const input = document.getElementById("search-input");
  if (!input) return;
  const query = input.value.trim();
  if (!query) return;

  if (currentMainView === 'youtube') {
    openYouTubePortal('search', query);
  } else {
    const firstEp = document.querySelector(".episode-card");
    if (firstEp) {
      firstEp.scrollIntoView({ behavior: 'smooth' });
    }
  }
}

// Search and Filter Handlers
function handleSearch(val) {
  searchQuery = val;
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) clearBtn.style.display = val.length > 0 ? "block" : "none";
  renderEpisodes();
}

function clearSearch() {
  const input = document.getElementById("search-input");
  if (input) input.value = "";
  searchQuery = "";
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) clearBtn.style.display = "none";
  renderEpisodes();
}

function applyFilters() {
  currentFilter = document.getElementById("status-filter").value;
  renderEpisodes();
}

// VLC Playback Launch
async function playInVLC(episodeId, resume = true) {
  const ep = catalog.episodes.find(e => e.id === episodeId);
  if (!ep) return;

  showToast(`🚀 Launching ${ep.episode_label} in VLC with Subtitles & Codecs...`);

  try {
    const res = await fetch("/api/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId, resume: resume })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "VLC launch error");

    if (data.resumed_from > 0) {
      showToast(`▶ Resumed ${ep.episode_label} at ${formatTime(data.resumed_from)} in VLC`);
    } else {
      showToast(`▶ Playing ${ep.episode_label} in VLC with English Subtitles`);
    }

    // Refresh after short delay
    setTimeout(fetchCatalog, 2500);
  } catch (err) {
    console.error("VLC launch error:", err);
    showToast(`Error launching VLC: ${err.message}`);
  }
}

// In-Browser Episode Navigation & Auto-Play
let upNextCountdownInterval = null;
let upNextCountdownSeconds = 5;

function getAdjacentEpisodes(episodeId) {
  if (!catalog || !catalog.episodes || catalog.episodes.length === 0) {
    return { prev: null, next: null, index: -1, total: 0 };
  }
  const idx = catalog.episodes.findIndex(e => e.id === episodeId);
  if (idx === -1) return { prev: null, next: null, index: -1, total: catalog.episodes.length };
  const prev = idx > 0 ? catalog.episodes[idx - 1] : null;
  const next = idx < catalog.episodes.length - 1 ? catalog.episodes[idx + 1] : null;
  return { prev, next, index: idx, total: catalog.episodes.length };
}

function updatePlayerNavigationUI(episodeId) {
  const { prev, next } = getAdjacentEpisodes(episodeId);

  // 1. Top overlay header buttons
  const prevBtn = document.getElementById("player-prev-ep-btn");
  const nextBtn = document.getElementById("player-next-ep-btn");

  if (prevBtn) {
    if (prev) {
      prevBtn.disabled = false;
      prevBtn.classList.remove("disabled");
      prevBtn.title = `Previous: ${prev.episode_label} • ${prev.title} (P or [)`;
    } else {
      prevBtn.disabled = true;
      prevBtn.classList.add("disabled");
      prevBtn.title = "First Episode (No previous episode)";
    }
  }

  if (nextBtn) {
    if (next) {
      nextBtn.disabled = false;
      nextBtn.classList.remove("disabled");
      nextBtn.title = `Next: ${next.episode_label} • ${next.title} (N or ])`;
    } else {
      nextBtn.disabled = true;
      nextBtn.classList.add("disabled");
      nextBtn.title = "Series Finale (No next episode)";
    }
  }

  // 2. Edge navigation wings
  const edgePrev = document.getElementById("player-edge-prev");
  const edgeNext = document.getElementById("player-edge-next");
  const edgePrevTooltip = document.getElementById("edge-prev-tooltip");
  const edgeNextTooltip = document.getElementById("edge-next-tooltip");

  if (edgePrev) {
    if (prev) {
      edgePrev.style.display = "flex";
      if (edgePrevTooltip) edgePrevTooltip.innerText = `⏮ ${prev.episode_label}: ${prev.title}`;
    } else {
      edgePrev.style.display = "none";
    }
  }

  if (edgeNext) {
    if (next) {
      edgeNext.style.display = "flex";
      if (edgeNextTooltip) edgeNextTooltip.innerText = `⏭ ${next.episode_label}: ${next.title}`;
    } else {
      edgeNext.style.display = "none";
    }
  }
}

function playNextEpisode() {
  if (!activeModalEpisode) return;
  const { next } = getAdjacentEpisodes(activeModalEpisode.id);
  if (next) {
    cancelPlayNext();
    showToast(`⏭ Playing Next: ${next.episode_label} • ${next.title}`);
    playInBrowser(next.id);
  } else {
    showToast("🏁 You have reached the final episode!");
  }
}

function playPreviousEpisode() {
  if (!activeModalEpisode) return;
  const { prev } = getAdjacentEpisodes(activeModalEpisode.id);
  if (prev) {
    cancelPlayNext();
    showToast(`⏮ Playing Previous: ${prev.episode_label} • ${prev.title}`);
    playInBrowser(prev.id);
  } else {
    showToast("⏮ You are at the first episode!");
  }
}

function showUpNextCard(nextEp) {
  const card = document.getElementById("player-up-next-card");
  const title = document.getElementById("up-next-title");
  const countSpan = document.getElementById("up-next-countdown");
  if (!card || !title || !countSpan) return;

  title.innerText = `${nextEp.episode_label} • ${nextEp.title}`;
  upNextCountdownSeconds = 5;
  countSpan.innerText = upNextCountdownSeconds;
  card.style.display = "flex";

  if (upNextCountdownInterval) clearInterval(upNextCountdownInterval);
  upNextCountdownInterval = setInterval(() => {
    upNextCountdownSeconds -= 1;
    if (countSpan) countSpan.innerText = upNextCountdownSeconds;
    if (upNextCountdownSeconds <= 0) {
      clearInterval(upNextCountdownInterval);
      upNextCountdownInterval = null;
      card.style.display = "none";
      playInBrowser(nextEp.id);
    }
  }, 1000);
}

function confirmPlayNext() {
  if (upNextCountdownInterval) {
    clearInterval(upNextCountdownInterval);
    upNextCountdownInterval = null;
  }
  const card = document.getElementById("player-up-next-card");
  if (card) card.style.display = "none";
  if (activeModalEpisode) {
    const { next } = getAdjacentEpisodes(activeModalEpisode.id);
    if (next) playInBrowser(next.id);
  }
}

function cancelPlayNext() {
  if (upNextCountdownInterval) {
    clearInterval(upNextCountdownInterval);
    upNextCountdownInterval = null;
  }
  const card = document.getElementById("player-up-next-card");
  if (card) card.style.display = "none";
}

// In-Browser Playback Modal
function playInBrowser(episodeId) {
  const ep = catalog.episodes.find(e => e.id === episodeId);
  if (!ep) return;

  const playerModal = document.getElementById("player-modal");
  const video = document.getElementById("html-video-player");
  const epTitle = document.getElementById("player-ep-title");

  epTitle.innerText = `${ep.episode_label} • ${ep.title}`;

  // Dismiss any existing Up Next card
  cancelPlayNext();

  // Clear existing tracks
  while (video.firstChild) {
    video.removeChild(video.firstChild);
  }

  // Setup video source
  const source = document.createElement("source");
  source.src = `/api/stream/${ep.id}`;
  source.type = "video/mp4";
  video.appendChild(source);

  // Setup Subtitle Track automatically
  if (ep.has_subtitles) {
    const track = document.createElement("track");
    track.kind = "subtitles";
    track.label = "English (Auto-Loaded)";
    track.srclang = "en";
    track.src = `/api/subtitles/${ep.id}`;
    track.default = true;
    video.appendChild(track);
  }

  video.load();

  // Resume from saved timestamp
  const startTime = (ep.progress && ep.progress.current_time > 15 && !ep.progress.completed)
    ? ep.progress.current_time - 3
    : 0;

  video.onloadedmetadata = () => {
    if (startTime > 0) {
      video.currentTime = startTime;
    }
    video.play().catch(e => console.log("Autoplay blocked or waiting:", e));
  };

  // When episode ends, automatically prompt/play next episode
  video.onended = () => {
    saveProgressToServer(ep.id, Math.floor(video.duration || 1320), Math.floor(video.duration || 1320), true);
    const { next } = getAdjacentEpisodes(ep.id);
    if (next) {
      showUpNextCard(next);
    } else {
      showToast("🎉 You've finished all episodes in Sanctuary!");
    }
  };

  // Auto save progress every 4 seconds
  if (browserPlayerSaveInterval) clearInterval(browserPlayerSaveInterval);
  browserPlayerSaveInterval = setInterval(() => {
    if (!video.paused && video.currentTime > 5 && video.duration > 0) {
      saveProgressToServer(ep.id, Math.floor(video.currentTime), Math.floor(video.duration));
    }
  }, 4000);

  // Remember window fullscreen state before entering in-browser player
  wasWindowFullscreenBeforePlayer = Boolean(isAppFullscreen);

  // Blur any active element so Space doesn't trigger previously focused button
  if (document.activeElement && document.activeElement.blur) {
    document.activeElement.blur();
  }

  // Double-click video to toggle fullscreen
  video.ondblclick = (e) => {
    e.preventDefault();
    toggleAppFullscreen();
  };

  // Intercept Space / K directly on video so native controls don't double-toggle
  video.onkeydown = (e) => {
    if (e.key === " " || e.code === "Space" || e.key.toLowerCase() === "k") {
      e.preventDefault();
      e.stopPropagation();
      if (!e.repeat) {
        toggleVideoPlayPause();
      }
    }
  };

  // Enter true borderless native fullscreen
  setAppFullscreen(true);

  // Update Next/Prev episode buttons and edge navigation
  updatePlayerNavigationUI(ep.id);

  // Setup auto-hide controls overlay on idle
  const wrapper = document.getElementById("player-wrapper");
  if (wrapper) {
    wrapper.classList.remove("idle");
    wrapper.onmousemove = () => resetPlayerIdle("player-wrapper");
    wrapper.onpointermove = () => resetPlayerIdle("player-wrapper");
    resetPlayerIdle("player-wrapper");
  }

  playerModal.classList.add("open");
  activeModalEpisode = ep;
}

function closePlayerModal(e = null) {
  const playerModal = document.getElementById("player-modal");
  const video = document.getElementById("html-video-player");

  cancelPlayNext();

  if (activeModalEpisode && video.currentTime > 5 && video.duration > 0) {
    saveProgressToServer(activeModalEpisode.id, Math.floor(video.currentTime), Math.floor(video.duration));
  }

  if (browserPlayerSaveInterval) {
    clearInterval(browserPlayerSaveInterval);
    browserPlayerSaveInterval = null;
  }

  if (playerIdleTimer) {
    clearTimeout(playerIdleTimer);
    playerIdleTimer = null;
  }

  const wrapper = document.getElementById("player-wrapper");
  if (wrapper) {
    wrapper.classList.remove("idle");
    wrapper.onmousemove = null;
    wrapper.onpointermove = null;
  }

  video.pause();
  video.src = "";
  playerModal.classList.remove("open");

  // Restore previous windowed state if window wasn't fullscreen prior to playback
  if (!wasWindowFullscreenBeforePlayer && isAppFullscreen) {
    setAppFullscreen(false);
  }

  setTimeout(fetchCatalog, 500);
}

function switchCurrentToVLC() {
  if (!activeModalEpisode) return;
  const video = document.getElementById("html-video-player");
  const currTime = Math.floor(video.currentTime);
  const dur = Math.floor(video.duration || 1320);

  saveProgressToServer(activeModalEpisode.id, currTime, dur);
  const epId = activeModalEpisode.id;
  closePlayerModal();
  setTimeout(() => playInVLC(epId, true), 300);
}

// Progress saving helper
async function saveProgressToServer(episodeId, currentTime, duration, completed = false) {
  try {
    const isCompleted = Boolean(completed || (duration > 0 && currentTime / duration > 0.92));
    await fetch("/api/progress/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        episode_id: episodeId,
        current_time: currentTime,
        duration: duration,
        completed: isCompleted
      })
    });
  } catch (e) {
    console.error("Failed to sync progress:", e);
  }
}

// Episode Details Modal
function openDetailsModal(episodeId) {
  const ep = catalog.episodes.find(e => e.id === episodeId);
  if (!ep) return;

  activeModalEpisode = ep;
  const modal = document.getElementById("details-modal");
  const prog = ep.progress;

  document.getElementById("modal-hero-img").src = ep.thumbnail;
  document.getElementById("modal-ep-label").innerText = ep.episode_label;
  document.getElementById("modal-title").innerText = ep.title;
  document.getElementById("modal-runtime").innerText = ep.runtime;
  document.getElementById("modal-airdate").innerText = ep.airdate || "2016";
  document.getElementById("modal-synopsis").innerText = ep.summary;
  document.getElementById("modal-filesize").innerText = `${ep.filesize_mb} MB`;
  document.getElementById("modal-filename").innerText = ep.filename;

  // VLC play button in modal
  const vlcBtn = document.getElementById("modal-vlc-btn");
  vlcBtn.innerHTML = `<i class="fa-solid fa-play"></i> ${prog.current_time > 15 && !prog.completed ? `Resume at ${prog.formatted_current_time}` : 'Play with VLC'}`;
  vlcBtn.onclick = () => {
    closeDetailsModal();
    playInVLC(ep.id, true);
  };

  // In-Browser button in modal
  const browserBtn = document.getElementById("modal-browser-btn");
  browserBtn.onclick = () => {
    closeDetailsModal();
    playInBrowser(ep.id);
  };

  // Watched button state
  const markBtn = document.getElementById("modal-mark-btn");
  markBtn.innerHTML = `<i class="fa-solid ${prog.completed ? 'fa-eye-slash' : 'fa-check'}"></i> ${prog.completed ? 'Mark Unwatched' : 'Mark Watched'}`;

  // Progress box
  const progBox = document.getElementById("modal-progress-box");
  if (prog.current_time > 10) {
    progBox.style.display = "block";
    document.getElementById("modal-progress-time").innerText = prog.formatted_current_time;
    document.getElementById("modal-duration-time").innerText = prog.formatted_duration;
    document.getElementById("modal-progress-pct").innerText = `${prog.progress_pct}% watched`;
    document.getElementById("modal-progress-bar").style.width = `${prog.progress_pct}%`;
  } else {
    progBox.style.display = "none";
  }

  modal.classList.add("open");
}

function closeDetailsModal(e = null) {
  document.getElementById("details-modal").classList.remove("open");
  activeModalEpisode = null;
}

function toggleModalWatched() {
  if (!activeModalEpisode) return;
  const isWatched = activeModalEpisode.progress.completed;
  toggleWatched(activeModalEpisode.id, !isWatched);
  closeDetailsModal();
}

function resetModalProgress() {
  if (!activeModalEpisode) return;
  resetProgress(activeModalEpisode.id);
  closeDetailsModal();
}

// Mark watched / reset progress actions
async function toggleWatched(episodeId, watched) {
  try {
    await fetch("/api/progress/mark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId, watched: watched })
    });
    showToast(watched ? "✓ Marked as Watched" : "Marked as Unwatched");
    fetchCatalog();
  } catch (e) {
    showToast("Error updating status");
  }
}

async function resetProgress(episodeId) {
  try {
    await fetch("/api/progress/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId, watched: false })
    });
    showToast("↺ Progress reset to 0:00");
    fetchCatalog();
  } catch (e) {
    showToast("Error resetting progress");
  }
}

// VLC Status Polling & Floating Remote Control Bar
function startVlcStatusPolling() {
  if (vlcPollInterval) clearInterval(vlcPollInterval);

  vlcPollInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/vlc/status");
      if (!res.ok) return;
      const status = await res.json();

      const remoteBar = document.getElementById("vlc-remote-bar");
      const statusPill = document.getElementById("vlc-status-pill");
      const statusText = document.getElementById("vlc-status-text");

      if (status.is_active) {
        if (remoteBar) remoteBar.classList.add("active");
        if (statusText) statusText.innerText = `VLC Active: ${status.status}`;
        if (statusPill) {
          const pulseDot = statusPill.querySelector(".pulse-dot");
          if (pulseDot) pulseDot.classList.add("playing");
        }

        // Update Remote Bar UI
        document.getElementById("remote-title").innerText = status.title || "2 Broke Girls";
        document.getElementById("remote-curr-time").innerText = formatTime(status.time);
        document.getElementById("remote-total-time").innerText = formatTime(status.length);

        const pct = status.length > 0 ? (status.time / status.length) * 100 : 0;
        document.getElementById("remote-progress-fill").style.width = `${pct}%`;

        const playPauseBtn = document.getElementById("remote-play-pause");
        if (status.status === "paused") {
          playPauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
        } else {
          playPauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        }
      } else {
        if (remoteBar) remoteBar.classList.remove("active");
        if (statusText) statusText.innerText = "VLC Engine Ready";
        if (statusPill) {
          const pulseDot = statusPill.querySelector(".pulse-dot");
          if (pulseDot) pulseDot.classList.remove("playing");
        }
      }
    } catch (e) {
      // Ignore poll failures
    }
  }, 1500);
}

// Remote Controls for VLC
async function sendVlcControl(action, val = null) {
  try {
    await fetch("/api/vlc/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action, value: val })
    });
  } catch (e) {
    console.error("VLC control error:", e);
  }
}

// Refresh Catalog Button
function refreshCatalog() {
  showToast("↻ Refreshing episodes, YouTube videos & progress...");
  fetchCatalog();
  fetchYouTubeCatalog();
}

// Toast notification helper
function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.innerText = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3200);
}

// Format seconds to mm:ss or hh:mm:ss
function formatTime(seconds) {
  if (!seconds || seconds <= 0) return "00:00";
  const sec = parseInt(seconds, 10);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  if (h > 0) {
    return `${h}:${remM.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

// Reliable debounced play/pause toggler
let lastPlayPauseToggleTime = 0;
function toggleVideoPlayPause() {
  const now = Date.now();
  if (now - lastPlayPauseToggleTime < 350) {
    return; // Prevent double-trigger within 350ms
  }
  lastPlayPauseToggleTime = now;

  const video = document.getElementById("html-video-player");
  if (!video) return;

  if (video.paused) {
    video.play().then(() => {
      showToast("▶ Play");
    }).catch(e => console.log("Play error:", e));
  } else {
    video.pause();
    showToast("⏸ Pause");
  }
}

// Keyboard shortcuts for theater feel
function setupKeyboardShortcuts() {
  // Prevent clicked buttons from retaining focus so Space doesn't re-trigger them
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (btn && btn.blur) btn.blur();
  }, true);

  document.addEventListener("keydown", (e) => {
    // If typing in search box, ignore
    if (document.activeElement && document.activeElement.tagName === "INPUT") return;

    const playerModal = document.getElementById("player-modal");
    const isPlayerOpen = Boolean(playerModal && playerModal.classList.contains("open"));
    const ytModal = document.getElementById("yt-player-modal");
    const isYtOpen = Boolean(ytModal && ytModal.classList.contains("open"));

    if (isPlayerOpen) {
      resetPlayerIdle("player-wrapper");
    } else if (isYtOpen) {
      resetPlayerIdle("yt-player-wrapper");
    }

    if (e.key === "Escape") {
      const detailsModal = document.getElementById("details-modal");
      const addYtModal = document.getElementById("add-yt-modal");

      if (isYtOpen) {
        closeYouTubePlayerModal();
      } else if (addYtModal && addYtModal.classList.contains("open")) {
        closeAddYouTubeModal();
      } else if (isPlayerOpen) {
        closePlayerModal();
      } else if (detailsModal && detailsModal.classList.contains("open")) {
        closeDetailsModal();
      } else if (isAppFullscreen) {
        toggleAppFullscreen();
      }
    } else if (e.key === "F11" || (e.key.toLowerCase() === "f" && !e.ctrlKey && !e.metaKey)) {
      // Toggle Fullscreen
      toggleAppFullscreen();
      e.preventDefault();
    } else if (e.key === " " || e.code === "Space" || (isPlayerOpen && e.key.toLowerCase() === "k")) {
      // Prevent browser default scroll and button re-activation
      e.preventDefault();
      if (e.repeat) return; // Prevent OS key hold repeat from fluttering play/pause
      if (isPlayerOpen) {
        toggleVideoPlayPause();
      } else if (!isYtOpen) {
        // Toggle VLC
        sendVlcControl("toggle");
      }
      return;
    } else if (isPlayerOpen) {
      const video = document.getElementById("html-video-player");
      if (video) {
        if (e.key === "ArrowLeft") {
          video.currentTime = Math.max(0, video.currentTime - 5);
          showToast(`⏪ -5s (${formatSeconds(video.currentTime)})`);
          e.preventDefault();
        } else if (e.key === "ArrowRight") {
          video.currentTime = Math.min(video.duration || 99999, video.currentTime + 5);
          showToast(`⏩ +5s (${formatSeconds(video.currentTime)})`);
          e.preventDefault();
        } else if (e.key === "ArrowUp") {
          video.volume = Math.min(1, Math.round((video.volume + 0.05) * 100) / 100);
          showToast(`🔊 Volume ${Math.round(video.volume * 100)}%`);
          e.preventDefault();
        } else if (e.key === "ArrowDown") {
          video.volume = Math.max(0, Math.round((video.volume - 0.05) * 100) / 100);
          showToast(`🔉 Volume ${Math.round(video.volume * 100)}%`);
          e.preventDefault();
        } else if (e.key.toLowerCase() === "m") {
          video.muted = !video.muted;
          showToast(video.muted ? "🔇 Muted" : "🔊 Unmuted");
          e.preventDefault();
        } else if (e.key.toLowerCase() === "n" || e.key === "]") {
          playNextEpisode();
          e.preventDefault();
        } else if (e.key.toLowerCase() === "p" || e.key === "[") {
          playPreviousEpisode();
          e.preventDefault();
        }
      }
    }
  });
}

// ==========================================
// YouTube Sanctuary Hub Functions
// ==========================================

async function fetchYouTubeCatalog() {
  try {
    const res = await fetch("/api/youtube");
    if (!res.ok) throw new Error("Failed to load YouTube catalog");
    const data = await res.json();
    youtubeCatalog.videos = data.videos || [];
    youtubeCatalog.categories = data.categories || [];
    renderYouTubeCategories();
    renderYouTubeVideos();
    renderContinueWatching();
  } catch (err) {
    console.error("Error loading YouTube catalog:", err);
  }
}

function renderYouTubeCategories() {
  const container = document.getElementById("yt-category-tabs");
  if (!container) return;

  const cats = ["all", ...youtubeCatalog.categories];
  const allCount = youtubeCatalog.videos.length;

  container.innerHTML = cats.map(cat => {
    const label = cat === "all" ? "All YouTube Videos" : cat;
    const count = cat === "all" ? allCount : youtubeCatalog.videos.filter(v => v.category === cat).length;
    const activeClass = youtubeCatalog.currentCategory === cat ? "active" : "";
    return `
      <button class="season-tab ${activeClass}" onclick="selectYouTubeCategory('${cat}')">
        ${label} <span class="count-pill">${count}</span>
      </button>
    `;
  }).join("");
}

function selectYouTubeCategory(cat) {
  youtubeCatalog.currentCategory = cat;
  renderYouTubeCategories();
  renderYouTubeVideos();
}

function renderYouTubeVideos() {
  const grid = document.getElementById("youtube-grid");
  if (!grid) return;

  let filtered = youtubeCatalog.videos;

  // Filter by category
  if (youtubeCatalog.currentCategory !== "all") {
    filtered = filtered.filter(v => v.category === youtubeCatalog.currentCategory);
  }

  // Filter by search query
  if (searchQuery.trim() !== "") {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter(v => 
      v.title.toLowerCase().includes(q) ||
      (v.channel && v.channel.toLowerCase().includes(q)) ||
      (v.description && v.description.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 50px 20px; color: var(--text-muted);">
        <i class="fa-brands fa-youtube" style="font-size: 40px; color: #555; margin-bottom: 14px;"></i>
        <p style="font-size: 15px;">No YouTube videos found in this category or search.</p>
        <button class="btn btn-sm btn-primary" style="margin-top: 14px;" onclick="openAddYouTubeModal()">
          <i class="fa-solid fa-plus"></i> Add Your First YouTube Video
        </button>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(vid => {
    return `
      <div class="episode-card yt-card" onclick="playYouTubeInApp('${vid.id}', '${escapeHtml(vid.title)}', '${escapeHtml(vid.channel)}')">
        <div class="episode-thumb-container">
          <img src="${vid.thumbnail}" alt="${escapeHtml(vid.title)}" loading="lazy">
          <span class="yt-badge-tag"><i class="fa-brands fa-youtube"></i> YouTube</span>
          <span class="ep-duration-overlay">${vid.duration || 'Video'}</span>
          <div class="continue-play-overlay">
            <div class="play-circle-icon"><i class="fa-solid fa-play"></i></div>
          </div>
        </div>

        <div class="ep-card-body">
          <div class="ep-card-title-row">
            <h3 class="ep-card-title" title="${escapeHtml(vid.title)}">${vid.title}</h3>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span class="yt-channel-tag"><i class="fa-solid fa-circle-check"></i> ${vid.channel}</span>
            <span style="font-size: 11px; color: var(--text-muted);">${vid.category}</span>
          </div>

          <p class="ep-card-summary">${vid.description || 'Watch now in PlayerSlayer Sanctuary.'}</p>

          <div class="ep-card-actions">
            <button class="btn btn-primary" onclick="event.stopPropagation(); playYouTubeInApp('${vid.id}', '${escapeHtml(vid.title)}', '${escapeHtml(vid.channel)}')" title="Watch in App Theater">
              <i class="fa-solid fa-play"></i> Watch In-App
            </button>
            <button class="icon-action-btn" onclick="event.stopPropagation(); playYouTubeInVLC('${vid.id}')" title="Stream directly in VLC Media Player with Hardware Acceleration">
              <i class="fa-solid fa-arrow-up-right-from-square"></i>
            </button>
            <button class="icon-action-btn" onclick="event.stopPropagation(); deleteYouTubeVideo('${vid.id}')" title="Remove video from Sanctuary">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function scrollToSection(sectionId, navElem = null) {
  const section = document.getElementById(sectionId);
  if (section) {
    section.scrollIntoView({ behavior: 'smooth' });
  }
  if (navElem) {
    setActiveNav(navElem);
  }
}

// Add YouTube Video Modal
function openAddYouTubeModal() {
  const modal = document.getElementById("add-yt-modal");
  document.getElementById("yt-add-url").value = "";
  document.getElementById("yt-add-title").value = "";
  document.getElementById("yt-add-desc").value = "";
  document.getElementById("yt-preview-box").style.display = "none";
  modal.classList.add("open");
}

function closeAddYouTubeModal(e = null) {
  document.getElementById("add-yt-modal").classList.remove("open");
}

let ytPreviewTimer = null;
function previewYouTubeInput(val) {
  clearTimeout(ytPreviewTimer);
  const previewBox = document.getElementById("yt-preview-box");
  const url = val.trim();
  if (url.length < 11) {
    previewBox.style.display = "none";
    return;
  }

  ytPreviewTimer = setTimeout(async () => {
    try {
      const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`;
      const res = await fetch(oembedUrl);
      if (res.ok) {
        const data = await res.json();
        document.getElementById("yt-preview-thumb").src = data.thumbnail_url;
        document.getElementById("yt-preview-channel").innerText = data.author_name;
        document.getElementById("yt-preview-title").innerText = data.title;
        previewBox.style.display = "flex";
      }
    } catch (e) {
      // ignore
    }
  }, 400);
}

async function submitAddYouTube() {
  const urlInput = document.getElementById("yt-add-url");
  const titleInput = document.getElementById("yt-add-title");
  const catInput = document.getElementById("yt-add-category");
  const descInput = document.getElementById("yt-add-desc");
  const submitBtn = document.getElementById("yt-submit-btn");

  const url = urlInput.value.trim();
  if (!url) {
    showToast("Please enter a YouTube link or Video ID");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';

  try {
    const res = await fetch("/api/youtube/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        title: titleInput.value.trim() || null,
        category: catInput.value,
        description: descInput.value.trim() || null
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to add video");

    closeAddYouTubeModal();
    showToast("✓ YouTube Video Added to Sanctuary!");
    await fetchYouTubeCatalog();

    // Scroll to YouTube section
    scrollToSection("youtube-section");
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Add to Sanctuary';
  }
}

async function deleteYouTubeVideo(videoId) {
  if (!confirm("Are you sure you want to remove this YouTube video from your Sanctuary?")) return;

  try {
    const res = await fetch(`/api/youtube/${videoId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete video");
    showToast("✓ Video removed from Sanctuary");
    fetchYouTubeCatalog();
  } catch (e) {
    showToast("Error deleting video");
  }
}

// In-App YouTube Theater Player
function playYouTubeInApp(videoId, title, channel) {
  const modal = document.getElementById("yt-player-modal");
  const iframe = document.getElementById("yt-iframe");
  const titleElem = document.getElementById("yt-player-title");

  activeYouTubeVideo = { id: videoId, title: title, channel: channel };
  titleElem.innerHTML = `<span style="color: #FF5555; font-weight: 700;">${channel}:</span> ${title}`;

  // Autoplay YouTube embed
  iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&enablejsapi=1&rel=0&modestbranding=1`;

  // Remember fullscreen state and enter borderless fullscreen
  wasWindowFullscreenBeforePlayer = Boolean(isAppFullscreen);
  setAppFullscreen(true);

  // Setup auto-hide controls overlay on idle
  const wrapper = document.getElementById("yt-player-wrapper");
  if (wrapper) {
    wrapper.classList.remove("idle");
    wrapper.onmousemove = () => resetPlayerIdle("yt-player-wrapper");
    wrapper.onpointermove = () => resetPlayerIdle("yt-player-wrapper");
    resetPlayerIdle("yt-player-wrapper");
  }

  modal.classList.add("open");
}

function closeYouTubePlayerModal(e = null) {
  const modal = document.getElementById("yt-player-modal");
  const iframe = document.getElementById("yt-iframe");
  iframe.src = ""; // stop playback immediately
  modal.classList.remove("open");
  activeYouTubeVideo = null;

  if (playerIdleTimer) {
    clearTimeout(playerIdleTimer);
    playerIdleTimer = null;
  }

  const wrapper = document.getElementById("yt-player-wrapper");
  if (wrapper) {
    wrapper.classList.remove("idle");
    wrapper.onmousemove = null;
    wrapper.onpointermove = null;
  }

  // Restore previous windowed state
  if (!wasWindowFullscreenBeforePlayer && isAppFullscreen) {
    setAppFullscreen(false);
  }
}

// VLC YouTube Streaming
async function playYouTubeInVLC(videoId) {
  showToast("🚀 Streaming YouTube video in VLC with Hardware Codecs...");
  try {
    const res = await fetch("/api/youtube/play-vlc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "VLC launch error");

    showToast(`▶ Streaming "${data.title}" in VLC Player`);
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

function switchYouTubeToVLC() {
  if (!activeYouTubeVideo) return;
  const vidId = activeYouTubeVideo.id;
  closeYouTubePlayerModal();
  setTimeout(() => playYouTubeInVLC(vidId), 300);
}

// Open YouTube directly inside PlayerSlayer's Sanctuary (Integrated, Seamless & Ad-Free)
async function openYouTubePortal(mode = 'home', url = null) {
  let targetUrl = url;
  if (!targetUrl) {
    if (mode === 'signin' || mode === 'login') {
      targetUrl = "https://www.youtube.com/signin";
    } else if (mode === 'account') {
      targetUrl = "https://www.youtube.com/account";
    } else if (mode === 'switch') {
      targetUrl = "https://accounts.google.com/AccountChooser?service=youtube";
    } else if (mode === 'subscriptions') {
      targetUrl = "https://www.youtube.com/feed/subscriptions";
    } else if (mode === 'history') {
      targetUrl = "https://www.youtube.com/feed/history";
    } else if (mode === 'library') {
      targetUrl = "https://www.youtube.com/feed/library";
    } else if (mode === 'tv') {
      targetUrl = "https://www.youtube.com/tv";
    } else {
      targetUrl = "https://www.youtube.com";
    }
  }

  showToast("Opening YouTube in Sanctuary...");

  try {
    window.location.href = targetUrl;
    return;
  } catch (e) {
    console.warn("window.location.href error, falling back to pywebview api:", e);
  }

  if (window.pywebview && window.pywebview.api && window.pywebview.api.navigate) {
    try {
      window.pywebview.api.navigate(targetUrl);
      return;
    } catch (e) {
      console.warn("PyWebView navigate error:", e);
    }
  }

  try {
    fetch("/api/youtube/open-window", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode, url: targetUrl })
    }).catch(function(){});
  } catch (err) {}
}

// Quick Stream Video by URL or Search (Theater, VLC, or Portal)
function quickStreamYouTube(target = 'theater') {
  const input = document.getElementById("yt-search-input");
  if (!input) return;
  const val = input.value.trim();
  if (!val) {
    showToast("Please enter a video link or search query");
    return;
  }

  let videoId = null;
  const match = val.match(/(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})/);
  if (match) {
    videoId = match[1];
  } else if (val.length === 11 && !val.includes(" ")) {
    videoId = val;
  }

  if (target === 'theater') {
    if (videoId) {
      playYouTubeInApp(videoId, "Video Stream", "YouTube");
    } else {
      openYouTubePortal('search', val);
    }
  } else if (target === 'vlc') {
    if (videoId) {
      playYouTubeInVLC(videoId);
    } else {
      showToast("Please enter a direct YouTube link for VLC playback");
    }
  } else {
    openYouTubePortal('search', val);
  }
}
