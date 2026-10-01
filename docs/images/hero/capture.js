// Capture the screenshots that make up docs/images/binderdash-hero.png.
//
// 1. Start Binderdash on http://localhost:8000 with authentication disabled and
//    the example BindCraft run (ccl7_8fk6_...) ingested.
// 2. From the repository root:
//      node docs/images/hero/capture.js /tmp/bdshots
//      python3 docs/images/hero/compose.py /tmp/bdshots
//
// Mol* needs WebGL, which headless Chromium only provides through SwiftShader,
// hence the launch flags.
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../../../node_modules/@playwright/test'));

const OUT = process.argv[2] || '/tmp/bdshots';
const BASE = process.env.BINDERDASH_URL || 'http://localhost:8000';
const RUN = process.env.HERO_RUN || 'ccl7_8fk6';
const TOGGLE_COLUMNS = ['Project ID', 'Run Name', 'Average I PAE', 'Average ShapeComplementarity', 'Average DG'];

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

(async () => {
  require('fs').mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1000 }, deviceScaleFactor: 2 });

  await page.goto(`${BASE}/#select-runs`);
  await page.waitForTimeout(3000);
  await page.locator('tr', { hasText: RUN }).first().locator('.p-checkbox').first().click();
  await page.waitForTimeout(1000);

  await page.goto(`${BASE}/#designs`);
  await page.waitForSelector('.p-datatable-tbody tr', { timeout: 20000 });

  // Swap the ID columns for more score columns.
  await page.locator('.p-multiselect', { hasText: 'columns shown' }).click();
  await page.waitForTimeout(500);
  for (const name of TOGGLE_COLUMNS) {
    await page.locator('.p-multiselect-option')
      .filter({ hasText: new RegExp(`^\\s*${escapeRe(name)}\\s*$`) })
      .first().click();
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);

  const rows = page.locator('.p-datatable-tbody tr');
  await rows.nth(0).locator('td').nth(1).click();
  await page.waitForTimeout(1000);
  await rows.nth(2).locator('.p-checkbox').first().click().catch(() => {});
  await page.waitForTimeout(9000);

  // Colour by chain rather than pLDDT so binder and target are distinct.
  await page.getByRole('button', { name: 'pLDDT' }).first().click();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: path.join(OUT, 'full.png'), fullPage: true });
  await page.locator('.p-datatable').first().screenshot({ path: path.join(OUT, 'table.png') });
  await page.locator('.molstar-viewer-container').first().screenshot({ path: path.join(OUT, 'viewer.png') });

  await browser.close();
})();
