/**
 * SPHEREx Planet X Challenge - Master Application Controller
 * Handles user interactions, 7 Unified Viewing Modes, URL state routing, API calls, and playback loops.
 * Compliant with UI/UX Pro Max guidelines and Mission Control accessibility standards.
 */

class SpherexApp {
  constructor() {
    // 1. Initialize State with URL Router Parameters (Section 3)
    this.state = this.parseUrlState();

    this.pipelineData = null;
    this.playbackTimer = null;

    // Viewers & Charts
    this.viewer = new FlipbookViewer('flipbookCanvas');
    this.spectrumChart = new SpectrumChart('spectrumChartContainer');
    this.auditChart = new AuditChart('auditChartContainer');

    this.syncUIWithState();
    this.initEventListeners();
    this.initKeyboardShortcuts();
    this.loadPipelineData();
    this.loadObservationsData();
  }

  parseUrlState() {
    const params = new URLSearchParams(window.location.search);
    return {
      target: params.get('q') || "Barnard's Star",
      detector: (params.get('det') || "D1").toUpperCase(),
      mode: params.get('mode') || "visit_blink",           // 7 Master Modes + shift_stack
      frameMode: params.get('frame_mode') || "inertial",   // 'inertial' or 'comoving'
      colorMode: params.get('color_mode') || "spectral",   // 'spectral', 'multiband', 'grayscale'
      sourceMode: params.get('source') || "auto",          // 'auto', 'real', 'simulated'
      fovMode: params.get('fov_mode') || "wide",           // 'wide' (30' zoomed out) or 'core' (6.5' zoomed in)
      blinkMode: params.get('blink_mode') || "spectral",   // 'spectral' (D1-D6) or 'temporal' (2014-2024 time series)
      fps: parseInt(params.get('fps') || "4", 10),
      isPlaying: true,
      currentFrameIdx: 0,
      totalFrames: 0
    };
  }

  updateUrlState() {
    const params = new URLSearchParams();
    params.set('q', this.state.target);
    params.set('det', this.state.detector);
    params.set('mode', this.state.mode);
    params.set('color_mode', this.state.colorMode);
    params.set('frame_mode', this.state.frameMode);
    params.set('source', this.state.sourceMode);
    params.set('fov_mode', this.state.fovMode);
    params.set('blink_mode', this.state.blinkMode);
    params.set('fps', this.state.fps.toString());

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  }

