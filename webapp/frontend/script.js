const API_BASE_URL = "http://localhost:9000"; // Assuming backend runs on port 9000

document.addEventListener("DOMContentLoaded", () => {
    // --- Tab Switching Logic ---
    const tabButtons = document.querySelectorAll(".tab-button");
    const tabContents = document.querySelectorAll(".tab-content");

    tabButtons.forEach(button => {
        button.addEventListener("click", () => {
            tabButtons.forEach(btn => btn.classList.remove("active"));
            tabContents.forEach(content => content.classList.remove("active"));

            button.classList.add("active");
            document.getElementById(button.dataset.tab).classList.add("active");
        });
    });

    // --- Asset Search Logic ---
    const assetTagSearch = document.getElementById("assetTagSearch");
    const manufacturerSearch = document.getElementById("manufacturerSearch");
    const modelSearch = document.getElementById("modelSearch");
    const searchAssetsBtn = document.getElementById("searchAssetsBtn");
    const assetTableContainer = document.getElementById("assetTableContainer");

    searchAssetsBtn.addEventListener("click", async () => {
        const params = new URLSearchParams();
        if (assetTagSearch.value) params.append("asset_tag", assetTagSearch.value);
        if (manufacturerSearch.value) params.append("manufacturer", manufacturerSearch.value);
        if (modelSearch.value) params.append("model", modelSearch.value);

        try {
            const response = await fetch(`${API_BASE_URL}/assets/search?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            renderTable(data, assetTableContainer);
            document.querySelector('.tab-button[data-tab="assetResults"]').click(); // Switch to asset results tab
        } catch (error) {
            console.error("Error fetching assets:", error);
            assetTableContainer.innerHTML = `<p style="color: red;">Error loading assets: ${error.message}</p>`;
        }
    });

    // --- Cable and Diagram Viewer Logic ---
    const targetTagFilter = document.getElementById("targetTagFilter");
    const directionFilter = document.getElementById("directionFilter");
    const cableTypeFilter = document.getElementById("cableTypeFilter");
    const viewDiagramBtn = document.getElementById("viewDiagramBtn");
    const cableTableContainer = document.getElementById("cableTableContainer");
    // const diagramDotOutput = document.getElementById("diagramDotOutput"); // Removed

    const diagramRenderArea = document.getElementById("diagramRenderArea"); // New
    let graphviz = d3.select("#diagramRenderArea").graphviz()
        .zoom(true) // Enable zooming
        .on("end", () => console.log("Graphviz rendering finished.")); // Optional callback

    viewDiagramBtn.addEventListener("click", async () => {
        const targetTag = targetTagFilter.value;
        if (!targetTag) {
            alert("Please enter a Target Asset Tag.");
            return;
        }

        // Fetch Cable Data
        const cableParams = new URLSearchParams();
        cableParams.append("target_tag", targetTag);
        cableParams.append("direction", directionFilter.value);
        if (cableTypeFilter.value) cableParams.append("cable_type", cableTypeFilter.value);

        try {
            const cableResponse = await fetch(`${API_BASE_URL}/cables/filter?${cableParams.toString()}`);
            if (!cableResponse.ok) {
                throw new Error(`HTTP error! status: ${cableResponse.status}`);
            }
            const cableData = await cableResponse.json();
            renderTable(cableData, cableTableContainer);
            // document.querySelector('.tab-button[data-tab="cableResults"]').click(); // Switch to cable results tab
        } catch (error) {
            console.error("Error fetching cable data:", error);
            cableTableContainer.innerHTML = `<p style="color: red;">Error loading cable data: ${error.message}</p>`;
        }

        // Fetch Graphviz DOT String
        const dotParams = new URLSearchParams();
        dotParams.append("target_tag", targetTag);
        dotParams.append("direction", directionFilter.value);
        if (cableTypeFilter.value) dotParams.append("cable_type", cableTypeFilter.value);

        try {
            const dotResponse = await fetch(`${API_BASE_URL}/graphviz/dot?${dotParams.toString()}`);
            if (!dotResponse.ok) {
                throw new Error(`HTTP error! status: ${dotResponse.status}`);
            }
            const dotJson = await dotResponse.json();
            
            // Render the DOT string using d3-graphviz
            graphviz.renderDot(dotJson.dot_string);
            document.querySelector('.tab-button[data-tab="diagramViewer"]').click(); // Switch to diagram tab
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz DOT string:", error);
            diagramRenderArea.innerHTML = `<p style="color: red;">Error loading or rendering diagram: ${error.message}</p>`;
        }
    });

    // --- Utility: Render Table ---
    function renderTable(data, container) {
        if (!data || data.length === 0) {
            container.innerHTML = "<p>No results found.</p>";
            return;
        }

        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const tbody = document.createElement("tbody");

        // Create table headers
        const headers = Object.keys(data[0]);
        const headerRow = document.createElement("tr");
        headers.forEach(headerText => {
            const th = document.createElement("th");
            th.textContent = headerText;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Create table rows
        data.forEach(rowData => {
            const row = document.createElement("tr");
            headers.forEach(headerText => {
                const td = document.createElement("td");
                td.textContent = rowData[headerText];
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        container.innerHTML = ""; // Clear previous content
        container.appendChild(table);
    }
});
