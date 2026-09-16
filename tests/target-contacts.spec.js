// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Target contacts: filtering on structure-derived conditions, and the contact map in
 * the structure viewer. Both need contacts computed first, which parses every structure
 * in the run, so these tests press Compute and wait for it rather than assuming a cache.
 */

/**
 * The small PD-L1 BindCraft run: the cheapest run to compute contacts for, and the
 * target the backend tests exercise.
 */
const RUN_NAME = 'pdl1-bindcraft';

/** Scan and ingest the PD-L1 example run over the API - faster and less brittle than
 * driving the folder browser, which the workflow spec already covers. */
async function ingestExampleRun(request) {
    const tree = await (await request.get('/api/tree')).json();
    const folders = (tree.folders || []).map((f) => f.path);
    if (!folders.length) return;
    const scan = await (
        await request.post('/api/runs/scan', { data: { folders, force_rescan_of_ingested: false } })
    ).json();
    const runs = (scan.runs || []).filter((r) => String(r.path || '').includes('/pdl1/'));
    if (runs.length) await request.post('/api/runs/ingest', { data: { runs } });
}

/** Put the PD-L1 run's designs in the Designs table; returns the Designs tab panel. */
async function ensureDesigns(page) {
    await page.goto('/');
    await page.getByRole('tab', { name: 'Select Runs' }).click();
    const panel = page
        .locator('[role="tabpanel"]')
        .filter({ has: page.getByRole('heading', { name: 'Select Runs' }) });
    const row = panel.locator('tbody tr', { hasText: RUN_NAME }).first();
    await expect(row).toBeVisible({ timeout: 30000 });
    if ((await row.locator('.p-checkbox').first().getAttribute('data-p-checked')) !== 'true') {
        await row.locator('input.p-checkbox-input').first().click();
    }

    await page.getByRole('tab', { name: 'Designs' }).click();
    const designs = page
        .locator('[role="tabpanel"]')
        .filter({ has: page.getByRole('heading', { name: 'Designs' }) });
    await expect(designs.locator('tbody tr').first()).toBeVisible({ timeout: 30000 });
    await expect(page.locator('text=No Designs Found')).toBeHidden({ timeout: 30000 });
    return designs;
}

test.describe('Target contacts', () => {
    // Computing contacts parses every structure in the run, so these are slow by nature.
    test.describe.configure({ timeout: 600000 });

    test.beforeAll(async ({ request }) => {
        await ingestExampleRun(request);
    });

    test('a contact condition narrows the filtered set', async ({ page }) => {
        await ensureDesigns(page);
        await page.getByRole('tab', { name: 'Filtering' }).click();

        const section = page.locator('text=2. Target contacts').first();
        await expect(section).toBeVisible({ timeout: 15000 });
        await section.click();

        // Contacts must exist before a condition can select anything.
        const compute = page.locator('button:has-text("Compute target contacts")').first();
        const computeVisible = await compute
            .waitFor({ state: 'visible', timeout: 20000 })
            .then(() => true)
            .catch(() => false);
        if (computeVisible) {
            await compute.click();
            await expect(compute).toBeEnabled({ timeout: 300000 });
        }

        await page.locator('button:has-text("Add condition")').first().click();

        // Pick the first target residue from the multiselect.
        await page.locator('.p-multiselect').first().click();
        const firstResidue = page.locator('.p-multiselect-overlay [role="option"]').first();
        await expect(firstResidue).toBeVisible({ timeout: 15000 });
        const residueLabel = (await firstResidue.innerText()).trim().split(/\s+/)[0];
        await firstResidue.click();
        await page.keyboard.press('Escape');

        // The condition joins the filter chain named by its residue, not by the
        // internal __tc_ column the engine actually filters on.
        const chain = page.locator('.filter-chain-summary').first();
        await expect(chain).toContainText(residueLabel, { timeout: 30000 });
        await expect(chain).not.toContainText('__tc_');

        await page.screenshot({ path: 'test-results/target-contacts-filter.png', fullPage: true });
    });

    test('the contact map colours the target in the structure viewer', async ({ page }) => {
        // The viewer logs this when PDBe Mol* rejects the selection, which is the only
        // way a broken colour map shows up - the canvas itself renders either way.
        const viewerWarnings = [];
        page.on('console', (msg) => {
            if (/residue colour map/i.test(msg.text())) viewerWarnings.push(msg.text());
        });

        const designs = await ensureDesigns(page);
        await designs.locator('tbody tr').first().click();
        await page.waitForSelector('.molstar-viewer-container', { timeout: 20000 });

        const disclosure = page.locator('#contact-map-disclosure');
        await expect(disclosure).toBeVisible({ timeout: 10000 });
        await disclosure.click();

        const enable = page.locator('#contact-map-enabled');
        await expect(enable).toBeVisible();
        await enable.click();

        // The Compute prompt only appears once coverage has been fetched.
        const compute = page.locator('#contact-map-content button:has-text("Compute")');
        const computeVisible = await compute
            .waitFor({ state: 'visible', timeout: 20000 })
            .then(() => true)
            .catch(() => false);
        if (computeVisible) {
            await compute.click();
            // Every design now has a record, so the prompt goes away.
            await expect(compute).toBeHidden({ timeout: 300000 });
        }

        // The summary names the residues the binders bury hardest, which only appears
        // once a profile came back over at least one computed design.
        await expect(page.locator('#contact-map-content')).toContainText(/strongest: [A-Z]\d+/, {
            timeout: 180000,
        });
        const key = page.locator('#contact-map-legend-slot');

        // ΔSASA is shown as a percentage of each residue's maximum, capped at 30% so the
        // gradient's contrast lands at the epitope boundary rather than on the few
        // residues that bury most of their area.
        await expect(key).toContainText('% of max');
        await expect(key).toContainText('≥ 30');

        // The key and its range slider live under the viewer, not in the panel, so they
        // stay visible while the panel is collapsed - and vanish when the map is off.
        await expect(key.locator('.p-slider-handle')).toHaveCount(2);
        await page.locator('#contact-map-disclosure').click();
        await expect(key.locator('.contact-map-legend-bar')).toBeVisible();
        await page.locator('#contact-map-disclosure').click();
        await page.locator('#contact-map-enabled').click();
        await expect(key.locator('.contact-map-legend-bar')).toBeHidden();
        await page.locator('#contact-map-enabled').click();
        await expect(key.locator('.contact-map-legend-bar')).toBeVisible();

        expect(viewerWarnings).toEqual([]);
        await page.screenshot({ path: 'test-results/target-contact-map.png', fullPage: true });
    });
});
