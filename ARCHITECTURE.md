# SPHEREx Planet X Challenge: Mathematical & Systems Architecture

This document provides the mathematical specifications, tensor operations, and data contracts implemented across the integrated pipeline.

---

## 1. Astrometric Space Motion & Parallax Propagation

Let a cataloged celestial source have coordinates $(\alpha_0, \delta_0)$ at reference discovery epoch $t_0$, proper motion $(\mu_{\alpha *}, \mu_\delta)$ with $\mu_{\alpha *} = \mu_\alpha \cos \delta_0$ in $\text{mas/yr}$, and parallax $\varpi$ in $\text{mas}$.

At observation epoch $t_{\text{obs}}$ with $\Delta t = t_{\text{obs}} - t_0$ (years):
1. **Proper Motion Vector:**
   $$\Delta \alpha_{\text{PM}} = \frac{\mu_{\alpha *}}{\cos \delta_0} \cdot \Delta t \quad [\text{mas}]$$
   $$\Delta \delta_{\text{PM}} = \mu_\delta \cdot \Delta t \quad [\text{mas}]$$
2. **Annual Parallax Reflex Ellipse:**
   Let $(X_\oplus, Y_\oplus, Z_\oplus)$ be Earth's barycentric coordinates in AU at $t_{\text{obs}}$:
   $$\Delta \alpha_\varpi = \frac{\varpi}{\cos \delta_0} \left( X_\oplus \sin \alpha_0 - Y_\oplus \cos \alpha_0 \right) \quad [\text{mas}]$$
   $$\Delta \delta_\varpi = \varpi \left( X_\oplus \cos \alpha_0 \sin \delta_0 + Y_\oplus \sin \alpha_0 \sin \delta_0 - Z_\oplus \cos \delta_0 \right) \quad [\text{mas}]$$
3. **Propagated Coordinates:**
   $$\alpha(t_{\text{obs}}) = \alpha_0 + \frac{\Delta \alpha_{\text{PM}} + \Delta \alpha_\varpi}{3,600,000} \quad [\text{deg}]$$
   $$\delta(t_{\text{obs}}) = \delta_0 + \frac{\Delta \delta_{\text{PM}} + \Delta \delta_\varpi}{3,600,000} \quad [\text{deg}]$$

---

## 2. Akhilesh's 5-Step Band-Balanced LVF Stacking Engine

### Step 1: Per-Exposure Spectral Labelling
For each exposure $i$ on detector $d \in \{D_1 \dots D_6\}$, evaluate the spectral WCS key `'W'` at $(x, y)$ to determine target central wavelength $\lambda_{\text{target}, i}$. Map $\lambda_{\text{target}, i}$ to discrete spectral channel index $b_i \in \{1 \dots 17\}$:
$$b_i = 1 + \left\lfloor \frac{\lambda_{\text{target}, i} - \lambda_{\min, d}}{\lambda_{\max, d} - \lambda_{\min, d}} \cdot 17 \right\rfloor$$

### Step 2: Two-Level Hierarchical Co-Addition
* **Level 1 (Within-Channel Inverse-Variance Mean):**
  For each channel $b \in \{1 \dots 17\}$ in visit $v$ and detector $d$:
  $$w_i(x,y) = \frac{1}{\sigma_i^2(x,y)}$$
  $$F_{v,d,b}(x,y) = \frac{\sum_{i \in \mathcal{E}_{v,d,b}} w_i(x,y) I_i(x,y)}{\sum_{i \in \mathcal{E}_{v,d,b}} w_i(x,y)}, \quad \sigma^2_{v,d,b}(x,y) = \frac{1}{\sum_{i \in \mathcal{E}_{v,d,b}} w_i(x,y)}$$
* **Level 2 (Across-Channel Equal-Weight Mean):**
  Average single-channel composites with **one equal vote per channel**:
  $$F_{v,d}(x,y) = \frac{1}{|\mathcal{C}_{\text{shared}}|} \sum_{b \in \mathcal{C}_{\text{shared}}} F_{v,d,b}(x,y)$$

