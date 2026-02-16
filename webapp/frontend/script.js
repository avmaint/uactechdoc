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
let availableDiagramAssetTags = [];

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
    const reloadDataBtn = document.getElementById("reloadDataBtn");
    const reloadStatus = document.getElementById("reloadStatus");
    const cableTableContainer = document.getElementById("cableTableContainer");
    const diagramRenderArea = document.getElementById("diagramRenderArea");
    const assetFilterCheckboxesDiv = document.getElementById("assetFilterCheckboxes");
    const additionalAssetsInput = document.getElementById("additionalAssetsInput"); // New
    const additionalAssetsErrorDiv = document.getElementById("additionalAssetsError"); // New


    viewDiagramBtn.addEventListener("click", async () => {
        console.log("View Diagram & Cables button clicked."); // Added log
        const targetTag = targetTagFilter.value.trim();
        targetTagFilter.value = targetTag;
        console.log("Target Tag value:", targetTag); // Added log
        if (!targetTag) {
            alert("Please enter a Target Asset Tag.");
            return;
        }

        additionalAssetsErrorDiv.textContent = ''; // Clear previous errors
        const additionalAssetsValue = additionalAssetsInput.value;
        await fetchAndRenderDiagramAndCables(
            targetTag,
            directionFilter.value,
            cableTypeFilter.value,
            additionalAssetsValue,
            true // reset active assets on a fresh request
        );
    });

    // Event listener for additionalAssetsInput
    additionalAssetsInput.addEventListener('change', async () => {
        additionalAssetsErrorDiv.textContent = ''; // Clear previous errors
        const targetTag = targetTagFilter.value.trim(); // Use current target tag
        const additionalAssetsValue = additionalAssetsInput.value;

        if (targetTag) {
            await fetchAndRenderDiagramAndCables(
                targetTag,
                directionFilter.value,
                cableTypeFilter.value,
                additionalAssetsValue,
                true // additional asset change should reset the visible set
            );
        }
    });

    // --- Reload Data Button Logic ---
    reloadDataBtn.addEventListener('click', async () => {
        reloadDataBtn.disabled = true;
        reloadStatus.textContent = 'Reloading data...';
        try {
            const response = await fetch(`${API_BASE_URL}/data/reload`, { method: 'POST' });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }
            const payload = await response.json();
            reloadStatus.textContent = `Reloaded ${payload.assets || 0} assets / ${payload.cables || 0} cables`;
        } catch (error) {
            console.error('Error reloading data:', error);
            reloadStatus.textContent = `Reload failed: ${error.message}`;
        } finally {
            reloadDataBtn.disabled = false;
        }
    });


    // Function to fetch and render diagram and cables based on filters and active assets
    async function fetchAndRenderDiagramAndCables(targetTag, direction, cableType, additionalAssets, resetActiveAssets = false) {
        // --- Fetch Cable Data (also used to derive node list) ---
        const cableParams = new URLSearchParams();
        cableParams.append("target_tag", targetTag);
        cableParams.append("direction", direction);
        if (cableType) cableParams.append("cable_type", cableType);

        if (additionalAssets) {
            cableParams.append("additional_asset_tags", additionalAssets);
        }
        let cableData = [];
        let backendAssetTags = [];
        try {
            const cableResponse = await fetch(`${API_BASE_URL}/cables/filter?${cableParams.toString()}`);
            if (!cableResponse.ok) {
                // Check if it's a 400 error from backend validation
                if (cableResponse.status === 400) {
                    const errorData = await cableResponse.json();
                    additionalAssetsErrorDiv.textContent = `Error: ${errorData.detail}`;
                    diagramRenderArea.innerHTML = `<p style="color: red;">${errorData.detail}</p>`;
                    cableTableContainer.innerHTML = `<p style="color: red;">${errorData.detail}</p>`;
                    return; // Stop further processing
                }
                throw new Error(`HTTP error! status: ${cableResponse.status}`);
            }
            const responsePayload = await cableResponse.json();
            if (Array.isArray(responsePayload)) {
                cableData = responsePayload;
            } else if (responsePayload && typeof responsePayload === 'object') {
                cableData = responsePayload.cables || [];
                backendAssetTags = responsePayload.asset_tags || [];
            } else {
                cableData = [];
            }
            renderTable(cableData, cableTableContainer, 'cableResults'); // Pass table ID
        } catch (error) {
            console.error("Error fetching cable data:", error);
            cableTableContainer.innerHTML = `<p style="color: red;">Error loading cable data: ${error.message}</p>`;
            diagramRenderArea.innerHTML = `<p style="color: red;">Error loading cable data for diagram: ${error.message}</p>`;
            return; // Exit if cable data fetch fails
        }

        // Build the available and active asset tag lists based on backend response/cable results.
        const discoveredAssetTags = new Set(backendAssetTags);
        cableData.forEach(cable => {
            if (cable.SrcTag) discoveredAssetTags.add(cable.SrcTag.trim());
            if (cable.DstTag) discoveredAssetTags.add(cable.DstTag.trim());
        });
        if (targetTag) {
            discoveredAssetTags.add(targetTag);
        }
        if (additionalAssets) {
            additionalAssets.split(',').forEach(tag => {
                const trimmed = tag.trim();
                if (trimmed) {
                    discoveredAssetTags.add(trimmed);
                }
            });
        }

        const sortedDiscoveredTags = Array.from(discoveredAssetTags).filter(Boolean).sort();
        availableDiagramAssetTags = [...sortedDiscoveredTags];

        if (resetActiveAssets || activeDiagramAssetTags.length === 0) {
            activeDiagramAssetTags = [...sortedDiscoveredTags];
        } else {
            const discoveredSet = new Set(sortedDiscoveredTags);
            activeDiagramAssetTags = activeDiagramAssetTags.filter(tag => discoveredSet.has(tag));
            if (activeDiagramAssetTags.length === 0) {
                activeDiagramAssetTags = [...sortedDiscoveredTags];
            }
        }

        if (!activeDiagramAssetTags.includes(targetTag)) {
            activeDiagramAssetTags.push(targetTag);
        }
        activeDiagramAssetTags = Array.from(new Set(activeDiagramAssetTags));

        // --- Fetch Graphviz SVG ---
        const dotParams = new URLSearchParams();
        dotParams.append("target_tag", targetTag);
        dotParams.append("direction", direction);
        if (cableType) dotParams.append("cable_type", cableType);
        // Always send visible_asset_tags, it's the source of truth for the graph
        if (activeDiagramAssetTags.length > 0) {
            dotParams.append("visible_asset_tags", activeDiagramAssetTags.join(','));
        }
        if (additionalAssets) {
            dotParams.append("additional_asset_tags", additionalAssets);
        }

        let svgText = "";
        try {
            // Expect SVG text directly from the backend
            const svgResponse = await fetch(`${API_BASE_URL}/graphviz/dot?${dotParams.toString()}`);
            if (!svgResponse.ok) {
                // Check if it's a 400 error from backend validation
                if (svgResponse.status === 400) {
                    const errorData = await svgResponse.json();
                    additionalAssetsErrorDiv.textContent = `Error: ${errorData.detail}`;
                    diagramRenderArea.innerHTML = `<p style="color: red;">${errorData.detail}</p>`;
                    return; // Stop further processing
                }
                throw new Error(`HTTP error! status: ${svgResponse.status}`);
            }
            svgText = await svgResponse.text(); // Get response as text

            // Inject the SVG text directly into the div
            diagramRenderArea.innerHTML = svgText;
            document.querySelector('.tab-button[data-tab="diagramViewer"]').click(); // Switch to diagram tab
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz SVG:", error);
            diagramRenderArea.innerHTML = `<p style="color: red;">Error loading or rendering diagram: ${error.message}</p>`;
            return; // Exit if SVG fetch fails
        }

        generateAssetCheckboxes(availableDiagramAssetTags, targetTag);
    }

    // Function to generate and manage asset checkboxes
    function generateAssetCheckboxes(allAssetTagsInDiagram, currentTargetTag) {
        assetFilterCheckboxesDiv.innerHTML = '<h4>Filter Assets:</h4>';
        assetFilterCheckboxesDiv.style.display = 'grid'; // Display as grid
        assetFilterCheckboxesDiv.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))'; // Responsive columns
        assetFilterCheckboxesDiv.style.gap = '10px';

        allAssetTagsInDiagram.forEach(tag => {
            const div = document.createElement('div');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `asset-${tag}`;
            checkbox.value = tag;
            checkbox.dataset.assetTag = tag;
            
            // If the tag is in the current activeDiagramAssetTags, it should be checked
            checkbox.checked = activeDiagramAssetTags.includes(tag);

            // The target tag should always be visible and its checkbox disabled
            if (tag === currentTargetTag) {
                checkbox.checked = true;
                checkbox.disabled = true;
            }

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
                await fetchAndRenderDiagramAndCables(targetTagFilter.value, directionFilter.value, cableTypeFilter.value, additionalAssetsInput.value);
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
