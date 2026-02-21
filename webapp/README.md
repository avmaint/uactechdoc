# UAC Tech Documentation Web Application

This repository contains technical documentation for UAC systems, including an interactive web application designed to query asset and cable data, and visualize connectivity diagrams.

## Web Application Overview

The web application provides a user-friendly interface to explore the UAC's technical inventory and cabling information. It allows users to:

-   Search for assets by various criteria (Asset Tag, Manufacturer, Model).
-   Filter cable connections based on a target asset, direction (in-bound, out-bound, or both), and cable type.
-   View filtered asset and cable data in tabular format.
-   Visualize connectivity diagrams dynamically generated from the cable data.

## Installation and Setup

To set up and run the web application, follow these steps:

1.  **Clone the Repository (if you haven't already):** \`\`\`bash git clone https://github.com/your-username/uactechdoc.git cd uactechdoc \`\`\` *(Note: Replace `https://github.com/your-username/uactechdoc.git` with the actual repository URL)*

2.  **Navigate to the Web Application Directory:** \`\`\`bash cd webapp \`\`\`

3.  **Create and Activate a Python Virtual Environment:** It's recommended to use a virtual environment to manage project dependencies. \`\`\`bash python3 -m venv .venv source .venv/bin/activate \`\`\`

4.  **Install Backend Dependencies:** \`\`\`bash pip install -r backend/requirements.txt \`\`\`

5.  **Ensure Data Files are Present:** The application relies on `uac_assets.xlsx` and `uac_cables.xlsx` located in the `data/` directory of the main project. A symbolic link to this directory should exist inside the `webapp` directory. If it doesn't, you can create it: \`\`\`bash \# From within the 'webapp' directory: ln -s ../data data \`\`\`

## Running the Application

1.  **Serve both sides (recommended):** From the `webapp` directory run `./run.sh serve`. This launches `python3 -m http.server 8000` for the frontend and `uvicorn` for the backend. Use `Ctrl+C` to stop both processes.

    *Manual alternative:* start the backend with `../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 9000`, then open `frontend/index.html` directly (or run `python3 -m http.server 8000` inside `frontend`).

2.  **Open the Frontend Application:** Visit `http://localhost:8000` when using `run.sh serve`, or open `frontend/index.html` directly in your browser.

## User Instructions

Once the frontend is open:

-   **Asset Search**: Use the input fields under "Asset Search" to filter assets by `Asset Tag`, `Manufacturer`, or `Model`. Click "Search Assets" to view the results in the "Asset Results" tab. The column headers in the asset table are sortable.
-   **Cable and Diagram Viewer**:
    -   Enter a `Target Asset Tag` (e.g., `2507-0700` from `SystemDesignVideo.qmd`).
    -   Select the `Direction` (`Both`, `In-bound`, or `Out-bound`).
    -   Optionally, enter a `Cable Type` (e.g., `SDI`).
    -   Click "View Diagram & Cables".
    -   The "Cable Results" tab will display a table of filtered cables. The column headers in the cable table are sortable.
    -   The "Diagram" tab renders the connectivity diagram. Right-click any node to hide it or to expand additional in-bound/out-bound connections; both the diagram and cable table update automatically.
-   **Diagram Options**:
    -   Use the **Node Label Fields** multi-select to choose which asset fields appear inside each node. The list includes every available asset column with the defaults (Tag, Manufacturer, Model, Usage) pinned at the top and the rest sorted alphabetically.
    -   Use the **Cable Label Fields** multi-select to pick which cable attributes (Tag, Type, In-Port → Out-Port, Usage, plus any additional columns) appear on each connection.
    -   Changes to either multi-select immediately refresh the cable table and diagram so you can see the updated labels without re-clicking *View Diagram & Cables*.

### API Base Configuration

By default the frontend calls the backend at the same origin/port. To override this (e.g., when loading `index.html` from disk), append `?apiBase=http://backend-host:9000` to the page URL or edit the `<meta name="api-base-url" ...>` tag in `frontend/index.html`.

### Manual Tests

Run `./run.sh test` (or `.venv/bin/python tests/run_tests.py`) to execute the backend regression suite. The script prints `[PASS]/[FAIL]` for each case and exits non-zero if any test fails.

## Contributing

*(Optional: Add information about how others can contribute to your project.)*
