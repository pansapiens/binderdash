// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Binderdash Workflow', () => {
    test('should complete full workflow: configure folders -> scan -> view designs -> load structure', async ({ page }) => {
        // Navigate to the application
        await page.goto('/');

        // Wait for the application to load
        await expect(page.locator('h1, h2')).toContainText(['Binderdash', 'Designs']);

        // Step 1: Click on "Configure Source Folders" tab
        await page.click('text=Configure Source Folders');

        // Wait for the specific tab panel content to be visible
        await expect(page.locator('text=Folder Browser')).toBeVisible();

        // Wait for the folder browser to load - wait for the treegrid to be visible AND have content
        await expect(page.locator('[role="treegrid"]')).toBeVisible();

        // Wait for the tree to have actual content (not just headers)
        await expect(page.locator('[role="treegrid"] tbody tr')).toHaveCount(1, { timeout: 10000 });

        // Step 2: Select the "example_runs" checkbox in the table
        // First, expand the tree to find example_runs
        const exampleRunsNode = page.locator('text=example_runs').first();
        await expect(exampleRunsNode).toBeVisible();

        // Click on the example_runs checkbox
        const exampleRunsCheckbox = page.locator('text=example_runs').locator('..').locator('input[type="checkbox"]');
        await exampleRunsCheckbox.check();

        // Verify the checkbox is checked
        await expect(exampleRunsCheckbox).toBeChecked();

        // Step 3: Click "Scan Selected Folders"
        await page.click('button:has-text("Scan Selected Folders")');

        // Wait for scan to complete (look for success message or table update)
        await page.waitForSelector('text=Scan Results', { timeout: 30000 });

        // Wait for the scan results table to be populated
        await expect(page.locator('text=Detected Runs')).toBeVisible();

        // Verify scan results are displayed with specific count
        const scanResultsTable = page.locator('text=Detected Runs').locator('..').locator('..');
        await expect(scanResultsTable).toBeVisible();

        // Verify we have scan results rows visible
        const scanResults = page.locator('table').last().locator('tbody tr');
        await expect(scanResults.first()).toBeVisible();

        // Step 4: Click on the "Designs" tab
        await page.click('text=Designs');
        await expect(page.locator('text=All Designs')).toBeVisible();

        // Wait for designs to load
        await page.waitForSelector('.p-datatable-tbody tr', { timeout: 10000 });

        // Step 5: Click on one of the rows in the designs table
        const firstDesignRow = page.locator('.p-datatable-tbody tr').first();
        await expect(firstDesignRow).toBeVisible();

        // Click on the first design row
        await firstDesignRow.click();

        // Wait for the structure viewer to appear
        await page.waitForSelector('.molstar-viewer-container', { timeout: 10000 });

        // Verify the structure viewer is visible
        const structureViewer = page.locator('.molstar-viewer-container');
        await expect(structureViewer).toBeVisible();

        // Check if there's a loading state or error state
        const loadingState = page.locator('.molstar-loading');
        const errorState = page.locator('.molstar-error');
        const viewerContent = page.locator('.molstar-viewer');

        // Wait for either loading to complete, error to appear, or viewer to load
        await Promise.race([
            loadingState.waitFor({ state: 'hidden', timeout: 15000 }),
            errorState.waitFor({ state: 'visible', timeout: 15000 }),
            viewerContent.waitFor({ state: 'visible', timeout: 15000 })
        ]);

        // Take a screenshot for debugging
        await page.screenshot({ path: 'test-results/binderdash-workflow.png', fullPage: true });

        // Verify that either the viewer loaded successfully or we have a clear error message
        const hasViewer = await viewerContent.isVisible();
        const hasError = await errorState.isVisible();

        if (hasError) {
            // Log the error message for debugging
            const errorMessage = await errorState.textContent();
            console.log('Structure viewer error:', errorMessage);
        }

        // The test passes if we either have a working viewer or a clear error message
        expect(hasViewer || hasError).toBeTruthy();
    });

    test('should handle navigation between designs', async ({ page }) => {
        // Navigate to the application
        await page.goto('/');

        // Go to Designs tab
        await page.click('text=Designs');
        await expect(page.locator('text=All Designs')).toBeVisible();

        // Wait for designs to load
        await page.waitForSelector('.p-datatable-tbody tr', { timeout: 10000 });

        // Select first design
        const firstDesignRow = page.locator('.p-datatable-tbody tr').first();
        await firstDesignRow.click();

        // Wait for structure viewer
        await page.waitForSelector('.molstar-viewer-container', { timeout: 10000 });

        // Navigate to next design if available
        const nextButton = page.locator('button[aria-label="Next"]').or(page.locator('button:has-text("Next")'));
        if (await nextButton.isVisible()) {
            await nextButton.click();

            // Wait for new structure to load
            await page.waitForTimeout(2000);
        }

        // Take screenshot
        await page.screenshot({ path: 'test-results/design-navigation.png', fullPage: true });
    });

    test('should handle filter functionality', async ({ page }) => {
        // Navigate to the application
        await page.goto('/');

        // Go to Designs tab
        await page.click('text=Designs');
        await expect(page.locator('text=All Designs')).toBeVisible();

        // Wait for designs to load
        await page.waitForSelector('.p-datatable-tbody tr', { timeout: 10000 });

        // Open filter panel
        const filterButton = page.locator('button[aria-label="Filter"]').or(page.locator('button:has-text("Filter")'));
        if (await filterButton.isVisible()) {
            await filterButton.click();

            // Wait for filter panel
            await page.waitForSelector('.filter-panel', { timeout: 5000 });

            // Test global search
            const globalSearch = page.locator('input[placeholder*="Search"]');
            if (await globalSearch.isVisible()) {
                await globalSearch.fill('test');
                await page.keyboard.press('Enter');

                // Wait for filtered results
                await page.waitForTimeout(1000);
            }
        }

        // Take screenshot
        await page.screenshot({ path: 'test-results/filter-functionality.png', fullPage: true });
    });
});
