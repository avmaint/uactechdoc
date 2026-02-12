# UAC Tech Documentation Web Application

This repository contains technical documentation for UAC systems, including an interactive web application designed to query asset and cable data, and visualize connectivity diagrams.

## Web Application Overview

The web application provides a user-friendly interface to explore the UAC's technical inventory and cabling information. It allows users to:

*   Search for assets by various criteria (Asset Tag, Manufacturer, Model).
*   Filter cable connections based on a target asset, direction (in-bound, out-bound, or both), and cable type.
*   View filtered asset and cable data in tabular format.
*   Visualize connectivity diagrams dynamically generated from the cable data.

## Installation and Setup

To set up and run the web application, follow these steps:

1.  **Clone the Repository (if you haven't already):**
    \`\`\`bash
    git clone https://github.com/your-username/uactechdoc.git
    cd uactechdoc
    \`\`\`
    *(Note: Replace `https://github.com/your-username/uactechdoc.git` with the actual repository URL)*

2.  **Navigate to the Web Application Directory:**
    \`\`\`bash
    cd webapp
    \`\`\`

3.  **Create and Activate a Python Virtual Environment:**
    It's recommended to use a virtual environment to manage project dependencies.
    \`\`\`bash
    python3 -m venv .venv
    source .venv/bin/activate
    \`\`\`

4.  **Install Backend Dependencies:**
    \`\`\`bash
    pip install -r backend/requirements.txt
    \`\`\`

5.  **Ensure Data Files are Present:**
    The application relies on `uac_assets.xlsx` and `uac_cables.xlsx` located in the `data/` directory of the main project. A symbolic link to this directory should exist inside the `webapp` directory. If it doesn't, you can create it:
    \`\`\`bash
    # From within the 'webapp' directory:
    ln -s ../data data
    \`\`\`

## Running the Application

1.  **Start the Backend API:**
    Open your terminal, navigate to the main project directory (`uactechdoc`), then run:
    \`\`\`bash
    cd webapp/backend
    ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 9000
    \`\`\`
    The backend API will start running on `http://0.0.0.0:9000`. Keep this terminal window open as long as you want the backend to be accessible.

2.  **Open the Frontend Application:**
    Open your web browser and navigate to the `index.html` file located in the `webapp/frontend` directory.
    You can do this by:
    *   Directly entering the file path in your browser's address bar:
        \`\`\`
        file:///path/to/your/uactechdoc/webapp/frontend/index.html
        \`\`\`
        (Replace `/path/to/your/uactechdoc` with the actual path to your cloned repository.)
    *   Dragging and dropping the `webapp/frontend/index.html` file directly into your web browser.

## User Instructions

Once the frontend is open:

*   **Asset Search**: Use the input fields under "Asset Search" to filter assets by `Asset Tag`, `Manufacturer`, or `Model`. Click "Search Assets" to view the results in the "Asset Results" tab.
*   **Cable and Diagram Viewer**:
    *   Enter a `Target Asset Tag` (e.g., `2507-0700` from `SystemDesignVideo.qmd`).
    *   Select the `Direction` (`Both`, `In-bound`, or `Out-bound`).
    *   Optionally, enter a `Cable Type` (e.g., `SDI`).
    *   Click "View Diagram & Cables".
    *   The "Cable Results" tab will display a table of filtered cables.
    *   The "Diagram" tab will show the rendered connectivity diagram directly.

## Contributing

*(Optional: Add information about how others can contribute to your project.)*
