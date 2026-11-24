import os
import sys
import time
import socket
import webbrowser
import threading
import subprocess
import atexit
from pathlib import Path

# Initialize WinForms / CLR on main STA thread before GUI starts
try:
    import clr
    clr.AddReference('System.Windows.Forms')
except Exception:
    pass

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

LOG_FILE = PROJECT_DIR / "app.log"

# Safe stream logger that never crashes on cp1252 or pythonw None streams
class SafeStream:
    def __init__(self, primary, filepath):
        self.primary = primary
        self.filepath = filepath
        self._file = None

    def _get_file(self):
        if self._file is None:
            try:
                self._file = open(self.filepath, "a", encoding="utf-8", buffering=1)
            except Exception:
                pass
        return self._file

    def write(self, s):
        f = self._get_file()
        if f:
            try:
                f.write(s)
            except Exception:
                pass
        if self.primary and hasattr(self.primary, "write"):
            try:
                self.primary.write(s)
            except Exception:
                # If console encoding fails, encode with ascii ignore
                try:
                    self.primary.write(s.encode("ascii", errors="replace").decode("ascii"))
                except Exception:
                    pass

    def flush(self):
        f = self._get_file()
        if f:
            try:
                f.flush()
            except Exception:
                pass
        if self.primary and hasattr(self.primary, "flush"):
            try:
                self.primary.flush()
            except Exception:
                pass

sys.stdout = SafeStream(sys.stdout, LOG_FILE)
sys.stderr = SafeStream(sys.stderr, LOG_FILE)

MUTEX_NAME = "Local\\PlayerSlayersSanctuary_SingleInstance_Mutex"
_mutex_handle = None

def acquire_single_instance_mutex() -> bool:
    global _mutex_handle
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        ERROR_ALREADY_EXISTS = 183
        
        mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        
        if last_error == ERROR_ALREADY_EXISTS:
            print("[INSTANCE] Another instance of PlayerSlayer's Sanctuary is already running.")
            hwnd = user32.FindWindowW(None, "PlayerSlayer's Sanctuary")
            if hwnd:
                user32.ShowWindow(hwnd, 9) # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                print("[INSTANCE] Brought existing window to front.")
            if mutex:
                kernel32.CloseHandle(mutex)
            return False
        
        _mutex_handle = mutex
        return True
    except Exception as e:
        print(f"[INSTANCE] Mutex error: {e}")
        return True

def release_single_instance_mutex():
    global _mutex_handle
    if _mutex_handle:
        try:
            import ctypes
            ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
        except Exception:
            pass

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

SERVER_PROCESS = None
SERVER_LOG_FILE = PROJECT_DIR / "server.log"
_server_log_handle = None

def start_server_subprocess(port: int = 7890):
    global SERVER_PROCESS, _server_log_handle
    server_script = PROJECT_DIR / "server.py"
    print(f"[SERVER] Starting isolated server process on http://127.0.0.1:{port}...")
    try:
        _server_log_handle = open(SERVER_LOG_FILE, "a", encoding="utf-8")
    except Exception:
        _server_log_handle = subprocess.DEVNULL

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    SERVER_PROCESS = subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(PROJECT_DIR),
        stdout=_server_log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags
    )
    return SERVER_PROCESS

def cleanup_server():
    global SERVER_PROCESS, _server_log_handle
    if SERVER_PROCESS and SERVER_PROCESS.poll() is None:
        try:
            SERVER_PROCESS.terminate()
            SERVER_PROCESS.wait(timeout=2)
        except Exception:
            try:
                SERVER_PROCESS.kill()
            except Exception:
                pass
    if _server_log_handle and hasattr(_server_log_handle, "close"):
        try:
            _server_log_handle.close()
        except Exception:
            pass
    cleanup_port(7890)
    cleanup_profile_locks()

atexit.register(cleanup_server)

