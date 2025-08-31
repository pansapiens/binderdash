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
- **Run detection logic** based on prototypes:
  - BindCraft runs: detects `final_design_stats.csv` and `Accepted/` folder
  - RFD runs: detects `combined_scores.tsv` or `.cs` files in `af2_initial_guess/`
  - Recursive scanning with proper path validation
  - In-memory caching of scan results
- **Frontend components**:
  - Main app layout with TabView (Runs & Structure Viewer, Plots, Folder Browser)
  - FolderBrowser component with TreeTable for folder navigation
  - RunsView component with DataTable for run listing and selection
  - PlotsView component with analytics dashboard
  - Structure viewer placeholder with navigation controls
- **UI/UX improvements**:
  - Modern responsive design with PrimeVue components
  - Toast notifications for user feedback
  - Loading states and error handling
  - Pagination and sorting for data tables
  - Multi-select functionality for runs and folders

### Changed
- Updated project structure to support full-stack application
- Enhanced error handling and logging throughout backend
- Improved path validation and security measures

### Fixed
- Static file serving configuration for frontend assets
- API endpoint routing and response formatting

## [0.1.0] - 2025-08-31

### Added
- Initial project scaffolding
- FastAPI backend with basic static file serving
- Vue 3 frontend with Vite and PrimeVue
- Environment configuration with `.env` support
- Basic folder tree API endpoint (`GET /api/tree`)
- Project documentation and setup instructions
