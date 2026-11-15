/**
 * SPHEREx Planet X Challenge - Canvas Double-Buffered Flipbook Viewer
 * High-performance astronomical canvas renderer with crisp sub-pixel scaling,
 * interactive pan & zoom, WCS overlays, reticle, Gaia DR3 markers, and live coordinate inspector.
 */

class FlipbookViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.currentFrame = null;
    this.allFrames = [];
    this.fieldStars = [];
    
    // Overlay display toggles
    this.showReticle = true;
    this.showMask = false;
    this.showCompass = true;
    this.showStars = false;
    this.showTrail = true;
    this.showWipe = false;
    this.wipeRatio = 0.5;
    this.isDraggingWipe = false;
    
    this.reticlePos = { x: 31.5, y: 31.5 };
    this.targetName = "TARGET";

    // Pan & Zoom state
    this.zoomLevel = 1.0;
    this.panOffset = { x: 0, y: 0 };
    this.isDragging = false;
    this.dragStart = { x: 0, y: 0 };

    this.coordReadoutEl = document.getElementById('canvasCoordReadout');

    this.initInteractions();
  }

  initInteractions() {
    const canvas = this.canvas;
    // Client (CSS) pixels -> canvas pixels; the canvas is scaled down on narrow screens.
    const toCanvas = (e) => {
      const rect = canvas.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * (canvas.width / rect.width),
        y: (e.clientY - rect.top) * (canvas.height / rect.height)
      };
    };
    this.onWipeChange = null;

    // Mouse wheel zoom
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.setZoom(this.zoomLevel * (e.deltaY < 0 ? 1.15 : 0.87));
    }, { passive: false });

    // Dragging on the image must not start a text selection on the page.
    canvas.addEventListener('mousedown', (e) => e.preventDefault());
    document.addEventListener('selectstart', (e) => { if (this.isDragging || this.isDraggingWipe) e.preventDefault(); });

    // Pointer events cover mouse, touch and pen.
    canvas.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      const pt = toCanvas(e);
      const wipeHitPx = e.pointerType === 'mouse' ? 22 : 40;
      if (this.wipeActive() && Math.abs(pt.x - canvas.width * this.wipeRatio) < wipeHitPx) {
        this.isDraggingWipe = true;
        canvas.style.cursor = 'ew-resize';
      } else {
        this.isDragging = true;
        this.dragStart = { x: pt.x - this.panOffset.x, y: pt.y - this.panOffset.y };
        canvas.style.cursor = 'grabbing';
      }
      this.activePointer = e.pointerId;
      try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* synthetic events */ }
      e.preventDefault();
    });

    const onMove = (e) => {
      if (this.activePointer !== undefined && e.pointerId !== this.activePointer) return;
      if (this.isDraggingWipe) {
        this.setWipeRatio(toCanvas(e).x / canvas.width);
      } else if (this.isDragging) {
        const pt = toCanvas(e);
        this.panOffset = { x: pt.x - this.dragStart.x, y: pt.y - this.dragStart.y };
        this.render();
      }
    };
    const onUp = (e) => {
      if (this.activePointer !== undefined && e.pointerId !== this.activePointer) return;
      this.isDraggingWipe = false;
      this.isDragging = false;
      this.activePointer = undefined;
      canvas.style.cursor = 'crosshair';
    };
    canvas.addEventListener('pointermove', onMove);
    window.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerup', onUp);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);

    // Hover coordinate inspector
    canvas.addEventListener('pointermove', (e) => {
      if (!this.currentFrame || !this.coordReadoutEl || this.isDraggingWipe) return;
      const pt = toCanvas(e);
      const cWidth = canvas.width, cHeight = canvas.height;
      const centerX = cWidth / 2 + this.panOffset.x;
      const centerY = cHeight / 2 + this.panOffset.y;
      const normX = (pt.x - centerX) / (cWidth * this.zoomLevel) + 0.5;
      const normY = (pt.y - centerY) / (cHeight * this.zoomLevel) + 0.5;
      const rows = this.currentFrame.rgb_pixels;
      const w = rows ? rows[0].length : 64;
      const h = rows ? rows.length : 64;
      const pxX = Math.floor(normX * w);
      const pxY = Math.floor(normY * h);
      const pixelScale = this.currentFrame.pixel_scale_arcsec || 6.15;
      const fovArcmin = this.currentFrame.fov_arcmin || ((w * pixelScale) / 60.0);
      if (pxX >= 0 && pxX < w && pxY >= 0 && pxY < h) {
        const dx = ((w - 1) / 2 - pxX) * pixelScale;
        const dy = ((h - 1) / 2 - pxY) * pixelScale;
        this.coordReadoutEl.textContent = `PX [${pxX}, ${pxY}] | dRA*cosDec ${dx > 0 ? '+' : ''}${dx.toFixed(1)}" | dDec ${dy > 0 ? '+' : ''}${dy.toFixed(1)}" | ${fovArcmin.toFixed(1)}' FOV`;
      } else {
        this.coordReadoutEl.textContent = `FOV ${fovArcmin.toFixed(1)}' | ${pixelScale.toFixed(2)}"/px`;
      }
    });
  }

  wipeActive() {
    return this.showWipe && this.allFrames && this.allFrames.length > 1;
  }

  setWipeRatio(ratio) {
    this.wipeRatio = Math.max(0.05, Math.min(0.95, ratio));
    this.render();
    if (this.onWipeChange) this.onWipeChange(this.wipeRatio);
  }

  setZoom(newZoom) {
    this.zoomLevel = Math.max(0.75, Math.min(5.0, newZoom));
    this.render();
  }

  resetView() {
    this.zoomLevel = 1.0;
    this.panOffset = { x: 0, y: 0 };
    this.render();
  }

  setFrameData(frameData, allFrames, fieldStars, targetPos, targetName) {
    this.currentFrame = frameData;
    this.allFrames = allFrames || [];
    this.fieldStars = fieldStars || [];
    if (targetPos) {
      this.reticlePos = { x: targetPos[0], y: targetPos[1] };
    }
    this.targetName = targetName || "TARGET";
    this.render();
  }

  _createOffscreenFromPixels(rgb) {
    if (!rgb || !rgb.length) return null;
    const h = rgb.length;
    const w = rgb[0].length;
    const off = document.createElement('canvas');
    off.width = w;
    off.height = h;
    const offCtx = off.getContext('2d');
    const imgData = offCtx.createImageData(w, h);
    let pIdx = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const pixel = rgb[y][x];
        imgData.data[pIdx]     = pixel[0]; // R
        imgData.data[pIdx + 1] = pixel[1]; // G
        imgData.data[pIdx + 2] = pixel[2]; // B
        imgData.data[pIdx + 3] = 255;      // Alpha
        pIdx += 4;
      }
    }
    offCtx.putImageData(imgData, 0, 0);
    return { canvas: off, w, h };
  }

  render() {
    if (!this.currentFrame || !this.currentFrame.rgb_pixels) return;

    const currentOff = this._createOffscreenFromPixels(this.currentFrame.rgb_pixels);
    if (!currentOff) return;

    const w = currentOff.w;
    const h = currentOff.h;
    const cWidth = this.canvas.width;
    const cHeight = this.canvas.height;

    this.ctx.imageSmoothingEnabled = false;
    this.ctx.clearRect(0, 0, cWidth, cHeight);

    if (this.showMask && this.currentFrame.mask) {
      const context = currentOff.canvas.getContext('2d');
      context.fillStyle = '#ff39ab';
      this.currentFrame.mask.forEach((row,y) => row.forEach((v,x) => { if(v) context.fillRect(x,y,1,1); }));
    }
    const applyView = () => {
      this.ctx.translate(cWidth / 2 + this.panOffset.x, cHeight / 2 + this.panOffset.y);
      this.ctx.scale(this.zoomLevel, this.zoomLevel);
      this.ctx.translate(-cWidth / 2, -cHeight / 2);
    };
    const wipeX = cWidth * this.wipeRatio;

    if (this.wipeActive()) {
      // Split comparison in screen space: first frame on the left, current frame on the right.
      const baseOff = this._createOffscreenFromPixels(this.allFrames[0].rgb_pixels) || currentOff;
      if (this.showMask && this.allFrames[0].mask) {
        const bctx = baseOff.canvas.getContext('2d');
        bctx.fillStyle = '#ff39ab';
        this.allFrames[0].mask.forEach((row, y) => row.forEach((v, x) => { if (v) bctx.fillRect(x, y, 1, 1); }));
      }
      for (const [off, x0, x1] of [[baseOff, 0, wipeX], [currentOff, wipeX, cWidth]]) {
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.rect(x0, 0, x1 - x0, cHeight);
        this.ctx.clip();
        applyView();
        this.ctx.drawImage(off.canvas, 0, 0, cWidth, cHeight);
        this.ctx.restore();
      }
    }

    // Zoom & pan transform for the image and overlays
    this.ctx.save();
    applyView();
    if (!this.wipeActive()) {
      this.ctx.drawImage(currentOff.canvas, 0, 0, cWidth, cHeight);
    }

    const scaleX = cWidth / w;
    const scaleY = cHeight / h;

    // 1. Draw Gaia DR3 Reference Field Stars (when enabled)
    if (this.showStars && this.fieldStars && this.fieldStars.length > 0) {
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)'; // Clean silver
      this.ctx.lineWidth = 1 / this.zoomLevel;
      this.ctx.font = `${Math.max(7, 8 / this.zoomLevel)}px "Fira Code", monospace`;
      this.ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';

      for (let i = 0; i < Math.min(12, this.fieldStars.length); i++) {
        const s = this.fieldStars[i];
        const sx = s.x * scaleX;
        const sy = s.y * scaleY;
        
        // Small box around cataloged Gaia star
        const boxSize = 8 / this.zoomLevel;
        this.ctx.strokeRect(sx - boxSize/2, sy - boxSize/2, boxSize, boxSize);
        if (i < 4) {
          this.ctx.fillText(`${s.catalog || "Sim"} ${s.id}`, sx + boxSize/2 + 3, sy - 2);
        }
      }
      this.ctx.restore();
    }

    // 2. Draw Motion Trajectory Trail across all epochs (when enabled)
    if (this.showTrail && this.allFrames && this.allFrames.length > 1) {
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(46, 150, 245, 0.85)'; // Vibranium kinetic purple
      this.ctx.lineWidth = 1.5 / this.zoomLevel;
      this.ctx.setLineDash([3 / this.zoomLevel, 3 / this.zoomLevel]);

      this.ctx.beginPath();
      for (let i = 0; i < this.allFrames.length; i++) {
        const f = this.allFrames[i];
        if (f.target_pos_px) {
          const tx = f.target_pos_px[0] * scaleX;
          const ty = f.target_pos_px[1] * scaleY;
          if (i === 0) this.ctx.moveTo(tx, ty);
          else this.ctx.lineTo(tx, ty);
        }
      }
      this.ctx.stroke();
      this.ctx.setLineDash([]);

      // Draw subtle kinetic dots at each epoch point
      for (let i = 0; i < this.allFrames.length; i++) {
        const f = this.allFrames[i];
        if (f.target_pos_px) {
          const tx = f.target_pos_px[0] * scaleX;
          const ty = f.target_pos_px[1] * scaleY;
          this.ctx.fillStyle = (f.visit_id === this.currentFrame.visit_id) ? '#EAFE07' : 'rgba(234, 254, 7, 0.4)';
          this.ctx.beginPath();
          this.ctx.arc(tx, ty, 3 / this.zoomLevel, 0, 2 * Math.PI);
          this.ctx.fill();
        }
      }
      this.ctx.restore();
    }

    // 3. Draw Target Reticle / Marker (Calibrated flux)
    if (this.showReticle) {
      const rx = this.reticlePos.x * scaleX;
      const ry = this.reticlePos.y * scaleY;
      
      this.ctx.save();
      this.ctx.strokeStyle = '#EAFE07'; // Selection accent
      this.ctx.lineWidth = 1.5 / this.zoomLevel;
      this.ctx.shadowColor = '#EAFE07';
      this.ctx.shadowBlur = 0;

      const rRadius = 14 / this.zoomLevel;
      const rArm = 20 / this.zoomLevel;
      const rGap = 5 / this.zoomLevel;

      // Reticle Circle
      this.ctx.beginPath();
      this.ctx.arc(rx, ry, rRadius, 0, 2 * Math.PI);
      this.ctx.stroke();

      // Crosshairs
      this.ctx.beginPath();
      this.ctx.moveTo(rx - rArm, ry);
      this.ctx.lineTo(rx - rGap, ry);
      this.ctx.moveTo(rx + rGap, ry);
      this.ctx.lineTo(rx + rArm, ry);
      this.ctx.moveTo(rx, ry - rArm);
      this.ctx.lineTo(rx, ry - rGap);
      this.ctx.moveTo(rx, ry + rGap);
      this.ctx.lineTo(rx, ry + rArm);
      this.ctx.stroke();

      // Reticle Label (Clean White)
      this.ctx.font = `${Math.max(9, 10 / this.zoomLevel)}px "Fira Code", monospace`;
      this.ctx.fillStyle = '#ffffff';
      this.ctx.shadowBlur = 0;
      this.ctx.fillText(`${this.targetName}`, rx + rRadius + 5, ry - 5);
      this.ctx.restore();
    }

    this.ctx.restore(); // Restore zoom/pan context for UI HUD overlays

    if (this.wipeActive()) {
      this.ctx.save();
      this.ctx.strokeStyle = '#EAFE07';
      this.ctx.lineWidth = 2;
      this.ctx.beginPath();
      this.ctx.moveTo(wipeX, 0);
      this.ctx.lineTo(wipeX, cHeight);
      this.ctx.stroke();
      this.ctx.fillStyle = '#07173F';
      this.ctx.beginPath();
      this.ctx.arc(wipeX, cHeight / 2, 14, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();
      this.ctx.fillStyle = '#EAFE07';
      this.ctx.beginPath();
      this.ctx.moveTo(wipeX - 9, cHeight / 2); this.ctx.lineTo(wipeX - 3, cHeight / 2 - 6); this.ctx.lineTo(wipeX - 3, cHeight / 2 + 6); this.ctx.closePath();
      this.ctx.moveTo(wipeX + 9, cHeight / 2); this.ctx.lineTo(wipeX + 3, cHeight / 2 - 6); this.ctx.lineTo(wipeX + 3, cHeight / 2 + 6); this.ctx.closePath();
      this.ctx.fill();
      this.ctx.font = '11px "Fira Code", monospace';
      this.ctx.fillStyle = '#FFFFFF';
      this.ctx.textBaseline = 'top';
      this.ctx.textAlign = 'right';
      this.ctx.fillText('FIRST', wipeX - 8, 52);
      this.ctx.textAlign = 'left';
      this.ctx.fillText('CURRENT', wipeX + 8, 52);
      this.ctx.restore();
    }

    // 4. Draw North-Up / East-Left Astrometric Compass & Scale (Fixed in HUD viewport space)
    if (this.showCompass) {
      const cx = 35;
      const cy = cHeight - 35;
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
      this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      this.ctx.font = '10px "Fira Code", monospace';
      this.ctx.lineWidth = 1.5;

      // North Arrow (pointing UP)
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.lineTo(cx, cy - 20);
      this.ctx.stroke();
      this.ctx.fillText('N', cx - 3, cy - 24);

      // East Arrow (pointing LEFT for astronomical standard)
      this.ctx.beginPath();
      this.ctx.moveTo(cx, cy);
      this.ctx.lineTo(cx - 20, cy);
      this.ctx.stroke();
      this.ctx.fillText('E', cx - 32, cy + 4);

      // Scale bar: 1 arcminute adjusted for dynamic pixel scale and zoom
      const pScale = (this.currentFrame && this.currentFrame.pixel_scale_arcsec) ? this.currentFrame.pixel_scale_arcsec : 6.15;
      const barPx = (60.0 / pScale) * scaleX * this.zoomLevel;
      const barX = cWidth - barPx - 15;
      const barY = cHeight - 25;
      this.ctx.beginPath();
      this.ctx.moveTo(barX, barY);
      this.ctx.lineTo(barX + barPx, barY);
      this.ctx.stroke();
      this.ctx.fillText('1 arcmin', barX + (barPx/2) - 24, barY - 4);

      this.ctx.restore();
    }
  }
}