class AppApi:
    def __init__(self, holder):
        self.holder = holder
        self._is_fullscreen = False

    def toggle_fullscreen(self):
        w = self.holder.get("window")
        if w:
            try:
                form = getattr(w, "native", None)
                if form:
                    form.toggle_fullscreen()
                    self._is_fullscreen = getattr(form, "is_fullscreen", False)
                else:
                    w.toggle_fullscreen()
                    self._is_fullscreen = not self._is_fullscreen
                return self._is_fullscreen
            except Exception as e:
                print(f"[UI ERROR] toggle_fullscreen: {e}")
                return False
        return False

    def set_fullscreen(self, enable: bool):
        w = self.holder.get("window")
        if w:
            try:
                form = getattr(w, "native", None)
                curr = getattr(form, "is_fullscreen", self._is_fullscreen) if form else self._is_fullscreen
                if bool(enable) != curr:
                    if form:
                        form.toggle_fullscreen()
                        self._is_fullscreen = getattr(form, "is_fullscreen", False)
                    else:
                        w.toggle_fullscreen()
                        self._is_fullscreen = bool(enable)
                else:
                    self._is_fullscreen = curr
                return self._is_fullscreen
            except Exception as e:
                print(f"[UI ERROR] set_fullscreen: {e}")
                return False
        return False

    def is_fullscreen(self):
        w = self.holder.get("window")
        if w:
            form = getattr(w, "native", None)
            if form:
                return getattr(form, "is_fullscreen", self._is_fullscreen)
        return self._is_fullscreen

    def navigate(self, url: str):
        print(f"[UI] AppApi navigate requested for: {url}")
        w = self.holder.get("window")
        if w:
            try:
                w.load_url(url)
                return True
            except Exception as e:
                print(f"[UI ERROR] navigate: {e}")
                return False
        return False

    def open_browser(self, url: str):
        print(f"[UI] AppApi open_browser redirected to in-app navigate: {url}")
        return self.navigate(url)

    def open_youtube_in_brave(self, url: str):
        print(f"[UI] AppApi open_youtube redirected to in-app navigate: {url}")
        return self.navigate(url)

PROFILE_DIR = PROJECT_DIR / "data" / "browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(PROFILE_DIR.resolve())

