# Binderdash Automated Testing

This directory contains Playwright tests for the Binderdash application.

## Test Scripts

### Main Workflow Test
The `binderdash-workflow.spec.js` file contains the main test that automates the complete user workflow:

1. **Configure Source Folders**: Navigate to the folder browser tab
2. **Select example_runs**: Check the example_runs checkbox in the tree
3. **Scan Selected Folders**: Click the scan button and wait for results
4. **View Designs**: Switch to the Designs tab and wait for data to load
5. **Load Structure**: Click on a design row to load the Molstar viewer

### Additional Tests
- **Design Navigation**: Tests navigation between different designs
- **Filter Functionality**: Tests the filter panel and search functionality

## Running Tests

### Quick Start
```bash
# Install root dependencies (first time only)
pnpm install

# Run all tests with automatic setup
pnpm test
```

### Manual Commands
```bash
# Install Playwright browsers (first time only)
pnpm exec playwright install

# Run tests in headless mode
pnpm exec playwright test

# Run tests with browser UI visible
pnpm exec playwright test --headed

# Run tests with Playwright UI
pnpm exec playwright test --ui

# Debug tests step by step
pnpm exec playwright test --debug

# Show test report in browser (happens automatically when tests fail)
pnpm exec playwright show-report
```

## Test Results

- **HTML Report**: `playwright-report/index.html` - Detailed test results
- **Screenshots**: `test-results/` - Screenshots taken during test execution
- **Videos**: `test-results/` - Video recordings of test runs (if enabled)

## Configuration

The tests are configured in `playwright.config.js`:
- **Base URL**: `http://localhost:8000` (your FastAPI server)
- **Auto-start Server**: Automatically starts the backend server before tests
- **Browsers**: Tests run on Chromium, Firefox, and WebKit
- **Timeout**: 30 seconds for most operations, 15 seconds for structure loading

## Debugging

### Common Issues
1. **Server not starting**: Ensure Python environment is set up correctly
2. **Tests timing out**: Check if the backend API is responding
3. **Structure viewer errors**: Check browser console for Molstar-related errors

### Debug Mode
```bash
# Run a specific test in debug mode
pnpm exec playwright test --debug tests/binderdash-workflow.spec.js
```

### Screenshots
Screenshots are automatically taken at key points:
- `binderdash-workflow.png` - Complete workflow test
- `design-navigation.png` - Design navigation test
- `filter-functionality.png` - Filter functionality test

## Adding New Tests

1. Create new `.spec.js` files in the `tests/` directory
2. Use the existing test structure as a template
3. Add appropriate waits and assertions
4. Update this README with new test descriptions

## CI/CD Integration

The tests are designed to work in CI environments:
- Automatic server startup
- Retry logic for flaky tests
- HTML report generation
- Screenshot capture for debugging
