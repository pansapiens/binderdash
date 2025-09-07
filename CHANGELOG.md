# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Enhanced Structure Viewer
- **Improved MolstarViewer performance**: Replaced destroy/recreate approach with PDBe Molstar `update()` helper method for smoother navigation
  - **Faster structure loading**: Uses `visual.update()` method to load new structures without recreating the entire viewer instance
  - **Auto-focus functionality**: Automatically focuses on new structures when navigating between designs
  - **Enhanced viewer controls**: Added focus and spin toggle buttons to the structure viewer interface
  - **Configurable viewer options**: Added props for auto-focus, show controls, and background color customization
  - **Helper method exposure**: Exposed useful PDBe Molstar helper methods (focus, spin, highlight, background color) for programmatic control
  - **Better error handling**: Improved error handling with fallback to full reload if update method fails
  - **Control panel preservation**: Fixed control panel disappearing after loading second structure by using minimal update parameters
  - **Theme consistency**: Restored visual theme parameters (visualStyle, hideStructure, bgColor) while preserving control panel state
  - **Improved structure details**: Enhanced structure information display with better formatted table layout

### Security Improvements
- **Migrated to secure HttpOnly cookies**: Replaced localStorage token storage with industry-standard secure cookie authentication
  - **XSS Protection**: Authentication tokens now stored in HttpOnly cookies, preventing JavaScript access and XSS token theft
  - **CSRF Protection**: Added comprehensive CSRF protection middleware with token validation
  - **Secure Cookie Attributes**: Implemented `HttpOnly`, `Secure`, and `SameSite` cookie attributes for maximum security
  - **Automatic Cookie Management**: Browser automatically handles cookie transmission, eliminating manual Authorization header management
  - **PDB File Security**: Removed insecure query parameter authentication for PDB file access, now uses secure cookies
  - **Backward Compatibility**: Maintained support for both cookie and header-based authentication during transition

### Added
- **Local username/password authentication**: Implemented comprehensive authentication system
  - Added JWT token-based authentication with configurable expiration (30 minutes default)
  - Created password encryption utility script (`backend/scripts/encrypt_password.py`) for generating bcrypt hashes
  - Added authentication endpoints: `/api/auth/login`, `/api/auth/me`, `/api/auth/status`, `/api/auth/logout`
  - Implemented `DISABLE_AUTHENTICATION` environment variable to completely disable auth when set to 'true'
  - Protected all previously unsecured endpoints: runs management, designs management, and plotting APIs
  - Added Vue.js login component with modern UI using PrimeVue components
  - Added authentication state management with Pinia store
  - Updated webapi.ts to use secure cookie-based authentication with CSRF token support
  - Added user info display and logout functionality in the main app header
  - Authentication is optional - only enforced when `LOCAL_USERS` is configured and `DISABLE_AUTHENTICATION` is not 'true'
  - Fixed PDB file access authentication by supporting token-based authentication via query parameters for external viewers like Mol*
  - Fixed frontend authentication flow to prevent premature data loading before authentication is complete
  - Added proper loading states and authentication-aware data fetching to prevent "Failed to load designs" errors on login page
  - Improved logout button styling and positioning - now uses primary styling and positioned in top right of header
  - Enhanced authentication error handling - expired tokens now automatically redirect to login page without showing error toasts
  - Fixed logout button positioning to properly appear in top right corner of header
- **Configurable CORS origins**: Added support for `CORS_ALLOWED_ORIGINS` environment variable
  - Allows specifying comma-separated list of allowed origins for CORS requests
  - Defaults to `*` (allow all origins) if not configured
  - Supports both development (localhost) and production (domain) origins
  - Updated `.env.example` with configuration examples
- **Improved password encryption utility**: Enhanced `encrypt_password.py` script usability
  - Made interactive mode the default (username as positional argument)
  - Added support for password input via stdin (useful for scripts)
  - Simplified command-line interface with `--password` option
  - Updated documentation and examples throughout
- **Protocol filtering in Plots tab**: Added "Filter by Protocol" dropdown to allow filtering runs by binding protocol (bindcraft/rfd) before plotting

### Changed
- **Simplified plotting architecture**: Removed unnecessary backend plotting API endpoints (`/api/runs/plots/scatter` and `/api/runs/plots/histogram`). Frontend now fetches raw data directly and handles all plotting logic with Vega-Lite, reducing API complexity and improving performance.

### Fixed
- **JSON serialization error**: Fixed `ValueError: Out of range float values are not JSON compliant: nan` by properly handling NaN and infinite values in DataFrame-to-JSON conversion in the `/api/runs/{run_id}/table` endpoint.
- **Initial scatter plot rendering**: Fixed issue where scatter plots wouldn't render immediately when runs are first selected, requiring users to change axis dropdowns to see the plot. Added proper DOM timing and container dimension checks.
- **Backend API endpoints**:
  - `GET /api/tree` - Return folder structure for the file browser
  - `POST /api/runs/scan` - Scan selected folders for valid run directories
  - `GET /api/runs/{run_id}/table` - Get results table data for specific runs
  - `GET /api/runs/{run_id}/files/pdb/{filename}` - Stream PDB files for structure viewing
  - `GET /api/runs` - List all cached runs
  - `DELETE /api/runs/{run_id}` - Remove specific run from cache
  - `DELETE /api/runs` - Clear all runs from cache
  - `GET /api/designs` - List all designs from all cached runs
  - `DELETE /api/designs` - Clear all designs from cache
  - `POST /api/runs/plots/columns` - Get combined columns from multiple runs
  - `POST /api/runs/plots/scatter` - Get raw data for scatter plots from multiple runs
  - `POST /api/runs/plots/histogram` - Get raw data for histograms from multiple runs
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
  - PlotsView component with Vega-Lite based plotting system (scatter plots and histograms)
  - Automatic data refresh when switching to Plots tab
  - Multi-run data merging for combined plots
  - Frontend-based Vega-Lite specification generation
  - Structure viewer integrated below designs table
  - Added Project ID column to both Designs and Folder Browser tables
  - Centralized API client (`webapi.js`) for all frontend API calls with proper error handling
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
- **Plots system refactoring**:
  - Moved Vega-Lite specification generation from backend to frontend for multiple-run endpoints
  - Multiple-run backend APIs now return raw data rows instead of Vega-Lite specs
  - Frontend creates Vega-Lite specifications locally for better customization
  - Added support for multiple runs data merging in plots
  - Implemented automatic data refresh when switching to Plots tab
  - Removed unused single-run plot endpoints (`/api/runs/{run_id}/plots/*`) to simplify API surface

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
