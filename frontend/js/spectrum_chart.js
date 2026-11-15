/**
 * SPHEREx Planet X Challenge - 102-Channel Spectrophotometry Interactive Chart
 * Renders calibrated fluxes across 0.744 - 5.002 um with molecular band markers.
 */

class SpectrumChart {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.canvas = document.createElement('canvas');
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.data = null;
    this.hoverPoint = null;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.setupInteractivity();
  }

  resize() {
    this.width = this.container.clientWidth || 600;
    this.height = this.container.clientHeight || 280;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    if (this.data) this.render();
  }

  setData(spectrumPayload) {
    this.data = spectrumPayload;
    this.render();
  }

  setupInteractivity() {
    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.data || !this.data.spectrum) return;
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      
      const margin = { left: 55, right: 25, top: 25, bottom: 35 };
      const plotWidth = this.width - margin.left - margin.right;
      
      const lambdaMin = 0.744;
      const lambdaMax = 5.002;
      const lambdaHover = lambdaMin + ((mouseX - margin.left) / plotWidth) * (lambdaMax - lambdaMin);

      // Find closest channel
      let closest = null;
      let minDiff = 1e9;
      for (const pt of this.data.spectrum) {
        const diff = Math.abs(pt.wavelength_um - lambdaHover);
        if (diff < minDiff) {
          minDiff = diff;
          closest = pt;
        }
      }
      this.hoverPoint = closest;
      this.render();
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverPoint = null;
      this.render();
    });
  }

  render() {
    if (!this.data || !this.data.spectrum) return;

    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    ctx.clearRect(0, 0, w, h);

    const margin = { left: 55, right: 25, top: 25, bottom: 35 };
    const pw = w - margin.left - margin.right;
    const ph = h - margin.top - margin.bottom;

    const lambdaMin = 0.744;
    const lambdaMax = 5.002;

    const pts = this.data.spectrum;
    let maxFlux = 0.1, minFlux = 0;
    for (const p of pts) {
      maxFlux = Math.max(maxFlux, p.flux_mjy + p.flux_err_mjy);
      minFlux = Math.min(minFlux, p.flux_mjy - p.flux_err_mjy);
    }
    maxFlux *= 1.15; // margin

    const xMap = (lam) => margin.left + ((lam - lambdaMin) / (lambdaMax - lambdaMin)) * pw;
    const yMap = (flux) => margin.top + ph - ((flux-minFlux) / (maxFlux-minFlux)) * ph;

    // 1. Draw Detector Bands (D1..D6) - Clean Monochrome Alternating
    const detectors = [
      { name: "D1", min: 0.744, max: 1.116, color: "rgba(255, 255, 255, 0.015)" },
      { name: "D2", min: 1.099, max: 1.651, color: "rgba(255, 255, 255, 0.035)" },
      { name: "D3", min: 1.636, max: 2.421, color: "rgba(255, 255, 255, 0.015)" },
      { name: "D4", min: 2.423, max: 3.822, color: "rgba(255, 255, 255, 0.035)" },
      { name: "D5", min: 3.809, max: 4.420, color: "rgba(255, 255, 255, 0.015)" },
      { name: "D6", min: 4.412, max: 5.002, color: "rgba(255, 255, 255, 0.035)" }
    ];

    for (const det of detectors) {
      const x1 = xMap(det.min);
      const x2 = xMap(det.max);
      ctx.fillStyle = det.color;
      ctx.fillRect(x1, margin.top, x2 - x1, ph);

      ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillText(det.name, x1 + 4, margin.top + 12);
    }

    // 2. Draw Molecular Feature Markers (Delicate Silver Dashed)
    const molecularFeatures = this.data.source?.includes("real") ? [] : [
      { name: "H2O 1.4u", lam: 1.40 },
      { name: "H2O 1.9u", lam: 1.90 },
      { name: "CH4 2.2u", lam: 2.20 },
      { name: "H2O-Ice 3.0u", lam: 3.00 },
      { name: "CH4 3.32u", lam: 3.32 },
      { name: "CO2 4.27u", lam: 4.27 },
      { name: "CO 4.60u", lam: 4.60 }
    ];

    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
    ctx.lineWidth = 1;
    for (const mol of molecularFeatures) {
      const mx = xMap(mol.lam);
      ctx.beginPath();
      ctx.moveTo(mx, margin.top);
      ctx.lineTo(mx, margin.top + ph);
      ctx.stroke();

      ctx.save();
      ctx.translate(mx - 2, margin.top + ph - 8);
      ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillText(mol.name, 0, 0);
      ctx.restore();
    }
    ctx.setLineDash([]);

    // 3. Draw Grid Lines & Axes (Hairline Monochrome)
    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.lineWidth = 1;
    // Y-ticks
    for (let i = 0; i <= 4; i++) {
      const fluxVal = minFlux + ((maxFlux-minFlux) / 4) * i;
      const gy = yMap(fluxVal);
      ctx.beginPath();
      ctx.moveTo(margin.left, gy);
      ctx.lineTo(margin.left + pw, gy);
      ctx.stroke();

      ctx.fillStyle = "#a1adb3";
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.textAlign = "right";
      ctx.fillText(fluxVal.toFixed(1), margin.left - 8, gy + 3);
    }

    // X-ticks (Wavelength)
    ctx.textAlign = "center";
    for (let lam = 1.0; lam <= 5.0; lam += 0.5) {
      const gx = xMap(lam);
      ctx.beginPath();
      ctx.moveTo(gx, margin.top);
      ctx.lineTo(gx, margin.top + ph);
      ctx.stroke();

      ctx.fillStyle = "#a1adb3";
      ctx.fillText(`${lam.toFixed(1)} um`, gx, margin.top + ph + 18);
    }

    // 4. Draw Calibrated Flux Spectrum Curve (Calibrated flux)
    ctx.save();
    ctx.shadowColor = "#a2d4c3";
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.strokeStyle = "#a2d4c3";
    ctx.lineWidth = 2;
    for (let i = 0; !this.data.source?.includes("real") && i < pts.length; i++) {
      const x = xMap(pts[i].wavelength_um);
      const y = yMap(pts[i].flux_mjy);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();

    // Draw error bars and channel points (White Core + Purple Glow)
    for (const p of pts) {
      const x = xMap(p.wavelength_um);
      const y = yMap(p.flux_mjy);
      const yErrTop = yMap(p.flux_mjy + p.flux_err_mjy);
      const yErrBot = yMap(p.flux_mjy - p.flux_err_mjy);

      ctx.strokeStyle = "rgba(162, 212, 195, 0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, yErrTop);
      ctx.lineTo(x, yErrBot);
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x, y, 1.8, 0, 2 * Math.PI);
      ctx.fill();
    }

    // 5. Draw Tooltip on Hover
    if (this.hoverPoint) {
      const hp = this.hoverPoint;
      const hx = xMap(hp.wavelength_um);
      const hy = yMap(hp.flux_mjy);

      ctx.strokeStyle = "#a2d4c3";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(hx, hy, 5, 0, 2 * Math.PI);
      ctx.stroke();

      // Tooltip Card
      const ttText1 = `${hp.detector} ${hp.mjd ? `MJD ${hp.mjd.toFixed(2)}` : `Ch ${hp.channel_in_detector}`} (${hp.wavelength_um.toFixed(3)} um)`;
      const ttText2 = `Flux: ${hp.flux_mjy.toFixed(3)} +/- ${hp.flux_err_mjy.toFixed(3)} mJy (SNR ${hp.snr})`;
      const ttWidth = 240;
      const ttX = Math.min(w - ttWidth - 10, Math.max(margin.left, hx - ttWidth / 2));
      const ttY = margin.top + 8;

      ctx.fillStyle = "rgba(8, 8, 12, 0.95)";
      ctx.strokeStyle = "rgba(162, 212, 195, 0.5)";
      ctx.lineWidth = 1;
      ctx.fillRect(ttX, ttY, ttWidth, 36);
      ctx.strokeRect(ttX, ttY, ttWidth, 36);

      ctx.fillStyle = "#a2d4c3";
      ctx.textAlign = "left";
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillText(ttText1, ttX + 8, ttY + 14);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(ttText2, ttX + 8, ttY + 28);
    }
  }
}