YOUTUBE_ADBLOCK_SCRIPTLET = r"""
(function() {
    'use strict';

    // 1. Safety check: Only execute on YouTube domains
    const host = window.location.hostname || '';
    if (!host.includes('youtube.com') && !host.includes('googlevideo.com')) {
        return;
    }

    // 2. Brave Shields Player Response Sanitizer (Deep removal of all ad placements & break definitions)
    function sanitizePlayerResponse(obj) {
        if (!obj || typeof obj !== 'object') return obj;
        try {
            delete obj.adPlacements;
            delete obj.adSlots;
            delete obj.playerAds;
            delete obj.adBreakHeartbeatParams;
            delete obj.adBreakParams;
            delete obj.adPlacementRenderer;
            if (obj.playerConfig) {
                delete obj.playerConfig.adConfig;
                delete obj.playerConfig.adPlacementConfig;
            }
            if (obj.playbackTracking) {
                delete obj.playbackTracking.videostatsPlaybackUrl;
                delete obj.playbackTracking.videostatsDelayplayUrl;
                delete obj.playbackTracking.videostatsWatchtimeUrl;
                delete obj.playbackTracking.qoeUrl;
                delete obj.playbackTracking.atrUrl;
            }
        } catch (e) {}
        return obj;
    }

    // 3. Document-Start Interceptor: Catch ytInitialPlayerResponse before player instantiates
    let _playerResp = undefined;
    try {
        Object.defineProperty(window, 'ytInitialPlayerResponse', {
            get: function() { return _playerResp; },
            set: function(val) {
                _playerResp = sanitizePlayerResponse(val);
            },
            configurable: true,
            enumerable: true
        });
    } catch(e) {}

    // Hook ytInitialData for clean feeds without sponsor cards
    let _initialData = undefined;
    try {
        Object.defineProperty(window, 'ytInitialData', {
            get: function() { return _initialData; },
            set: function(val) { _initialData = val; },
            configurable: true,
            enumerable: true
        });
    } catch(e) {}

    // 4. Hook window.fetch for SPA / In-App Video Navigation (/youtubei/v1/player)
    if (!window._ps_fetch_hooked) {
        window._ps_fetch_hooked = true;
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const url = (typeof args[0] === 'string') ? args[0] : (args[0] && args[0].url ? args[0].url : '');

            // Block ad network telemetry & beacons
            if (
                url.includes('/api/stats/ads') || 
                url.includes('/pagead/') || 
                url.includes('/ptracking') || 
                url.includes('doubleclick.net') || 
                url.includes('googleads') ||
                url.includes('/youtubei/v1/att/')
            ) {
                return new Response(JSON.stringify({}), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                });
            }

            const response = await originalFetch.apply(this, args);

            // Strip ad structures from /player responses before player receives them
            if (url.includes('/youtubei/v1/player')) {
                try {
                    const clone = response.clone();
                    const json = await clone.json();
                    const cleaned = sanitizePlayerResponse(json);
                    return new Response(JSON.stringify(cleaned), {
                        status: response.status,
                        statusText: response.statusText,
                        headers: response.headers
                    });
                } catch(e) {
                    return response;
                }
            }
            return response;
        };
    }

    // 5. Hook XMLHttpRequest for player requests
    if (!window._ps_xhr_hooked) {
        window._ps_xhr_hooked = true;
        const origOpen = XMLHttpRequest.prototype.open;
        const origSend = XMLHttpRequest.prototype.send;

        XMLHttpRequest.prototype.open = function(method, url) {
            this._ps_url = typeof url === 'string' ? url : '';
            return origOpen.apply(this, arguments);
        };

        XMLHttpRequest.prototype.send = function() {
            if (this._ps_url && (
                this._ps_url.includes('/api/stats/ads') || 
                this._ps_url.includes('/pagead/') || 
                this._ps_url.includes('/ptracking') || 
                this._ps_url.includes('doubleclick.net') || 
                this._ps_url.includes('googleads')
            )) {
                return;
            }

            if (this._ps_url && this._ps_url.includes('/youtubei/v1/player')) {
                this.addEventListener('readystatechange', function() {
                    if (this.readyState === 4 && this.status === 200) {
                        try {
                            const data = JSON.parse(this.responseText);
                            const cleaned = sanitizePlayerResponse(data);
                            Object.defineProperty(this, 'responseText', { value: JSON.stringify(cleaned) });
                            Object.defineProperty(this, 'response', { value: JSON.stringify(cleaned) });
                        } catch(e) {}
                    }
                });
            }
            return origSend.apply(this, arguments);
        };
    }

    // 6. Inject CSS to hide all banner ads, sponsored items & promo overlays
    function injectAdStyles() {
        if (document.getElementById('ps-pure-adblock')) return;
        const target = document.head || document.documentElement;
        if (!target) return;

        const style = document.createElement('style');
        style.id = 'ps-pure-adblock';
        style.textContent = `
            ytd-ad-slot-renderer,
            ytd-in-feed-ad-layout-renderer,
            ytd-banner-promo-renderer,
            ytd-statement-banner-renderer,
            ytd-rich-item-renderer:has(ytd-ad-slot-renderer),
            ytd-rich-item-renderer:has(.ytd-ad-slot-renderer),
            ytd-rich-section-renderer:has(ytd-ad-slot-renderer),
            .ytd-ad-slot-renderer,
            #player-ads,
            .ytp-ad-module,
            .ytp-ad-overlay-container,
            #masthead-ad,
            ytd-companion-ad-renderer,
            tp-yt-paper-dialog:has(#feedback),
            ytd-enforcement-message-view-model,
            yt-playability-error-supported-renderers,
            .video-ads,
            .ytp-ad-text,
            .ytp-ad-preview-container,
            .ytp-ad-skip-button-container,
            #panels:has(ytd-ads-engagement-panel-content-renderer) {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                opacity: 0 !important;
                pointer-events: none !important;
            }
        `;
        target.appendChild(style);
    }
    if (document.head || document.documentElement) injectAdStyles();
    document.addEventListener('DOMContentLoaded', injectAdStyles);

    // 7. Instant Real-Time Video Ad Muter & Skipper (Backup safety net)
    let lastMutedAd = false;
    function instantSkipAds() {
        try {
            const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
            const video = document.querySelector('video.html5-main-video') || document.querySelector('video');

            if (!player || !video) return;

            const isAd = player.classList.contains('ad-showing') || 
                         player.classList.contains('ad-interrupting') ||
                         document.querySelector('.ytp-ad-player-overlay') !== null;

            if (isAd) {
                // Instantly mute ad so zero sound is heard
                if (!video.muted) {
                    video.muted = true;
                    lastMutedAd = true;
                }

                // Fast-forward ad to completion
                if (isFinite(video.duration) && video.duration > 0) {
                    video.currentTime = video.duration;
                }

                // Super-accelerate ad playback rate
                video.playbackRate = 16.0;

                // Click all variations of skip button immediately
                const skipBtns = document.querySelectorAll(
                    '.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, .ytp-ad-skip-button-text, .ytp-ad-overlay-close-button'
                );
                skipBtns.forEach(btn => {
                    try { btn.click(); } catch (e) {}
                });
            } else {
                // When ad finishes and real video resumes
                if (lastMutedAd) {
                    video.muted = false;
                    lastMutedAd = false;
                }
                if (video.playbackRate > 2.0) {
                    video.playbackRate = 1.0;
                }
            }
        } catch(e) {}
    }

    // High frequency interval (100ms) for instantaneous backup skip
    setInterval(instantSkipAds, 100);

    // 5. Floating Luxury Sanctuary Dock (Top window only)
    if (window.self === window.top) {
        function setupSanctuaryDock() {
            if (document.getElementById('ps-sanctuary-dock')) return;
            const target = document.body || document.documentElement;
            if (!target) return;

            // Clear any old top-dock legacy position that collided with YouTube masthead
            try {
                const legacy = localStorage.getItem('ps_dock_pos');
                if (legacy && (legacy.includes('9px') || legacy.includes('145px') || legacy.includes('180px'))) {
                    localStorage.removeItem('ps_dock_pos');
                }
            } catch(e) {}

            // Check if user previously dragged the dock to a custom position
            let savedPos = null;
            try {
                const s = localStorage.getItem('ps_dock_pos');
                if (s) savedPos = JSON.parse(s);
            } catch(e) {}

            const dock = document.createElement('div');
            dock.id = 'ps-sanctuary-dock';
            if (savedPos && savedPos.left && savedPos.top) {
                dock.style.cssText = 'position:fixed !important; top:' + savedPos.top + ' !important; left:' + savedPos.left + ' !important; height:38px !important; background:rgba(15, 15, 20, 0.94) !important; border:1px solid rgba(212,175,55,0.7) !important; border-radius:19px !important; padding:0 12px !important; display:flex !important; align-items:center !important; gap:10px !important; z-index:2147483647 !important; box-shadow:0 6px 24px rgba(0,0,0,0.85) !important; backdrop-filter:blur(12px) !important; box-sizing:border-box !important; user-select:none !important; font-family:"Outfit", system-ui, sans-serif !important;';
            } else {
                const initialBottom = (savedPos && savedPos.bottom) || '24px';
                const initialRight = (savedPos && savedPos.right) || '28px';
                dock.style.cssText = 'position:fixed !important; bottom:' + initialBottom + ' !important; right:' + initialRight + ' !important; height:38px !important; background:rgba(15, 15, 20, 0.94) !important; border:1px solid rgba(212,175,55,0.7) !important; border-radius:19px !important; padding:0 12px !important; display:flex !important; align-items:center !important; gap:10px !important; z-index:2147483647 !important; box-shadow:0 6px 24px rgba(0,0,0,0.85) !important; backdrop-filter:blur(12px) !important; box-sizing:border-box !important; user-select:none !important; font-family:"Outfit", system-ui, sans-serif !important;';
            }

            const badge = document.createElement('span');
            badge.textContent = "✦ SANCTUARY";
            badge.title = "Click & drag to move dock anywhere";
            badge.style.cssText = 'color:#D4AF37 !important; font-weight:800 !important; font-size:11px !important; letter-spacing:1.5px !important; margin-right:4px !important; cursor:move !important;';

            // Dragging functionality
            let isDragging = false;
            let dragOffsetX = 0, dragOffsetY = 0;

            badge.addEventListener('mousedown', function(e) {
                isDragging = true;
                const rect = dock.getBoundingClientRect();
                dragOffsetX = e.clientX - rect.left;
                dragOffsetY = e.clientY - rect.top;
                dock.style.transition = 'none';
                dock.style.bottom = 'auto';
                dock.style.right = 'auto';
                e.preventDefault();
            });

            document.addEventListener('mousemove', function(e) {
                if (!isDragging) return;
                const newLeft = Math.max(8, Math.min(window.innerWidth - dock.offsetWidth - 8, e.clientX - dragOffsetX));
                const newTop = Math.max(8, Math.min(window.innerHeight - dock.offsetHeight - 8, e.clientY - dragOffsetY));
                dock.style.left = newLeft + 'px';
                dock.style.top = newTop + 'px';
            });

            document.addEventListener('mouseup', function() {
                if (isDragging) {
                    isDragging = false;
                    dock.style.transition = '';
                    try {
                        localStorage.setItem('ps_dock_pos', JSON.stringify({
                            left: dock.style.left,
                            top: dock.style.top
                        }));
                    } catch(e) {}
                }
            });

            const backBtn = document.createElement('button');
            backBtn.textContent = '←';
            backBtn.title = 'Back';
            backBtn.style.cssText = 'background:rgba(255,255,255,0.12) !important; color:#e0e0e0 !important; border:none !important; width:26px !important; height:26px !important; border-radius:50% !important; font-size:13px !important; font-weight:700 !important; cursor:pointer !important; display:flex !important; align-items:center !important; justify-content:center !important; transition:0.2s;';
            backBtn.onmouseover = function() { backBtn.style.background = 'rgba(255,255,255,0.25)'; };
            backBtn.onmouseout = function() { backBtn.style.background = 'rgba(255,255,255,0.12)'; };
            backBtn.onclick = function() { window.history.back(); };

            const fsBtn = document.createElement('button');
            fsBtn.textContent = '⛶';
            fsBtn.title = 'Fullscreen (F11)';
            fsBtn.style.cssText = 'background:rgba(255,255,255,0.12) !important; color:#e0e0e0 !important; border:none !important; width:26px !important; height:26px !important; border-radius:50% !important; font-size:13px !important; font-weight:700 !important; cursor:pointer !important; display:flex !important; align-items:center !important; justify-content:center !important; transition:0.2s;';
            fsBtn.onmouseover = function() { fsBtn.style.background = 'rgba(255,255,255,0.25)'; };
            fsBtn.onmouseout = function() { fsBtn.style.background = 'rgba(255,255,255,0.12)'; };
            fsBtn.onclick = function() {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) {
                    window.pywebview.api.toggle_fullscreen();
                } else {
                    fetch('http://127.0.0.1:7890/api/app/fullscreen', { method: 'POST' }).catch(function(){});
                }
            };

            const returnBtn = document.createElement('button');
            returnBtn.textContent = '🎬 2 Broke Girls';
            returnBtn.title = 'Switch to 2 Broke Girls Sanctuary';
            returnBtn.style.cssText = 'background:linear-gradient(135deg, #E50914, #B20710) !important; color:#fff !important; border:none !important; padding:4px 12px !important; border-radius:14px !important; font-size:12px !important; font-weight:700 !important; cursor:pointer !important; box-shadow:0 2px 10px rgba(229,9,20,0.5) !important; transition:0.2s;';
            returnBtn.onmouseover = function() { returnBtn.style.transform = 'scale(1.05)'; };
            returnBtn.onmouseout = function() { returnBtn.style.transform = 'scale(1.0)'; };
            returnBtn.onclick = function() {
                window.location.href = 'http://127.0.0.1:7890';
            };

            dock.appendChild(badge);
            dock.appendChild(backBtn);
            dock.appendChild(fsBtn);
            dock.appendChild(returnBtn);

            target.appendChild(dock);
        }

        document.addEventListener('fullscreenchange', function() {
            const isFs = Boolean(document.fullscreenElement);
            const dock = document.getElementById('ps-sanctuary-dock');
            if (dock) dock.style.display = isFs ? 'none' : 'flex';
        });

        setInterval(setupSanctuaryDock, 1000);
        if (document.body) setupSanctuaryDock();
        else document.addEventListener('DOMContentLoaded', setupSanctuaryDock);
    }
})();
"""