  syncUIWithState() {
    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(b => {
      if (b.dataset.target === this.state.target) b.classList.add('active');
      else b.classList.remove('active');
    });

    // 7 Master Modes + Shift-Stack
    document.querySelectorAll('.mode-card').forEach(b => {
      if (b.dataset.mode === this.state.mode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // Detector buttons and text
    this.setDetector(this.state.detector);

    // Frame Mode
    document.querySelectorAll('.frame-mode-btn').forEach(b => {
      if (b.dataset.frame === this.state.frameMode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // Color Mode
    document.querySelectorAll('.color-mode-btn').forEach(b => {
      if (b.dataset.color === this.state.colorMode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // FOV Mode (Wide 30' vs Core 6.5')
    document.querySelectorAll('[data-fov]').forEach(b => {
      if (b.dataset.fov === this.state.fovMode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // Data Source Mode (Real vs Simulated)
    document.querySelectorAll('[data-source]').forEach(b => {
      if (b.dataset.source === this.state.sourceMode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // Blink Mode (Spectral vs Temporal)
    document.querySelectorAll('[data-blink]').forEach(b => {
      if (b.dataset.blink === this.state.blinkMode) b.classList.add('active');
      else b.classList.remove('active');
    });

    // FPS
    const slider = document.getElementById('fpsSlider');
    const valText = document.getElementById('fpsValue');
    if (slider) slider.value = this.state.fps;
    if (valText) valText.textContent = `${this.state.fps} FPS`;
  }

  setMode(modeKey) {
    const card = document.querySelector(`.mode-card[data-mode="${modeKey}"]`);
    if (card) {
      card.click();
    }
  }

  setDetector(det) {
    this.state.detector = det;
    document.querySelectorAll('.det-btn').forEach(b => {
      if (b.dataset.det === det) b.classList.add('active');
      else b.classList.remove('active');
    });

    const detSpecs = {
      'D1': 'D1 • 0.744 - 1.116 µm (R=39)',
      'D2': 'D2 • 1.099 - 1.651 µm (R=41)',
      'D3': 'D3 • 1.636 - 2.421 µm (R=41)',
      'D4': 'D4 • 2.423 - 3.822 µm (R=35)',
      'D5': 'D5 • 3.809 - 4.420 µm (R=112)',
      'D6': 'D6 • 4.412 - 5.002 µm (R=128)'
    };
    const info = detSpecs[det] || det;
    const bandEl = document.getElementById('activeDetBandInfo');
    if (bandEl) bandEl.textContent = info;
    const hudDet = document.getElementById('hudDetector');
    if (hudDet) hudDet.textContent = info;
  }

  initEventListeners() {
    // 1. Benchmark Presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.target = e.currentTarget.dataset.target;
        
        // Intelligent default detector for specific physical targets
        if (this.state.target.includes("Barnard")) this.setDetector("D1");
        else if (this.state.target.includes("Epsilon")) this.setDetector("D3");
        else if (this.state.target.includes("RW Aurigae")) this.setDetector("D2");
        else if (this.state.target.includes("R Draconis")) this.setDetector("D4");
        else this.setDetector("D6");

        this.updateUrlState();
        this.loadPipelineData();
        this.loadObservationsData();
      });
    });

    // 2. The 7 Unified Viewing Modes + Shift-Stack (Section 9.1)
    document.querySelectorAll('.mode-card').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.mode-card').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.mode = e.currentTarget.dataset.mode;
        
        // Mode-specific parameter overrides
        if (this.state.mode === "motion_tracked") {
          this.state.frameMode = "comoving";
        } else {
          this.state.frameMode = "inertial";
        }
        
        if (this.state.mode === "spectral_color") {
          this.state.colorMode = "multiband";
        } else {
          this.state.colorMode = "spectral";
        }

        this.syncUIWithState();
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 3. Detector Selector (D1..D6)
    document.querySelectorAll('.det-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        this.setDetector(e.currentTarget.dataset.det);
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 4. Granular Frame Mode (Idea 1)
    document.querySelectorAll('.frame-mode-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.frame-mode-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.frameMode = e.currentTarget.dataset.frame;
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 5. Granular Color Mode (Idea 2)
    document.querySelectorAll('.color-mode-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.color-mode-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.colorMode = e.currentTarget.dataset.color;
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 5b. FOV Mode (Wide 30' vs Core 6.5')
    document.querySelectorAll('[data-fov]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('[data-fov]').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.fovMode = e.currentTarget.dataset.fov;
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 5c. Data Source Mode (Real FITS vs Synthetic Benchmark)
    document.querySelectorAll('[data-source]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('[data-source]').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.sourceMode = e.currentTarget.dataset.source;
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 5d. Blink Comparator Mode (Spectral D1-D6 vs Temporal 2014-2024)
    document.querySelectorAll('[data-blink]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('[data-blink]').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.state.blinkMode = e.currentTarget.dataset.blink;
        this.updateUrlState();
        this.loadPipelineData();
      });
    });

    // 6. Overlay Toggles (Reticle, Compass, Stars, Trail, Wipe)
    this.setupOverlayToggle('toggleReticleBtn', 'showReticle');
    this.setupOverlayToggle('toggleCompassBtn', 'showCompass');
    this.setupOverlayToggle('toggleStarsBtn', 'showStars');
    this.setupOverlayToggle('toggleTrailBtn', 'showTrail');
    this.setupOverlayToggle('toggleWipeBtn', 'showWipe');

    // 7. Zoom Toolbar
    const zoomIn = document.getElementById('zoomInBtn');
    if (zoomIn) zoomIn.addEventListener('click', () => this.viewer.setZoom(this.viewer.zoomLevel * 1.25));
    const zoomOut = document.getElementById('zoomOutBtn');
    if (zoomOut) zoomOut.addEventListener('click', () => this.viewer.setZoom(this.viewer.zoomLevel / 1.25));
    const zoomReset = document.getElementById('zoomResetBtn');
    if (zoomReset) zoomReset.addEventListener('click', () => this.viewer.resetView());

    // 8. Playback Controls
    document.getElementById('playPauseBtn')?.addEventListener('click', () => {
      this.togglePlayback();
    });

    document.getElementById('prevFrameBtn')?.addEventListener('click', () => {
      this.stepFrame(-1);
    });

    document.getElementById('nextFrameBtn')?.addEventListener('click', () => {
      this.stepFrame(1);
    });

    const fpsSlider = document.getElementById('fpsSlider');
    if (fpsSlider) {
      fpsSlider.addEventListener('input', (e) => {
        this.state.fps = parseInt(e.target.value, 10);
        document.getElementById('fpsValue').textContent = `${this.state.fps} FPS`;
        this.updateUrlState();
        if (this.state.isPlaying) {
          this.stopPlayback();
          this.startPlayback();
        }
      });
    }

    // 9. Tab Navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const tabId = e.currentTarget.dataset.tab;
        const targetTab = document.getElementById(tabId);
        if (targetTab) targetTab.classList.add('active');
        // Trigger responsive redraw
        this.spectrumChart.resize();
        this.auditChart.resize();
      });
    });

    // 10. Export Actions
    document.getElementById('exportGifBtn')?.addEventListener('click', () => {
      this.exportGif();
    });

    document.getElementById('exportCsvBtn')?.addEventListener('click', () => {
      this.exportCsv();
    });

    document.getElementById('copyShareUrlBtn')?.addEventListener('click', () => {
      this.copyShareUrl();
    });

    // 11. Modal Trigger and Close
    const shortcutsBtn = document.getElementById('shortcutsBtn');
    const closeShortcutsBtn = document.getElementById('closeShortcutsBtn');
    const shortcutsModal = document.getElementById('shortcutsModal');
    
    if (shortcutsBtn && shortcutsModal) {
      shortcutsBtn.addEventListener('click', () => {
        shortcutsModal.classList.add('open');
      });
    }
    if (closeShortcutsBtn && shortcutsModal) {
      closeShortcutsBtn.addEventListener('click', () => {
        shortcutsModal.classList.remove('open');
      });
    }
    if (shortcutsModal) {
      shortcutsModal.addEventListener('click', (e) => {
        if (e.target === shortcutsModal) {
          shortcutsModal.classList.remove('open');
        }
      });
    }
  }

  initKeyboardShortcuts() {
    const shortcutsModal = document.getElementById('shortcutsModal');

    window.addEventListener('keydown', (e) => {
      // Ignore if user is typing in an input or select
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlayback();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        this.stepFrame(-1);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        this.stepFrame(1);
      } else if (e.key >= '1' && e.key <= '7') {
        const modeKeys = [
          'visit_blink',
          'longest_baseline',
          'difference_sequence',
          'motion_tracked',
          'spectral_color',
          'wavelength_matched',
          'within_visit_fast'
        ];
        const idx = parseInt(e.key, 10) - 1;
        if (modeKeys[idx]) {
          e.preventDefault();
          this.setMode(modeKeys[idx]);
        }
      } else if (e.key === '8') {
        e.preventDefault();
        this.setMode('shift_stack');
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        this.viewer.resetView();
      } else if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        this.viewer.setZoom(this.viewer.zoomLevel * 1.25);
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        this.viewer.setZoom(this.viewer.zoomLevel / 1.25);
      } else if (e.key === 't' || e.key === 'T') {
        e.preventDefault();
        document.getElementById('toggleReticleBtn')?.click();
      } else if (e.key === 'g' || e.key === 'G') {
        e.preventDefault();
        document.getElementById('toggleStarsBtn')?.click();
      } else if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        document.getElementById('toggleCompassBtn')?.click();
      } else if (e.key === '?') {
        e.preventDefault();
        if (shortcutsModal) {
          shortcutsModal.classList.toggle('open');
        }
      } else if (e.key === 'Escape') {
        if (shortcutsModal && shortcutsModal.classList.contains('open')) {
          shortcutsModal.classList.remove('open');
        }
      }
    });
  }

  setupOverlayToggle(btnId, propertyName) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('click', () => {
      this.viewer[propertyName] = !this.viewer[propertyName];
      if (this.viewer[propertyName]) btn.classList.add('active');
      else btn.classList.remove('active');
      this.viewer.render();
    });
  }

  updatePlayPauseIcon() {
    const btn = document.getElementById('playPauseBtn');
    if (!btn) return;
    if (this.state.isPlaying) {
      btn.innerHTML = `<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
      btn.title = "Pause Flipbook (Space)";
    } else {
      btn.innerHTML = `<svg viewBox="0 0 24 24"><polygon points="6 4 20 12 6 20 6 4"/></svg>`;
      btn.title = "Play Flipbook (Space)";
    }
  }

  async loadPipelineData() {
    this.stopPlayback();
    const statusEl = document.getElementById('systemStatusText');
    const message = document.getElementById('viewerMessage');
    if (message) {
      message.hidden = false;
      message.querySelector('strong').textContent = 'Loading observations';
      message.querySelector('span').textContent = 'Preparing the selected field and detector.';
    }
    if (statusEl) statusEl.textContent = 'Loading observations';

    // Standardized endpoint conforming to Section 9.2 with real FITS and FOV support
    const url = `/api/frames?q=${encodeURIComponent(this.state.target)}&det=${this.state.detector}&mode=${this.state.mode}&frame_mode=${this.state.frameMode}&color_mode=${this.state.colorMode}&source=${this.state.sourceMode}&fov_mode=${this.state.fovMode}&blink_mode=${this.state.blinkMode}`;
    
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Observation request failed (${resp.status})`);
      const data = await resp.json();
      if (!data.frames?.length) throw new Error('No frames returned');
      this.pipelineData = data;
      if (this.state.sourceMode === 'auto') {
        document.getElementById('sourceRealBtn').classList.toggle('active', data.is_real_data);
        document.getElementById('sourceSimBtn').classList.toggle('active', !data.is_real_data);
      }
      this.state.totalFrames = data.frames ? data.frames.length : 0;
      this.state.currentFrameIdx = 0;

      // Update Stale Epoch Warning Banner
      const banner = document.getElementById('staleEpochBanner');
      if (banner) {
        if (data.stale_epoch_warning) {
          banner.style.display = 'flex';
          document.getElementById('staleEpochText').textContent = data.stale_epoch_warning;
        } else {
          banner.style.display = 'none';
        }
      }

      // Update Astrometric Validation HUD
      this.updateAstrometryHUD(data.astrometric_validation, data.target);

      // Update Planet Nine / TNO Detectability & Calibration HUD
      if (data.planet_nine_detectability) {
        const p9 = data.planet_nine_detectability;
        const elSingle = document.getElementById('p9SingleVisitDepth');
        if (elSingle) elSingle.textContent = `${p9.single_visit_limit_ab_mag.toFixed(2)} AB`;
        const elCoadd = document.getElementById('p9CoaddDepth');
        if (elCoadd) elCoadd.textContent = `${p9.coadded_stack_limit_ab_mag.toFixed(2)} AB`;
        const elZodi = document.getElementById('p9ZodiStatus');
        if (elZodi) elZodi.textContent = p9.zodiacal_light_subtraction ? "Active (Plane Sub)" : "Standard";
        const elFlags = document.getElementById('p9FlagsStatus');
        if (elFlags) elFlags.textContent = p9.cosmic_ray_filter ? "Masked (FLAGS 0x01)" : "Standard";
      }

      // Update Still-Star Flicker Audit
      this.updateFlickerAudit(data.flicker_audit);

      // Update 102-Channel Spectrophotometry
      this.spectrumChart.setData(data.spectrophotometry);

      // Rebuild dynamic visit scrubber buttons
      this.rebuildVisitScrubber();

      // Render first frame & start loop
      this.renderFrame(0);
      if (message) message.hidden = true;
      if (this.state.isPlaying) {
        this.startPlayback();
      }

      if (statusEl) {
        if (data.is_real_data) {
          statusEl.textContent = 'Archive FITS';
        } else {
          statusEl.textContent = 'Simulation';
        }
      }
    } catch (err) {
      console.error('Failed to load pipeline data:', err);
      if (statusEl) statusEl.textContent = 'Observations unavailable';
      if (message) {
        message.hidden = false;
        message.querySelector('strong').textContent = 'Could not load observations';
        message.querySelector('span').textContent = 'Select another target or try the simulation source.';
      }
    }
  }

  async loadObservationsData() {
    try {
      const resp = await fetch(`/api/observations?q=${encodeURIComponent(this.state.target)}`);
      const obs = await resp.json();
      
      const countEl = document.getElementById('obsVisitsCount');
      if (countEl) countEl.textContent = `${obs.n_visits_found} Visits`;

      const tbody = document.getElementById('obsTableBody');
      if (tbody && obs.visits) {
        tbody.innerHTML = '';
        for (const v of obs.visits) {
          const row = document.createElement('tr');
          row.style.borderBottom = '1px solid var(--border-subtle)';
          row.innerHTML = `
            <td style="padding: 9px 12px; font-weight: 700; color: var(--text-pure);">${v.visit_id}</td>
            <td style="padding: 9px 12px; color: var(--text-secondary);">${v.survey_pass}</td>
            <td style="padding: 9px 12px; color: var(--text-pure);">${v.date_utc.split(' ')[0]}</td>
            <td style="padding: 9px 12px; color: var(--text-muted);">${v.mjd_mid.toFixed(1)}</td>
            <td style="padding: 9px 12px; color: var(--text-secondary);">${v.n_exposures} exps</td>
            <td style="padding: 9px 12px;"><span style="background: var(--panther-purple-subtle); color: var(--panther-purple-bright); border: 1px solid var(--panther-purple-border); padding: 2px 7px; border-radius: 3px; font-weight: 600;">${v.release}</span></td>
          `;
          tbody.appendChild(row);
        }
      }
    } catch (err) {
      console.warn('Failed to load observations data:', err);
    }
  }

  rebuildVisitScrubber() {
    const container = document.getElementById('visitScrubberContainer');
    if (!container || !this.pipelineData || !this.pipelineData.frames) return;
    
    container.innerHTML = '';
    this.pipelineData.frames.forEach((f, idx) => {
      const btn = document.createElement('button');
      btn.className = 'visit-step-btn' + (idx === 0 ? ' active' : '');
      btn.textContent = f.visit_id;
      btn.title = `Jump to ${f.visit_id} (${f.date_utc})`;
      btn.addEventListener('click', () => {
        this.stopPlayback();
        this.renderFrame(idx);
      });
      container.appendChild(btn);
    });
  }

  renderFrame(idx) {
    if (!this.pipelineData || !this.pipelineData.frames || this.pipelineData.frames.length === 0) return;
    this.state.currentFrameIdx = idx % this.pipelineData.frames.length;
    const f = this.pipelineData.frames[this.state.currentFrameIdx];

    // Determine target reticle position based on frame dimensions and mode
    const w = f.rgb_pixels ? f.rgb_pixels[0].length : 64;
    const h = f.rgb_pixels ? f.rgb_pixels.length : 64;
    let targetPos = f.target_pos_px;
    if (this.state.frameMode === "comoving" || !targetPos) {
      targetPos = [w / 2.0, h / 2.0]; // Target locked at center!
    }

    this.viewer.setFrameData(
      f,
      this.pipelineData.frames,
      this.pipelineData.field_stars,
      targetPos,
      this.pipelineData.target.common_name
    );

    // Update HUD overlay elements
    const hudV = document.getElementById('hudVisit');
    if (hudV) hudV.textContent = f.visit_id || f.label || 'Frame';
    const hudD = document.getElementById('hudDate');
    if (hudD) hudD.textContent = f.date_utc ? f.date_utc.split(' ')[0] : (f.epoch_year ? f.epoch_year.toString() : '2025');
    const hudM = document.getElementById('hudMjd');
    if (hudM) hudM.textContent = f.mjd ? `MJD ${f.mjd.toFixed(1)}` : 'MJD 60810.0';

    const hudSrc = document.getElementById('hudSourceBadge');
    if (hudSrc) {
      if (f.is_real_data) {
        hudSrc.textContent = "REAL FITS";
        hudSrc.className = "hud-pill hud-pill-source";
      } else {
        hudSrc.textContent = "SIMULATED";
        hudSrc.className = "hud-pill";
      }
    }

    const hudFov = document.getElementById('hudFovBadge');
    if (hudFov) {
      const fovVal = f.fov_arcmin || (this.state.fovMode === 'wide' ? 30.1 : 6.5);
      hudFov.textContent = `${fovVal.toFixed(1)}' ${this.state.fovMode === 'wide' ? 'WIDE FIELD' : 'CORE'}`;
    }

    const hudFile = document.getElementById('hudFile');
    if (hudFile) {
      hudFile.textContent = f.source_file || 'Synthetic Benchmark';
      hudFile.title = f.source_file || 'Synthetic Benchmark';
    }

    const hudDet = document.getElementById('hudDetector');
    if (hudDet) {
      hudDet.textContent = `${f.band || this.state.detector} • ${(f.fov_arcmin || 30.0).toFixed(1)}' FOV`;
    }

    // Update scrubber buttons
    document.querySelectorAll('.visit-step-btn').forEach((b, i) => {
      if (i === this.state.currentFrameIdx) b.classList.add('active');
      else b.classList.remove('active');
    });
  }

  startPlayback() {
    this.stopPlayback();
    this.state.isPlaying = true;
    this.updatePlayPauseIcon();
    const interval = Math.max(80, 1000 / this.state.fps);
    this.playbackTimer = setInterval(() => {
      this.stepFrame(1);
    }, interval);
  }

  stopPlayback() {
    this.state.isPlaying = false;
    this.updatePlayPauseIcon();
    if (this.playbackTimer) {
      clearInterval(this.playbackTimer);
      this.playbackTimer = null;
    }
  }

  togglePlayback() {
    if (this.state.isPlaying) this.stopPlayback();
    else this.startPlayback();
  }

  stepFrame(delta) {
    if (!this.pipelineData || !this.pipelineData.frames) return;
    const n = this.pipelineData.frames.length;
    let nextIdx = (this.state.currentFrameIdx + delta) % n;
    if (nextIdx < 0) nextIdx += n;
    this.renderFrame(nextIdx);
  }

  updateAstrometryHUD(astro, target) {
    if (!astro) return;
    const elTarget = document.getElementById('astTargetName');
    if (elTarget) elTarget.textContent = target.common_name;
    const elSpec = document.getElementById('astSpectralType');
    if (elSpec) elSpec.textContent = `${target.spectral_type} (${target.teff_k} K)`;
    const elEp = document.getElementById('astCatalogEpoch');
    if (elEp) elEp.textContent = `J${target.discovery_epoch.toFixed(1)}`;
    const elCoord = document.getElementById('astCatalogCoords');
    if (elCoord) elCoord.textContent = `RA ${target.ra_deg.toFixed(4)}°, Dec ${target.dec_deg.toFixed(4)}°`;
    
    const elPm = document.getElementById('astFittedPm');
    if (elPm) elPm.textContent = astro.fitted_pm
      ? `${astro.fitted_pm.fitted_total_pm_arcsec_yr}"/yr (${astro.fitted_pm.fitted_total_pm_mas_yr} mas/yr)`
      : `${astro.proper_motion_total_arcsec_yr}"/yr (catalog)`;
    const elRes = document.getElementById('astGaiaResidual');
    if (elRes) elRes.textContent = astro.residuals
      ? `${astro.residuals.total_residual_mas_yr} mas/yr`
      : 'Not measured';
    const elVer = document.getElementById('astVerdict');
    if (elVer) elVer.textContent = astro.validation_verdict || 'Archive images loaded. Independent astrometric fitting is not available for this source.';
  }

  updateFlickerAudit(audit) {
    if (!audit) return;
    const pct = (v) => (v == null ? 'Not run' : `${v}%`);
    const rawF = document.getElementById('rawFlickerVal');
    if (rawF) rawF.textContent = pct(audit.mean_raw_flicker_pct);
    const balF = document.getElementById('balancedFlickerVal');
    if (balF) balF.textContent = pct(audit.mean_balanced_flicker_pct);
    const supF = document.getElementById('flickerSuppressionVal');
    if (supF) supF.textContent = pct(audit.overall_flicker_suppression_pct);
    const nullF = document.getElementById('nullTestVal');
    if (nullF) nullF.textContent = audit.null_test_chi2_nu == null
      ? 'Not provided'
      : `Chi2 = ${audit.null_test_chi2_nu}`;

    this.auditChart.setData(audit);
  }

  exportGif() {
    const url = `/api/export/gif?target=${encodeURIComponent(this.state.target)}&detector=${this.state.detector}&mode=${this.state.mode}&fps=${this.state.fps}&source=${this.state.sourceMode}&fov_mode=${this.state.fovMode}&blink_mode=${this.state.blinkMode}`;
    window.open(url, '_blank');
  }

  exportCsv() {
    if (!this.pipelineData || !this.pipelineData.spectrophotometry) return;
    const pts = this.pipelineData.spectrophotometry.spectrum;
    let csv = "channel_id,detector,channel_in_detector,wavelength_um,bandwidth_um,flux_mjy,flux_err_mjy,snr,molecular_feature\n";
    for (const p of pts) {
      csv += `${p.channel_id},${p.detector},${p.channel_in_detector},${p.wavelength_um},${p.bandwidth_um},${p.flux_mjy},${p.flux_err_mjy},${p.snr},${p.molecular_feature || ""}\n`;
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `spherex_${this.state.target.replace(' ', '_').toLowerCase()}_102channel_sed.csv`;
    link.click();
  }

  copyShareUrl() {
    this.updateUrlState();
    navigator.clipboard.writeText(window.location.href).then(() => {
      const toast = document.getElementById('toastNotification');
      if (toast) {
        toast.style.display = 'block';
        setTimeout(() => {
          toast.style.display = 'none';
        }, 2500);
      }
    }).catch(err => {
      console.warn('Clipboard write failed:', err);
    });
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.spherexApp = new SpherexApp();
});
