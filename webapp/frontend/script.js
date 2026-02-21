const API_BASE_URL = (() => {
    const searchParams = new URLSearchParams(window.location.search);
    const paramValue = searchParams.get("apiBase") || searchParams.get("api");
    if (paramValue) return paramValue.replace(/\/$/, "");
    const meta = document.querySelector('meta[name="api-base-url"]');
    if (meta && meta.content) return meta.content.replace(/\/$/, "");
    if (window.API_BASE_URL) return String(window.API_BASE_URL).replace(/\/$/, "");
    if (window.location.origin && window.location.origin.startsWith("http")) {
        return window.location.origin.replace(/\/$/, "");
    }
    return "http://localhost:9000";
})();

const DEFAULT_NODE_FIELDS = ["tag", "manufacturer", "model", "usage"];
const DEFAULT_EDGE_FIELDS = ["tag", "type", "ports", "usage"];
const FALLBACK_FIELD_LABELS = {
    tag: "Tag",
    manufacturer: "Manufacturer",
    model: "Model",
    usage: "Usage",
    type: "Type",
    ports: "In-Port → Out-Port"
};
let nodeFieldDefaults = [...DEFAULT_NODE_FIELDS];
let edgeFieldDefaults = [...DEFAULT_EDGE_FIELDS];

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
const hiddenNodes = new Set();
const allKnownDiagramAssetTags = new Set();
const adjacencyOutMap = new Map();
const adjacencyInMap = new Map();
const expansionResultLog = new Map(); // node+direction -> includesNewNodes boolean
// Records each hidden node's neighbors (both in and out) at the moment it was
// hidden, while the adjacency maps are still complete. This is the only reliable
// source for re-exposing hidden nodes, because subsequent fetches may drop a
// hidden node's cables from the adjacency maps entirely.
const hiddenNodeNeighbors = new Map(); // hiddenTag -> Set of neighbor tags

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
    const diagramStatus = document.getElementById("diagramStatus");
    const nodeFieldsSelect = document.getElementById("nodeFieldsSelect");
    const edgeFieldsSelect = document.getElementById("edgeFieldsSelect");

    initializeDiagramFieldSelects();

    const handleFieldSelectChange = () => {
        if (!currentFilters.targetTag) {
            return;
        }
        fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType
        ).catch(error => {
            console.error("Error refreshing diagram after field change:", error);
        });
    };

    if (nodeFieldsSelect) {
        nodeFieldsSelect.addEventListener("change", handleFieldSelectChange);
    }
    if (edgeFieldsSelect) {
        edgeFieldsSelect.addEventListener("change", handleFieldSelectChange);
    }

    let baseTargetTag = "";
    let contextMenuTargetTag = null;
    let currentFilters = { targetTag: "", direction: "both", cableType: "" };
    const nodeExpansionMap = new Map(); // tag -> Set('in','out')


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
        hiddenNodeNeighbors.clear();
        allKnownDiagramAssetTags.clear();
        expansionResultLog.clear();
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
    async function fetchAndRenderDiagramAndCables(targetTag, direction, cableType, resetActiveAssets = false, forceIncludeTags = new Set()) {
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
        const selectedNodeFields = getSelectedOptions(nodeFieldsSelect, nodeFieldDefaults);
        const selectedEdgeFields = getSelectedOptions(edgeFieldsSelect, edgeFieldDefaults);

        // --- Fetch Cable Data (also used to derive node list) ---
        const cableParams = new URLSearchParams();
        cableParams.append("target_tag", targetTag);
        cableParams.append("direction", direction);
        if (cableType) cableParams.append("cable_type", cableType);
        cableParams.append("node_fields", selectedNodeFields.join(','));
        cableParams.append("edge_fields", selectedEdgeFields.join(','));

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
                setDiagramStatus(`Error loading cables: ${message}`, "error");
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
            const errMsg = `Error loading cable data: ${error.message}`;
            cableTableContainer.innerHTML = `<p style="color: red;">${errMsg}</p>`;
            diagramRenderArea.innerHTML = `<p style="color: red;">${errMsg}</p>`;
            setDiagramStatus(errMsg, "error");
            return { availableChanged: false }; // Exit if cable data fetch fails
        }

        // Rebuild adjacency maps for neighbor lookups.
        adjacencyOutMap.clear();
        adjacencyInMap.clear();
        cableData.forEach(cable => {
            const src = cable.SrcTag ? cable.SrcTag.trim() : "";
            const dst = cable.DstTag ? cable.DstTag.trim() : "";
            if (!src || !dst) return;
            if (!adjacencyOutMap.has(src)) adjacencyOutMap.set(src, new Set());
            if (!adjacencyInMap.has(dst)) adjacencyInMap.set(dst, new Set());
            adjacencyOutMap.get(src).add(dst);
            adjacencyInMap.get(dst).add(src);
        });

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

        // Ensure any explicitly-unhidden nodes are always discoverable,
        // even if the backend didn't return their cables this fetch.
        forceIncludeTags.forEach(tag => { if (tag) discoveredAssetTags.add(tag); });

        const sortedDiscoveredTags = Array.from(discoveredAssetTags).filter(Boolean).sort();
        const newlyDiscovered = [];
        sortedDiscoveredTags.forEach(tag => {
            if (!allKnownDiagramAssetTags.has(tag)) {
                allKnownDiagramAssetTags.add(tag);
                newlyDiscovered.push(tag);
            }
        });
        availableDiagramAssetTags = [...sortedDiscoveredTags];

        if (resetActiveAssets) {
            hiddenNodes.clear();
            allKnownDiagramAssetTags.clear();
            expansionResultLog.clear();
        }
        hiddenNodes.delete(baseTargetTag);

        newlyDiscovered.forEach(tag => hiddenNodes.delete(tag));
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
        dotParams.append("node_fields", selectedNodeFields.join(','));
        dotParams.append("edge_fields", selectedEdgeFields.join(','));
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
                setDiagramStatus(message, "error");
                return { availableChanged: false };
            }
            svgText = await svgResponse.text(); // Get response as text

            // Inject the SVG text directly into the div
            diagramRenderArea.innerHTML = svgText;
            document.querySelector('.tab-button[data-tab="diagramViewer"]').click(); // Switch to diagram tab
            hideContextMenu();
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz SVG:", error);
            const errMsg = `Error loading or rendering diagram: ${error.message}`;
            diagramRenderArea.innerHTML = `<p style="color: red;">${errMsg}</p>`;
            setDiagramStatus(errMsg, "error");
            return { availableChanged: false }; // Exit if SVG fetch fails
        }

        attachNodeContextMenuHandlers();
        const availableChanged = prevAvailableSnapshot.length !== availableDiagramAssetTags.length ||
            prevAvailableSnapshot.some((tag, idx) => tag !== availableDiagramAssetTags[idx]);
        if (availableChanged || newlyDiscovered.length > 0) {
            clearDiagramStatus();
        }
        return { availableChanged, newlyDiscoveredCount: newlyDiscovered.length };
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
        // Snapshot this node's neighbors NOW while adjacency maps are still
        // complete. Once we re-fetch with the node hidden the backend may stop
        // returning its cables, wiping its edges from the adjacency maps.
        // This snapshot is the only reliable record for re-exposing it later.
        const neighbors = new Set();
        const inbound = adjacencyInMap.get(normalizedTag);
        if (inbound) inbound.forEach(n => neighbors.add(n));
        const outbound = adjacencyOutMap.get(normalizedTag);
        if (outbound) outbound.forEach(n => neighbors.add(n));
        hiddenNodeNeighbors.set(normalizedTag, neighbors);

        hiddenNodes.add(normalizedTag);

        await fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType
        );
        clearDiagramStatus();
    }

    async function handleAddConnections(tag, direction) {
        if (!currentFilters.targetTag) return;
        if (!tag) return;
        const normalizedTag = tag.trim();
        if (!normalizedTag) return;
        const wasHidden = hiddenNodes.delete(normalizedTag);
        const neighborsToUnhide = new Set();

        // Forward lookup: live adjacency maps for current visible neighbours
        if (direction === 'both' || direction === 'in') {
            const inboundNeighbors = adjacencyInMap.get(normalizedTag);
            if (inboundNeighbors) inboundNeighbors.forEach(n => neighborsToUnhide.add(n));
        }
        if (direction === 'both' || direction === 'out') {
            const outboundNeighbors = adjacencyOutMap.get(normalizedTag);
            if (outboundNeighbors) outboundNeighbors.forEach(n => neighborsToUnhide.add(n));
        }

        // Reverse lookup via snapshot: find any hidden node that listed the
        // clicked node as a neighbour when it was hidden. This is the fix —
        // after hiding, the backend drops the node's cables from subsequent
        // responses so the live adjacency maps no longer contain its edges.
        // The snapshot recorded at hide-time is the only reliable data source.
        hiddenNodeNeighbors.forEach((neighborSet, hiddenTag) => {
            if (neighborSet.has(normalizedTag)) {
                neighborsToUnhide.add(hiddenTag);
            }
        });

        neighborsToUnhide.forEach(n => {
            hiddenNodes.delete(n);
            hiddenNodeNeighbors.delete(n); // clean up snapshot once unhidden
        });
        const nodesToReactivate = new Set([normalizedTag, ...neighborsToUnhide]);
        nodesToReactivate.add(baseTargetTag);
        nodesToReactivate.forEach(tagValue => {
            if (!tagValue) return;
            if (!activeDiagramAssetTags.includes(tagValue)) {
                activeDiagramAssetTags.push(tagValue);
            }
        });

        const updated = addExpansionDirection(normalizedTag, direction);
        // Pass the freshly-unhidden nodes as forceIncludeTags so they are
        // guaranteed to appear in sortedDiscoveredTags and reach activeDiagramAssetTags,
        // even if the backend doesn't return their cables in this specific fetch.
        const forceInclude = new Set([normalizedTag, ...neighborsToUnhide]);
        const result = await fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType,
            false,
            forceInclude
        );
        const discovered = result?.newlyDiscoveredCount || 0;
        const key = `${normalizedTag}::${direction}`;
        const hasNewBefore = expansionResultLog.get(key) || false;
        if (!updated && !wasHidden && discovered === 0 && !hasNewBefore) {
            setDiagramStatus(`No additional ${direction === 'in' ? 'in-bound' : 'out-bound'} connections were found for ${normalizedTag}.`, "warn");
        } else {
            clearDiagramStatus();
            if (discovered > 0) {
                expansionResultLog.set(key, true);
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

    function setDiagramStatus(message, level = "info") {
        if (!diagramStatus) return;
        if (!message) {
            diagramStatus.textContent = "";
            diagramStatus.className = "status-message hidden";
            return;
        }
        const levelClass = {
            info: "status-info",
            success: "status-success",
            warn: "status-warn",
            error: "status-error"
        }[level] || "status-info";
        diagramStatus.className = `status-message ${levelClass}`;
        diagramStatus.textContent = message;
    }

    function clearDiagramStatus() {
        setDiagramStatus("");
    }

    async function initializeDiagramFieldSelects() {
        if (!nodeFieldsSelect || !edgeFieldsSelect) {
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/diagram/options`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const payload = await response.json();
            const nodePayload = payload?.node || {};
            const edgePayload = payload?.edge || {};

            nodeFieldDefaults = Array.isArray(nodePayload.defaults) && nodePayload.defaults.length
                ? [...nodePayload.defaults]
                : [...DEFAULT_NODE_FIELDS];
            edgeFieldDefaults = Array.isArray(edgePayload.defaults) && edgePayload.defaults.length
                ? [...edgePayload.defaults]
                : [...DEFAULT_EDGE_FIELDS];

            const nodeOptions = Array.isArray(nodePayload.options) && nodePayload.options.length
                ? nodePayload.options
                : buildFallbackOptions(nodeFieldDefaults);
            const edgeOptions = Array.isArray(edgePayload.options) && edgePayload.options.length
                ? edgePayload.options
                : buildFallbackOptions(edgeFieldDefaults);

            populateFieldSelect(nodeFieldsSelect, nodeOptions, nodeFieldDefaults);
            populateFieldSelect(edgeFieldsSelect, edgeOptions, edgeFieldDefaults);
        } catch (error) {
            console.error("Error loading diagram field options:", error);
            populateFieldSelect(nodeFieldsSelect, buildFallbackOptions(nodeFieldDefaults), nodeFieldDefaults);
            populateFieldSelect(edgeFieldsSelect, buildFallbackOptions(edgeFieldDefaults), edgeFieldDefaults);
        }
    }

    function populateFieldSelect(selectElement, options, defaults) {
        if (!selectElement) {
            return;
        }
        selectElement.innerHTML = "";
        const seen = new Set();
        options.forEach(option => {
            if (!option || !option.value || seen.has(option.value)) {
                return;
            }
            const opt = document.createElement("option");
            opt.value = option.value;
            opt.textContent = option.label || humanizeFieldLabel(option.value);
            opt.selected = option.selected ?? defaults.includes(option.value);
            selectElement.appendChild(opt);
            seen.add(option.value);
        });
        // Ensure all defaults exist even if backend omitted them for some reason
        defaults.forEach(value => {
            if (seen.has(value)) {
                return;
            }
            const opt = document.createElement("option");
            opt.value = value;
            opt.textContent = humanizeFieldLabel(value);
            opt.selected = true;
            selectElement.appendChild(opt);
            seen.add(value);
        });
    }

    function buildFallbackOptions(fields) {
        return fields.map(value => ({
            value,
            label: humanizeFieldLabel(value),
            selected: true
        }));
    }

    function humanizeFieldLabel(value) {
        if (!value) return "";
        if (FALLBACK_FIELD_LABELS[value]) {
            return FALLBACK_FIELD_LABELS[value];
        }
        const spaced = value.replace(/_/g, " ").replace(/\s+/g, " ").trim();
        return spaced.split(" ").map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
    }

    function getSelectedOptions(selectElement, fallback = []) {
        if (!selectElement) return [...fallback];
        const values = Array.from(selectElement.selectedOptions).map(opt => opt.value);
        return values.length ? values : [...fallback];
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
