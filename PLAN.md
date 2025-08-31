# binderdash

This will be a 'dashboard' application for viewing the results of _de novo_ protein binder design runs,
using tables, plots and and a Molstar viewer.

## Technologies

- uv (https://docs.astral.sh/uv/)
- pnpm (https://pnpm.io/)
- Vite (https://vitejs.dev/)
- Vue.js 3 (using the composition API) https://vuejs.org/guide/essentials/application.html
- PrimeVue (https://primevue.org/)
- FastAPI (https://fastapi.tiangolo.com/)
- Molstar (https://molstar.org/)
- Vega-Lite (https://vega.github.io/vega-lite/) and Altair (https://altair-viz.github.io/)
- .env files
- Docker Compose

## Prototypes

Prototype apps have been written in Streamlit - we want to translate these in to a single application using the technologies listed above.

- [rfd.py](prototypes/rfd.py)
- [bindcraft.py](prototypes/bindcraft.py)

## Application design

The application will run as a single page application, serving data to the frontend via FastAPI. FastAPI should also server the static files for the frontend.

The initial version should replicate the table, molstar viewer and plot functionality of the prototypes.
Use tab views as in the prototypes (on tab for table + molstar, one tab for plots, one tab for the path selection tree (below)).

The app should have a TreeTable component that acts as a file browser for selecting multiple paths.
The `.env` file will define a list of `RUN_BASE_DIRS=["/data/runs", "/data2/runs/"]` - these will be the base directories for the file browser. We will only show folders, not files. Folders can be selected using a checkbox (https://primevue.org/treetable/#checkbox_row_selection). We will have a function that recursively scans the selected directories and determines if they contain a denovo binder design run (following rules in `rfd.py` and `bindcraft.py`, which may be refined or expanded). When we find a valid directory, we don't search for any 'nested' runs inside that directory (as in the prototypes). From scanning the selected folders, we will produce a data structure with list of run directories, the path to each results table (eg 'bindcraft_summary.tsv' or 'combined_scores.tsv') and a list of PDB files (and other files) associated with the run (eg 'pdbs' directory).

## Extra features

These features should be added after the initial version is working. Be sure to anticipate that they will be added, so the architecture is designed to support them.

- *Authentication*: The app should use Google Authentication for access. Only authenticated users should be able to view the app.
Allowed users will be listed by email address in the `.env` file as a comma-separated list of email addresses (`ALLOWED_USERS=["user1@example.com", "user2@example.com", ...]`). Also allow simple username/password authentication in `LOCAL_USERS=["user1:encryptedpassword1", "user2:encryptedpassword2", ...]` (where passwords are encrypted using `bcrypt` or similar).

- *Caching*: We will add a simple in-memory caching layer to the backend API to cache the scan results.
- 
- *Database* (postgres): We don't initially need a database, but consider that the app will likely evolve to use folder scans to populate the database with run information, and data will be served from there rather than re-scanning the filesystem. The database schema will organize runs by project+run where each run will have a set of PDB struture files, tabular result data and associated metadata like run settings.