# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Backend API endpoints**:
  - `POST /api/runs/scan` - Scan selected folders for valid run directories
  - `GET /api/runs/{run_id}/table` - Get results table data for specific runs
  - `GET /api/runs/{run_id}/files/pdb/{filename}` - Stream PDB files for structure viewing
  - `GET /api/runs` - List all cached runs
  - `DELETE /api/runs/{run_id}` - Remove specific run from cache
  - `DELETE /api/runs` - Clear all runs from cache
  - `GET /api/designs` - List all designs from all cached runs
  - `DELETE /api/designs` - Clear all designs from cache
- **Run metadata enhancements**:
  - Added `project_id` field to RunMetadata with intelligent detection
  - Implemented `guess_project_id()` function for project ID detection from directory structure
  - Implemented `guess_run_name()` function for intelligent run name detection
  - Project ID guessing avoids disallowed names: 'runs', 'bindcraft', 'rfd', and numeric-only names
  - Run name guessing uses regex patterns to avoid disallowed names: 'results.*', 'bindcraft', 'batches', and numeric-only names
  - Both functions traverse directory hierarchy to find appropriate names
- **Run detection logic** based on prototypes:
  - BindCraft runs: detects `final_design_stats.csv` and `Accepted/` folder
  - RFD runs: detects `combined_scores.tsv` or `.cs` files in `af2_initial_guess/`
  - Recursive scanning with proper path validation
  - In-memory caching of scan results
- **Design parsing and aggregation**:
  - Unified design structure combining data from all runs
  - Automatic column detection for bindcraft (`Design`, `Average_i_pTM`) and RFD (`description`, `pae_interaction`)
  - Score columns handled as regular data columns in frontend instead of backend preprocessing
  - Smart sorting by appropriate scores (ascending for pae_interaction, descending for i_pTM)
  - PDB file association for structure viewing
  - Support for arbitrary additional columns from source tables with dynamic frontend column generation
- **Frontend components**:
  - Main app layout with TabView (Designs, Plots, Folder Browser)
  - FolderBrowser component with TreeTable for folder navigation and DataTable for scan results
  - RunsView component renamed to Designs view with comprehensive DataTable
  - PlotsView component with analytics dashboard
  - Structure viewer integrated below designs table
  - Added Project ID column to both Designs and Folder Browser tables
- **UI/UX improvements**:
  - Modern responsive design with PrimeVue components
  - Toast notifications for user feedback
  - Loading states and error handling
  - Pagination and sorting for data tables
  - Multi-select functionality for runs and designs
  - Column toggle functionality for designs table positioned above the table
  - Close button (X) in top-right corner of column selector panel
  - Comprehensive filter panel with global search, column-specific filters, and score range filtering
  - Default PrimeVue styling with checkbox row selection
- **Structure viewer integration**:
  - Molstar viewer for 3D protein structure visualization
  - PDB file loading via backend API endpoints
  - Navigation between selected structures with next/previous buttons
  - Row-based navigation reflecting filtered table state
  - Loading states and error handling for structure viewer
  - Proper cleanup and resource management

### Changed
- Updated project structure to support full-stack application
- Enhanced error handling and logging throughout backend
- Improved path validation and security measures
- Renamed "Runs & Structure Viewer" tab to "Designs"
- Restructured RunsView component to show designs instead of runs
- Updated FolderBrowser to show scan results as DataTable with run selection
- Integrated structure viewer below designs table instead of separate tab
- **Architecture improvements**:
  - Moved score column logic from backend to frontend for better separation of concerns
  - Backend now focuses on data parsing and metadata assignment
  - Frontend dynamically generates columns based on available data
  - Score columns (`pae_interaction`, `Average_i_pTM`) are now treated as regular data columns

### Fixed
- Static file serving configuration for frontend assets
- API endpoint routing and response formatting
- Toast component imports and usage across components
- **Molstar integration**: Refactored to separate component and fixed API issues
  - Created dedicated MolstarViewer.vue component for better modularity
  - Removed problematic molstar npm package that caused build failures
  - Switched to PDBe Molstar implementation from CDN (https://cdn.jsdelivr.net/npm/pdbe-molstar@latest/)
  - Fixed API usage to use direct PDBeMolstarPlugin constructor instead of non-existent create() method
  - Implemented proper PDB ID extraction from URLs for PDBe Molstar
  - Added extensive debugging and error handling for structure viewer
  - Separated Molstar logic from DesignsView component for better maintainability
  - Fixed TypeError: window.PDBeMolstarPlugin.create is not a function error
- **Automated Testing**: Added comprehensive Playwright test suite
  - Created reusable test script for complete workflow automation
  - Tests: Configure folders → Scan → View designs → Load structure
  - Added additional tests for design navigation and filter functionality
  - Configured automatic server startup and browser management
  - Added screenshot capture and HTML reporting for debugging
  - Created helper scripts and documentation for test execution

## [0.1.0] - 2025-08-31

### Added
- Initial project scaffolding
- FastAPI backend with basic static file serving
- Vue 3 frontend with Vite and PrimeVue
- Environment configuration with `.env` support
- Basic folder tree API endpoint (`GET /api/tree`)
- Project documentation and setup instructions
