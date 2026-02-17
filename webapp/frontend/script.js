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
    const nodeContextMenu = document.getElementById("nodeContextMenu");

    let baseTargetTag = "";
    let contextMenuTargetTag = null;
    let currentFilters = { targetTag: "", direction: "both", cableType: "" };
    const nodeExpansionMap = new Map(); // tag -> Set('in','out')
    const hiddenNodes = new Set();


    viewDiagramBtn.addEventListener("click", async () => {
        console.log("View Diagram & Cables button clicked."); // Added log
        const targetTag = targetTagFilter.value.trim();
        targetTagFilter.value = targetTag;
        console.log("Target Tag value:", targetTag); // Added log
        if (!targetTag) {
            alert("Please enter a Target Asset Tag.");
            return;
        }

        baseTargetTag = targetTag;
        hiddenNodes.clear();
        currentFilters = {
            targetTag,
            direction: directionFilter.value,
            cableType: cableTypeFilter.value
        };
        initializeExpansionMap(baseTargetTag, currentFilters.direction);
        await fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType,
            true // reset active assets on a fresh request
        );
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


    document.addEventListener('click', () => hideContextMenu());

    nodeContextMenu.addEventListener('click', async (event) => {
        const action = event.target.dataset.action;
        const targetTag = contextMenuTargetTag;
        if (!action || !targetTag) {
            return;
        }
        event.stopPropagation();
        hideContextMenu();
        if (action === 'hide') {
            await handleHideNode(targetTag);
        } else if (action === 'add-in') {
            await handleAddConnections(targetTag, 'in');
        } else if (action === 'add-out') {
            await handleAddConnections(targetTag, 'out');
        }
    });


    // Function to fetch and render diagram and cables based on filters and active assets
    async function fetchAndRenderDiagramAndCables(targetTag, direction, cableType, resetActiveAssets = false) {
        const prevAvailableSnapshot = [...availableDiagramAssetTags];
        const expansionEntries = Array.from(nodeExpansionMap.entries());
        const additionalAssetsList = expansionEntries
            .map(([tag]) => tag)
            .filter(tag => tag !== baseTargetTag);
        const additionalAssets = additionalAssetsList.join(',');
        const expansionParam = expansionEntries
            .map(([tag, dirSet]) => {
                const hasIn = dirSet.has('in');
                const hasOut = dirSet.has('out');
                let dirValue = 'both';
                if (hasIn && !hasOut) dirValue = 'in';
                else if (!hasIn && hasOut) dirValue = 'out';
                return `${tag}:${dirValue}`;
            })
            .join(';');

        // --- Fetch Cable Data (also used to derive node list) ---
        const cableParams = new URLSearchParams();
        cableParams.append("target_tag", targetTag);
        cableParams.append("direction", direction);
        if (cableType) cableParams.append("cable_type", cableType);

        if (additionalAssets) {
            cableParams.append("additional_asset_tags", additionalAssets);
        }
        if (expansionParam) {
            cableParams.append("expansions", expansionParam);
        }
        let cableData = [];
        let backendAssetTags = [];
        try {
            const cableResponse = await fetch(`${API_BASE_URL}/cables/filter?${cableParams.toString()}`);
            if (!cableResponse.ok) {
                const errorData = await cableResponse.json().catch(() => ({}));
                const message = errorData.detail || `HTTP error! status: ${cableResponse.status}`;
                diagramRenderArea.innerHTML = `<p style="color: red;">${message}</p>`;
                cableTableContainer.innerHTML = `<p style="color: red;">${message}</p>`;
                return { availableChanged: false }; // Stop further processing
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
            return { availableChanged: false }; // Exit if cable data fetch fails
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
        additionalAssetsList.forEach(tag => {
            if (tag) {
                discoveredAssetTags.add(tag);
            }
        });

        const sortedDiscoveredTags = Array.from(discoveredAssetTags).filter(Boolean).sort();
        availableDiagramAssetTags = [...sortedDiscoveredTags];

        if (resetActiveAssets) {
            hiddenNodes.clear();
        }
        hiddenNodes.delete(baseTargetTag);

        activeDiagramAssetTags = sortedDiscoveredTags.filter(tag => !hiddenNodes.has(tag));
        if (!activeDiagramAssetTags.includes(baseTargetTag) && sortedDiscoveredTags.includes(baseTargetTag)) {
            activeDiagramAssetTags.push(baseTargetTag);
        }
        if (activeDiagramAssetTags.length === 0 && sortedDiscoveredTags.length > 0) {
            activeDiagramAssetTags = [...sortedDiscoveredTags];
        }

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
        if (expansionParam) {
            dotParams.append("expansions", expansionParam);
        }

        let svgText = "";
        try {
            // Expect SVG text directly from the backend
            const svgResponse = await fetch(`${API_BASE_URL}/graphviz/dot?${dotParams.toString()}`);
            if (!svgResponse.ok) {
                const errorData = await svgResponse.json().catch(() => ({}));
                const message = errorData.detail || `HTTP error! status: ${svgResponse.status}`;
                diagramRenderArea.innerHTML = `<p style="color: red;">${message}</p>`;
                return { availableChanged: false };
            }
            svgText = await svgResponse.text(); // Get response as text

            // Inject the SVG text directly into the div
            diagramRenderArea.innerHTML = svgText;
            document.querySelector('.tab-button[data-tab="diagramViewer"]').click(); // Switch to diagram tab
            hideContextMenu();
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz SVG:", error);
            diagramRenderArea.innerHTML = `<p style="color: red;">Error loading or rendering diagram: ${error.message}</p>`;
            return { availableChanged: false }; // Exit if SVG fetch fails
        }

        attachNodeContextMenuHandlers();
        const availableChanged = prevAvailableSnapshot.length !== availableDiagramAssetTags.length ||
            prevAvailableSnapshot.some((tag, idx) => tag !== availableDiagramAssetTags[idx]);
        return { availableChanged };
    }
    function attachNodeContextMenuHandlers() {
        const svgNodes = diagramRenderArea.querySelectorAll('g.node');
        svgNodes.forEach(node => {
            const titleEl = node.querySelector('title');
            if (!titleEl || !titleEl.textContent) return;
            const tag = titleEl.textContent.trim();
            if (!tag) return;
            node.addEventListener('contextmenu', (event) => {
                event.preventDefault();
                showContextMenu(tag, event.clientX, event.clientY);
            });
        });
    }

    function showContextMenu(tag, clientX, clientY) {
        contextMenuTargetTag = tag;
        nodeContextMenu.style.display = 'flex';
        const { offsetWidth, offsetHeight } = nodeContextMenu;
        let left = clientX;
        let top = clientY;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        if (left + offsetWidth > viewportWidth) {
            left = viewportWidth - offsetWidth - 10;
        }
        if (top + offsetHeight > viewportHeight) {
            top = viewportHeight - offsetHeight - 10;
        }
        left = Math.max(10, left);
        top = Math.max(10, top);
        nodeContextMenu.style.left = `${left}px`;
        nodeContextMenu.style.top = `${top}px`;
    }

    function hideContextMenu() {
        nodeContextMenu.style.display = 'none';
        contextMenuTargetTag = null;
    }

    async function handleHideNode(tag) {
        if (!currentFilters.targetTag) return;
        const normalizedTag = tag.trim();
        if (normalizedTag === baseTargetTag) {
            alert("Cannot hide the primary target asset.");
            return;
        }
        hiddenNodes.add(normalizedTag);
        nodeExpansionMap.delete(normalizedTag);
        await fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType
        );
    }

    async function handleAddConnections(tag, direction) {
        if (!currentFilters.targetTag) return;
        if (!tag) return;
        const normalizedTag = tag.trim();
        if (!normalizedTag) return;
        hiddenNodes.delete(normalizedTag);
        const updated = addExpansionDirection(normalizedTag, direction);
        if (updated) {
            const result = await fetchAndRenderDiagramAndCables(
                currentFilters.targetTag,
                currentFilters.direction,
                currentFilters.cableType
            );
            if (!result.availableChanged) {
                alert(`No additional ${direction === 'in' ? 'in-bound' : direction === 'out' ? 'out-bound' : ''} connections were found for ${normalizedTag}.`);
            }
        }
    }

    function initializeExpansionMap(targetTag, direction) {
        nodeExpansionMap.clear();
        addExpansionDirection(targetTag, direction);
    }

    function addExpansionDirection(tag, direction) {
        const normalizedTag = tag ? tag.trim() : "";
        if (!normalizedTag) return false;
        if (!nodeExpansionMap.has(normalizedTag)) {
            nodeExpansionMap.set(normalizedTag, new Set());
        }
        const dirSet = nodeExpansionMap.get(normalizedTag);
        const prevSize = dirSet.size;
        if (direction === 'both') {
            dirSet.add('in');
            dirSet.add('out');
        } else if (direction === 'in') {
            dirSet.add('in');
        } else if (direction === 'out') {
            dirSet.add('out');
        } else {
            dirSet.add('in');
            dirSet.add('out');
        }
        return dirSet.size !== prevSize;
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