def launch_ui(url: str):
    icon_path = PROJECT_DIR / "static" / "assets" / "icon.ico"
    holder = {}
    api = AppApi(holder)

    try:
        import webview
        from server import set_main_window

        # Prevent WebView2 from intercepting links to spawn external background processes
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False

        print("[UI] Creating native PlayerSlayer's Sanctuary window...")
        window = webview.create_window(
            title="PlayerSlayer's Sanctuary",
            url=url,
            js_api=api,
            width=1340,
            height=860,
            min_size=(960, 640),
            background_color="#141414"
        )
        holder["window"] = window
        set_main_window(window)

        def on_page_loaded(w=None):
            win = holder.get("window")
            if not win:
                return
            try:
                curr_url = win.get_current_url()
                print(f"[UI] In-app window loaded: {curr_url}")
                if curr_url and ("youtube.com" in curr_url or "googlevideo.com" in curr_url):
                    print("[UI] YouTube loaded, evaluating AdBlock scriptlet...")
                    win.evaluate_js(YOUTUBE_ADBLOCK_SCRIPTLET)
            except Exception as e:
                print(f"[UI ERROR] on_page_loaded error: {e}")

        window.events.loaded += on_page_loaded

        def on_shown():
            try:
                form = getattr(window, "native", None)
                if not form:
                    return
                wv = getattr(form, "webview", None)
                if not wv:
                    return

                def _setup_webview_features(core):
                    try:
                        core.Settings.AreBrowserAcceleratorKeysEnabled = True
                        core.AddScriptToExecuteOnDocumentCreatedAsync(YOUTUBE_ADBLOCK_SCRIPTLET)
                        print("[UI] Successfully attached Brave Shields scriptlet for document-creation!")
                    except Exception as ex:
                        print(f"[UI ERROR] _attach_script failed: {ex}")

                    try:
                        def _on_fs_changed(sender, args):
                            try:
                                is_elem_fs = bool(sender.ContainsFullScreenElement)
                                is_win_fs = bool(getattr(form, "is_fullscreen", False))
                                print(f"[UI] ContainsFullScreenElementChanged: elem={is_elem_fs}, win={is_win_fs}")
                                if is_elem_fs and not is_win_fs:
                                    form.toggle_fullscreen()
                                elif not is_elem_fs and is_win_fs:
                                    form.toggle_fullscreen()
                            except Exception as fse:
                                print(f"[UI ERROR] _on_fs_changed error: {fse}")

                        core.ContainsFullScreenElementChanged += _on_fs_changed
                        print("[UI] Successfully hooked ContainsFullScreenElementChanged!")
                    except Exception as ex:
                        print(f"[UI ERROR] Hook ContainsFullScreenElementChanged failed: {ex}")

                def _on_init_completed(sender, args):
                    if args.IsSuccess:
                        _setup_webview_features(sender.CoreWebView2)

                if wv.CoreWebView2:
                    _setup_webview_features(wv.CoreWebView2)
                else:
                    wv.CoreWebView2InitializationCompleted += _on_init_completed
            except Exception as e:
                print(f"[UI ERROR] on_shown setup failed: {e}")

        window.events.shown += on_shown

        print(f"[UI] Starting webview GUI loop with persistent profile at: {PROFILE_DIR}...")
        try:
            webview.start(
                debug=False,
                icon=str(icon_path) if icon_path.exists() else None,
                private_mode=False,
                storage_path=str(PROFILE_DIR)
            )
            return
        except Exception as start_err:
            print(f"[UI ERROR] webview.start failed with profile: {start_err}. Retrying fresh profile...")
            cleanup_profile_locks()
            webview.start(
                debug=False,
                icon=str(icon_path) if icon_path.exists() else None,
                private_mode=False
            )
            return
    except Exception as e:
        print(f"[UI FATAL] Desktop webview failed: {e}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Error initializing PlayerSlayer's Sanctuary window:\n\n{e}\n\nPlease relaunch the application.",
                "PlayerSlayer's Sanctuary",
                0x10
            )
        except Exception:
            pass

