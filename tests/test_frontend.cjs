const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const elements = {};
const context = vm.createContext({
  document: {
    addEventListener() {},
    getElementById(id) { return elements[id] ||= { textContent: '' }; }
  }
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/js/app.js'), 'utf8'), context);
const update = vm.runInContext('SpherexApp.prototype.updateAstrometryHUD', context);
const target = { common_name: 'Test star', spectral_type: 'M', teff_k: 3000, discovery_epoch: 2000, ra_deg: 10, dec_deg: 20 };

// Archive and simulated responses have different astrometry contracts.
update({ proper_motion_total_arcsec_yr: 10.4 }, target);
assert.equal(elements.astFittedPm.textContent, '10.4"/yr (catalog)');
assert.equal(elements.astGaiaResidual.textContent, 'Not measured');
assert.match(elements.astVerdict.textContent, /not available/);

update({
  fitted_pm: { fitted_total_pm_arcsec_yr: 8.1, fitted_total_pm_mas_yr: 8100 },
  residuals: { total_residual_mas_yr: 32 }, validation_verdict: 'PASS'
}, target);
assert.equal(elements.astFittedPm.textContent, '8.1"/yr (8100 mas/yr)');
assert.equal(elements.astGaiaResidual.textContent, '32 mas/yr');
assert.equal(elements.astVerdict.textContent, 'PASS');
const audit = vm.runInContext('SpherexApp.prototype.updateFlickerAudit', context);
audit.call({ auditChart: { setData() {} } }, {});
assert.equal(elements.nullTestVal.textContent, 'Not provided');
audit.call({ auditChart: { setData() {} } }, { null_test_chi2_nu: 0 });
assert.equal(elements.nullTestVal.textContent, 'Chi2 = 0');

vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/js/audit_chart.js'), 'utf8'), context);
const renderAudit = vm.runInContext('AuditChart.prototype.render', context);
const labels = [];
renderAudit.call({ width: 360, height: 300, data: {}, ctx: {
  clearRect() {}, fillText(text) { labels.push(text); }
} });
assert.equal(labels[0], 'Per-star audit unavailable');
console.log('Frontend astrometry and missing-data checks passed.');
