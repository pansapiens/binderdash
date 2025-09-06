#!/usr/bin/env node

const { execSync } = require('child_process');
const path = require('path');

console.log('🧪 Starting Binderdash Playwright Tests...\n');

try {
    // Install Playwright browsers if not already installed
    console.log('📦 Installing Playwright browsers...');
    execSync('npx playwright install', { stdio: 'inherit' });

    // Create test results directory
    console.log('📁 Creating test results directory...');
    execSync('mkdir -p test-results', { stdio: 'inherit' });

    // Run the tests
    console.log('🚀 Running Playwright tests...');
    execSync('npx playwright test --reporter=html', { stdio: 'inherit' });

    console.log('\n✅ Tests completed successfully!');
    console.log('📊 Test report available at: playwright-report/index.html');
    console.log('📸 Screenshots saved in: test-results/');

} catch (error) {
    console.error('\n❌ Test execution failed:', error.message);
    process.exit(1);
}
