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
    this.showCompass = true;
    this.showStars = true;
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
    // Mouse Wheel Zoom
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      this.setZoom(this.zoomLevel * zoomFactor);
    }, { passive: false });

    // Mouse Drag Pan & Wipe Interaction
    this.canvas.addEventListener('mousedown', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const clickX = (e.clientX - rect.left) * (this.canvas.width / rect.width);
      if (this.showWipe && Math.abs(clickX - this.canvas.width * this.wipeRatio) < 22) {
        this.isDraggingWipe = true;
        this.canvas.style.cursor = 'ew-resize';
        return;
      }
      if (e.button === 0) { // Left click
        this.isDragging = true;
        this.dragStart = { x: e.clientX - this.panOffset.x, y: e.clientY - this.panOffset.y };
        this.canvas.style.cursor = 'grabbing';
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (this.isDraggingWipe) {
        const rect = this.canvas.getBoundingClientRect();
        const curX = (e.clientX - rect.left) * (this.canvas.width / rect.width);
        this.wipeRatio = Math.max(0.05, Math.min(0.95, curX / this.canvas.width));
        this.render();
        return;
      }
      if (this.isDragging) {
        this.panOffset = {
          x: e.clientX - this.dragStart.x,
          y: e.clientY - this.dragStart.y
        };
        this.render();
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDraggingWipe = false;
      if (this.isDragging) {
        this.isDragging = false;
        this.canvas.style.cursor = 'crosshair';
      }
    });

    // Hover Coordinate Inspector
    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.currentFrame || !this.coordReadoutEl) return;
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Invert pan and zoom
      const cWidth = this.canvas.width;
      const cHeight = this.canvas.height;
      const centerX = cWidth / 2 + this.panOffset.x;
      const centerY = cHeight / 2 + this.panOffset.y;

      const normX = (mouseX - centerX) / (cWidth * this.zoomLevel) + 0.5;
      const normY = (mouseY - centerY) / (cHeight * this.zoomLevel) + 0.5;

      const w = (this.currentFrame && this.currentFrame.rgb_pixels) ? this.currentFrame.rgb_pixels[0].length : 64;
      const h = (this.currentFrame && this.currentFrame.rgb_pixels) ? this.currentFrame.rgb_pixels.length : 64;

      const pxX = Math.floor(normX * w);
      const pxY = Math.floor(normY * h);

      const pixelScale = (this.currentFrame && this.currentFrame.pixel_scale_arcsec) ? this.currentFrame.pixel_scale_arcsec : 6.15;
      const fovArcmin = (this.currentFrame && this.currentFrame.fov_arcmin) ? this.currentFrame.fov_arcmin : ((w * pixelScale) / 60.0);

      if (pxX >= 0 && pxX < w && pxY >= 0 && pxY < h) {
        const dArcsecX = (pxX - w / 2) * pixelScale;
        const dArcsecY = (h / 2 - pxY) * pixelScale;
        this.coordReadoutEl.textContent = `PX [${pxX}, ${pxY}] | dRA ${dArcsecX > 0 ? '+' : ''}${dArcsecX.toFixed(1)}" | dDec ${dArcsecY > 0 ? '+' : ''}${dArcsecY.toFixed(1)}" | ${fovArcmin.toFixed(1)}' FOV`;
      } else {
        this.coordReadoutEl.textContent = `FOV ${fovArcmin.toFixed(1)}' | ${pixelScale.toFixed(2)}"/px`;
      }
    });
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

    // Apply Zoom & Pan Transform
    this.ctx.save();
    this.ctx.translate(cWidth / 2 + this.panOffset.x, cHeight / 2 + this.panOffset.y);
    this.ctx.scale(this.zoomLevel, this.zoomLevel);
    this.ctx.translate(-cWidth / 2, -cHeight / 2);

    if (this.showWipe && this.allFrames && this.allFrames.length > 1) {
      // Split Wipe Mode: Compare Frame 0 (Baseline) against currentFrame (Active)
      const baseFrame = this.allFrames[0];
      const baseOff = this._createOffscreenFromPixels(baseFrame.rgb_pixels) || currentOff;
      const wipeX = cWidth * this.wipeRatio;

      // 1. Draw Baseline Frame on Left
      this.ctx.save();
      this.ctx.beginPath();
      this.ctx.rect(0, 0, wipeX, cHeight);
      this.ctx.clip();
      this.ctx.drawImage(baseOff.canvas, 0, 0, cWidth, cHeight);
      this.ctx.restore();

      // 2. Draw Active Frame on Right
      this.ctx.save();
      this.ctx.beginPath();
      this.ctx.rect(wipeX, 0, cWidth - wipeX, cHeight);
      this.ctx.clip();
      this.ctx.drawImage(currentOff.canvas, 0, 0, cWidth, cHeight);
      this.ctx.restore();

      // 3. Draw Vertical Wipe Divider Line
      this.ctx.save();
      this.ctx.strokeStyle = '#a2d4c3';
      this.ctx.lineWidth = 2 / this.zoomLevel;
      this.ctx.beginPath();
      this.ctx.moveTo(wipeX, 0);
      this.ctx.lineTo(wipeX, cHeight);
      this.ctx.stroke();

      // Wipe drag handle
      const handleR = 12 / this.zoomLevel;
      this.ctx.fillStyle = '#09090b';
      this.ctx.strokeStyle = '#a2d4c3';
      this.ctx.beginPath();
      this.ctx.arc(wipeX, cHeight / 2, handleR, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.stroke();
      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = `${Math.max(8, 9 / this.zoomLevel)}px "JetBrains Mono", monospace`;
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      this.ctx.fillText('◧', wipeX, cHeight / 2);
      this.ctx.restore();
    } else {
      // Draw main pixel array
      this.ctx.drawImage(currentOff.canvas, 0, 0, cWidth, cHeight);
    }

    const scaleX = cWidth / w;
    const scaleY = cHeight / h;

    // 1. Draw Gaia DR3 Reference Field Stars (when enabled)
    if (this.showStars && this.fieldStars && this.fieldStars.length > 0) {
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)'; // Clean silver
      this.ctx.lineWidth = 1 / this.zoomLevel;
      this.ctx.font = `${Math.max(7, 8 / this.zoomLevel)}px "JetBrains Mono", monospace`;
      this.ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';

      for (let i = 0; i < Math.min(12, this.fieldStars.length); i++) {
        const s = this.fieldStars[i];
        const sx = s.x * scaleX;
        const sy = s.y * scaleY;
        
        // Small box around cataloged Gaia star
        const boxSize = 8 / this.zoomLevel;
        this.ctx.strokeRect(sx - boxSize/2, sy - boxSize/2, boxSize, boxSize);
        if (i < 4) {
          this.ctx.fillText(`Gaia ${s.id}`, sx + boxSize/2 + 3, sy - 2);
        }
      }
      this.ctx.restore();
    }

    // 2. Draw Motion Trajectory Trail across all epochs (when enabled)
    if (this.showTrail && this.allFrames && this.allFrames.length > 1) {
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(168, 85, 247, 0.6)'; // Vibranium kinetic purple
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
          this.ctx.fillStyle = (f.visit_id === this.currentFrame.visit_id) ? '#a2d4c3' : 'rgba(162, 212, 195, 0.4)';
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
      this.ctx.strokeStyle = '#a2d4c3'; // Selection accent
      this.ctx.lineWidth = 1.5 / this.zoomLevel;
      this.ctx.shadowColor = '#a2d4c3';
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
      this.ctx.font = `${Math.max(9, 10 / this.zoomLevel)}px "JetBrains Mono", monospace`;
      this.ctx.fillStyle = '#ffffff';
      this.ctx.shadowBlur = 0;
      this.ctx.fillText(`${this.targetName}`, rx + rRadius + 5, ry - 5);
      this.ctx.restore();
    }

    this.ctx.restore(); // Restore zoom/pan context for UI HUD overlays

    // 4. Draw North-Up / East-Left Astrometric Compass & Scale (Fixed in HUD viewport space)
    if (this.showCompass) {
      const cx = 35;
      const cy = cHeight - 35;
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
      this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      this.ctx.font = '10px "JetBrains Mono", monospace';
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
