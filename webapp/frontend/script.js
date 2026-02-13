const API_BASE_URL = "http://localhost:9000"; // Assuming backend runs on port 9000

// Store sort state for tables
const tableSortStates = {
    assetResults: {
        column: null,
        direction: 'asc' // 'asc' or 'desc'
    },
    cableResults: {
        column: null,
        direction: 'asc'
    }
};

// Store active asset tags for diagram filtering
let activeDiagramAssetTags = [];
let initialDiagramTargetTag = null; // Store the initial target tag for diagram

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOMContentLoaded event fired."); // Added log
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
            renderTable(data, assetTableContainer, 'assetResults'); // Pass table ID
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
    const diagramRenderArea = document.getElementById("diagramRenderArea");
    const assetFilterCheckboxesDiv = document.getElementById("assetFilterCheckboxes");


    viewDiagramBtn.addEventListener("click", async () => {
        console.log("View Diagram & Cables button clicked."); // Added log
        const targetTag = targetTagFilter.value;
        initialDiagramTargetTag = targetTag; // Store the initial target tag
        console.log("Target Tag value:", targetTag); // Added log
        if (!targetTag) {
            alert("Please enter a Target Asset Tag.");
            return;
        }

        // Always start with all assets visible for a new diagram request
        activeDiagramAssetTags = []; 
        await fetchAndRenderDiagramAndCables(targetTag, directionFilter.value, cableTypeFilter.value);
    });

    // Function to fetch and render diagram and cables based on filters and active assets
    async function fetchAndRenderDiagramAndCables(targetTag, direction, cableType) {
        // --- Fetch Cable Data ---
        const cableParams = new URLSearchParams();
        cableParams.append("target_tag", targetTag);
        cableParams.append("direction", direction);
        if (cableType) cableParams.append("cable_type", cableType);
        if (activeDiagramAssetTags.length > 0) {
            cableParams.append("visible_asset_tags", activeDiagramAssetTags.join(','));
        }

        try {
            const cableResponse = await fetch(`${API_BASE_URL}/cables/filter?${cableParams.toString()}`);
            if (!cableResponse.ok) {
                throw new Error(`HTTP error! status: ${cableResponse.status}`);
            }
            const cableData = await cableResponse.json();
            renderTable(cableData, cableTableContainer, 'cableResults'); // Pass table ID
            // document.querySelector('.tab-button[data-tab="cableResults"]').click(); // Switch to cable results tab
        } catch (error) {
            console.error("Error fetching cable data:", error);
            cableTableContainer.innerHTML = `<p style="color: red;">Error loading cable data: ${error.message}</p>`;
        }

        // --- Fetch Graphviz SVG ---
        const dotParams = new URLSearchParams();
        dotParams.append("target_tag", targetTag);
        dotParams.append("direction", direction);
        if (cableType) dotParams.append("cable_type", cableType);
        if (activeDiagramAssetTags.length > 0) {
            dotParams.append("visible_asset_tags", activeDiagramAssetTags.join(','));
        }

        try {
            // Expect SVG text directly from the backend
            const svgResponse = await fetch(`${API_BASE_URL}/graphviz/dot?${dotParams.toString()}`);
            if (!svgResponse.ok) {
                throw new Error(`HTTP error! status: ${svgResponse.status}`);
            }
            const svgText = await svgResponse.text(); // Get response as text

            // Inject the SVG text directly into the div
            diagramRenderArea.innerHTML = svgText;
            document.querySelector('.tab-button[data-tab="diagramViewer"]').click(); // Switch to diagram tab

            // After initial render, get all asset tags from the SVG to create checkboxes
            // (This is a simplified way; a better way would be to get asset tags from the backend)
            if (activeDiagramAssetTags.length === 0 && initialDiagramTargetTag === targetTag) { // Only generate checkboxes once for initial load
                const parser = new DOMParser();
                const svgDoc = parser.parseFromString(svgText, "image/svg+xml");
                const nodeTitles = svgDoc.querySelectorAll('g.node title'); // Graphviz nodes usually have titles
                
                const allTagsInDiagram = new Set();
                nodeTitles.forEach(title => {
                    const tag = title.textContent.trim();
                    if (tag && tag !== targetTag) { // Exclude the root target tag
                        allTagsInDiagram.add(tag);
                    }
                });
                activeDiagramAssetTags = Array.from(allTagsInDiagram); // Initialize active tags
                generateAssetCheckboxes(activeDiagramAssetTags, targetTag);
            }
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz SVG:", error);
            diagramRenderArea.innerHTML = `<p style="color: red;">Error loading or rendering diagram: ${error.message}</p>`;
        }
    }

    // Function to generate and manage asset checkboxes
    function generateAssetCheckboxes(assetTags, targetTag) {
        assetFilterCheckboxesDiv.innerHTML = '<h4>Filter Assets:</h4>';
        assetFilterCheckboxesDiv.style.display = 'grid'; // Display as grid
        assetFilterCheckboxesDiv.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))'; // Responsive columns
        assetFilterCheckboxesDiv.style.gap = '10px';

        assetTags.sort().forEach(tag => {
            const div = document.createElement('div');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `asset-${tag}`;
            checkbox.value = tag;
            checkbox.checked = true; // All checked by default
            checkbox.dataset.assetTag = tag;

            const label = document.createElement('label');
            label.htmlFor = `asset-${tag}`;
            label.textContent = tag;

            checkbox.addEventListener('change', async () => {
                // Update activeDiagramAssetTags based on checkbox state
                if (checkbox.checked) {
                    if (!activeDiagramAssetTags.includes(tag)) {
                        activeDiagramAssetTags.push(tag);
                    }
                } else {
                    activeDiagramAssetTags = activeDiagramAssetTags.filter(item => item !== tag);
                }
                // Re-fetch and render diagram
                await fetchAndRenderDiagramAndCables(targetTag, directionFilter.value, cableTypeFilter.value);
            });

            div.appendChild(checkbox);
            div.appendChild(label);
            assetFilterCheckboxesDiv.appendChild(div);
        });
    }


    // --- Utility: Render Table ---
    function renderTable(data, container, tableId) { // Added tableId parameter
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
            th.dataset.column = headerText; // Store column name in dataset
            th.classList.add('sortable'); // Add class for styling
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Sort data based on current state
        const currentSortState = tableSortStates[tableId];
        if (currentSortState.column) {
            data.sort((a, b) => {
                const valA = a[currentSortState.column];
                const valB = b[currentSortState.column];
                let comparison = 0;
                if (valA > valB) comparison = 1;
                else if (valA < valB) comparison = -1;
                return currentSortState.direction === 'desc' ? comparison * -1 : comparison;
            });
        }

        // Create table rows (same as before)
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

        // Add event listeners to headers for sorting
        thead.querySelectorAll('th').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                let direction = 'asc';

                if (tableSortStates[tableId].column === column && tableSortStates[tableId].direction === 'asc') {
                    direction = 'desc';
                }

                tableSortStates[tableId] = { column, direction };
                renderTable(data, container, tableId); // Re-render with sorted data
            });
        });
    }
});