### Step 3: Shared Channel Intersection Gate
$$\mathcal{C}_{\text{shared}} = \bigcap_{v=1}^M \left\{ b \in \{1 \dots 17\} : \mathcal{E}_{v,d,b} \neq \emptyset \right\}$$
Reliability threshold: $|\mathcal{C}_{\text{shared}}| \ge 10$.

### Step 4: Temporal Median Template & Difference Imaging
$$T_d(x,y) = \operatorname{median}_{v=1\dots M} F_{v,d}(x,y)$$
$$D_{v,d}(x,y) = F_{v,d}(x,y) - T_d(x,y)$$

---

## 3. Idea 1 - Metadata-Driven Relative Frame Positioning

Construct output gnomonic grid $\mathcal{G}_{\text{out}}$ centered on reference coordinate $(\alpha_c, \delta_c)$ at $(u_0, v_0)$ with pixel scale $s = 6.15\text{ arcsec/px}$.

1. Standard Tangent Plane Coordinates:
   $$\xi = -\frac{\pi}{180} \cdot \frac{s}{3600} \cdot (u - u_0), \quad \eta = +\frac{\pi}{180} \cdot \frac{s}{3600} \cdot (v - v_0)$$
2. Inverse Gnomonic Projection:
   $$\alpha(u,v) = \alpha_c + \operatorname{atan2}\left(\xi, \cos\delta_c - \eta\sin\delta_c\right)$$
   $$\delta(u,v) = \operatorname{atan2}\left(\sin\delta_c + \eta\cos\delta_c, \sqrt{(\cos\delta_c - \eta\sin\delta_c)^2 + \xi^2}\right)$$
3. **Dual Frame Transformations:**
   * **Inertial Sky-Fixed Frame:** Background stars stationary; movers translate.
   * **Co-Moving Target-Locked Frame:** Evaluation point shifted by target displacement vector $\Delta \vec{\theta}(t_i)$, pinning the moving object at $(u_0, v_0)$ in every frame while background stars drift backwards.

---

## 4. Idea 2 - Infrared-to-Visible Spectral Superposition

1. **Logarithmic Wavelength Bijection:**
   $$\lambda_{\text{vis}}(\lambda_{\text{IR}}) = 380 + 370 \cdot \frac{\ln(\lambda_{\text{IR}} / 0.744)}{\ln(5.002 / 0.744)} \quad [\text{nm}]$$
2. **CIE 1931 Integration & Detector Hue Assignment:**
   * $D_1$ ($0.744 - 1.116\,\mu\text{m}$): Violet $\to$ Royal Blue
   * $D_2$ ($1.099 - 1.651\,\mu\text{m}$): Blue $\to$ Cyan
   * $D_3$ ($1.636 - 2.421\,\mu\text{m}$): Cyan $\to$ Green
   * $D_4$ ($2.423 - 3.822\,\mu\text{m}$): Green $\to$ Orange
   * $D_5$ ($3.809 - 4.420\,\mu\text{m}$): Orange $\to$ Deep Red
   * $D_6$ ($4.412 - 5.002\,\mu\text{m}$): Deep Red $\to$ Far-IR Ruby Red
3. **Lupton (2004) Chromaticity-Preserving Asinh Compression:**
   $$I_{\text{mean}} = \frac{R + G + B}{3}$$
   $$f(I) = \frac{\operatorname{asinh}(I \cdot Q)}{\operatorname{asinh}(Q)} \cdot \frac{1}{I + \epsilon}$$
   $$R' = R \cdot f(I_{\text{mean}}), \quad G' = G \cdot f(I_{\text{mean}}), \quad B' = B \cdot f(I_{\text{mean}})$$
4. **sRGB Gamma Companding:**
   $$C_{\text{sRGB}} = \begin{cases} 12.92 C' & C' \le 0.0031308 \\ 1.055 C'^{1/2.4} - 0.055 & C' > 0.0031308 \end{cases}$$