def cleanup_port(port: int):
    try:
        import subprocess
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True, stderr=subprocess.DEVNULL)
        pids = set()
        for line in output.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts:
                pids.add(parts[-1])
        current_pid = str(os.getpid())
        for pid in pids:
            if pid and pid != current_pid and pid != "0":
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception:
        pass

def cleanup_profile_locks():
    eb_dir = PROFILE_DIR / "EBWebView"
    if eb_dir.exists():
        for lock_file in eb_dir.rglob("LOCK"):
            try:
                lock_file.unlink()
            except Exception:
                pass

def main():
    if not acquire_single_instance_mutex():
        print("[STARTUP] Another instance is already active. Exiting.")
        sys.exit(0)

    port = 7890
    print("\n" + "=" * 55)
    print("  [STARTUP] Launching PlayerSlayer's Sanctuary...")
    print("=" * 55)

    cleanup_profile_locks()
    cleanup_port(port)

    if not is_port_in_use(port):
        start_server_subprocess(port)

        print(f"[STARTUP] Waiting for server on port {port}...")
        for i in range(40):
            if is_port_in_use(port):
                print(f"[STARTUP] Server is live after {(i+1)*0.25:.2f}s!")
                break
            if SERVER_PROCESS and SERVER_PROCESS.poll() is not None:
                print(f"[STARTUP ERROR] Server process died with code {SERVER_PROCESS.poll()}")
                break
            time.sleep(0.25)

    target_url = f"http://127.0.0.1:{port}"
    print(f"[STARTUP] Default home screen (2 Broke Girls Sanctuary): {target_url}")
    try:
        launch_ui(target_url)
    finally:
        cleanup_server()
        release_single_instance_mutex()

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        import traceback
        err_details = traceback.format_exc()
        print(f"[FATAL ERROR]\n{err_details}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Error starting PlayerSlayer's Sanctuary:\n\n{ex}\n\nCheck app.log for details.",
                "PlayerSlayer's Sanctuary - Error",
                0x10
            )
        except Exception:
            pass
