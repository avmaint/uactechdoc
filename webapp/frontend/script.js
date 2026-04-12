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
const DEFAULT_CROSSPOINT_FIELDS = ["port", "usage"];
const ASSET_TABLE_DEFAULT_COLUMNS = ["AssetTag", "Model", "Manufacturer", "Desc", "Usage"];
const DIAGRAM_INPUT_CONNECTIONS_CONTAINER_ID = "diagramInputConnections";
const DIAGRAM_OUTPUT_CONNECTIONS_CONTAINER_ID = "diagramOutputConnections";

// Asset Details Tab Constants
const ASSET_DETAILS_TAB_ID = "assetDetails";
const ASSET_DETAILS_INPUT_ID = "assetDetailsTagInput";
const ASSET_DETAILS_VIEW_BUTTON_ID = "viewAssetDetailsBtn";
const ASSET_DETAILS_CONTAINER_ID = "assetDetailsContainer";
const ASSET_PROPERTIES_CONTAINER_ID = "assetProperties";
const INPUT_PARTNERS_LIST_ID = "inputPartnersList";
const OUTPUT_PARTNERS_LIST_ID = "outputPartnersList";
const KNOWLEDGE_BASE_ISSUES_TABLE_ID = "knowledgeBaseIssuesTable";

const FALLBACK_FIELD_LABELS = {
    tag: "Tag",
    manufacturer: "Manufacturer",
    model: "Model",
    usage: "Usage",
    type: "Type",
    ports: "In-Port → Out-Port",
    port: "Port",
    protocol: "Protocol",
    notes: "Notes",
    AssetTag: "Asset Tag",
    Desc: "Description",
    TargetPort: "Target Port",
    SourcePort: "Source Port",
    DestinationPort: "Destination Port",
    CableID: "Cable ID",
    PartnerAssetTag: "Partner Asset Tag",
    PartnerManufacturer: "Partner Manufacturer",
    PartnerModel: "Partner Model",
    PartnerUsage: "Partner Usage"
};
let nodeFieldDefaults = [...DEFAULT_NODE_FIELDS];
let edgeFieldDefaults = [...DEFAULT_EDGE_FIELDS];
let crosspointHeaderDefaults = [...DEFAULT_CROSSPOINT_FIELDS];
let assetColumnDefaults = [...ASSET_TABLE_DEFAULT_COLUMNS];
let assetTableData = [];

// Store sort state for tables
const tableSortStates = {
    assetResults: {
        column: null,
        direction: 'asc' // 'asc' or 'desc'
    },
    cableResults: {
        column: null,
        direction: 'asc'
    },
    [DIAGRAM_INPUT_CONNECTIONS_CONTAINER_ID]: {
        column: null,
        direction: 'asc'
    },
    [DIAGRAM_OUTPUT_CONNECTIONS_CONTAINER_ID]: {
        column: null,
        direction: 'asc'
    },
    knowledgeBaseIssuesTable: {
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
const selectedAssetTags = new Set();

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
    const inServiceOnlyCheckbox = document.getElementById("inServiceOnlyCheckbox");
    const assetColumnSelect = document.getElementById("assetColumnSelect");
    const searchAssetsBtn = document.getElementById("searchAssetsBtn");
    const assetTableContainer = document.getElementById("assetTableContainer");

    const performAssetSearch = async () => {
        const params = new URLSearchParams();
        if (assetTagSearch.value) params.append("asset_tag", assetTagSearch.value);
        if (manufacturerSearch.value) params.append("manufacturer", manufacturerSearch.value);
        if (modelSearch.value) params.append("model", modelSearch.value);
        // Add in_service_only parameter based on checkbox state (convert to string)
        const inServiceValue = inServiceOnlyCheckbox ? inServiceOnlyCheckbox.checked : true;
        params.append("in_service_only", inServiceValue.toString());
        console.log("Asset search - in_service_only:", inServiceValue, "URL:", `${API_BASE_URL}/assets/search?${params.toString()}`);

        try {
            const response = await fetch(`${API_BASE_URL}/assets/search?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            assetTableData = Array.isArray(data) ? data : [];
            console.log("Asset search results count:", assetTableData.length);
            renderAssetTable();
            document.querySelector('.tab-button[data-tab="assetResults"]').click(); // Switch to asset results tab
        } catch (error) {
            console.error("Error fetching assets:", error);
            assetTableContainer.innerHTML = `<p style="color: red;">Error loading assets: ${error.message}</p>`;
        }
    };

    searchAssetsBtn.addEventListener("click", performAssetSearch);

    // Add Enter key support for asset search inputs
    [assetTagSearch, manufacturerSearch, modelSearch].forEach(input => {
        input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                performAssetSearch();
            }
        });
    });

    // --- Cable and Diagram Viewer Logic ---
    const targetTagFilter = document.getElementById("targetTagFilter");
    const directionFilter = document.getElementById("directionFilter");
    const cableTypeFilter = document.getElementById("cableTypeFilter");
    const protocolFilter = document.getElementById("protocolFilter");
    const viewDiagramBtn = document.getElementById("viewDiagramBtn");
    const reloadDataBtn = document.getElementById("reloadDataBtn");
    const reloadStatus = document.getElementById("reloadStatus");
    const cableTableContainer = document.getElementById("cableTableContainer");
    const diagramRenderArea = document.getElementById("diagramRenderArea");
    const nodeContextMenu = document.getElementById("nodeContextMenu");
    const diagramStatus = document.getElementById("diagramStatus");
    const nodeFieldsSelect = document.getElementById("nodeFieldsSelect");
    const edgeFieldsSelect = document.getElementById("edgeFieldsSelect");
    const crosspointHeaderFields = document.getElementById("crosspointHeaderFields");
    const crosspointProtocolSelect = document.getElementById("crosspointProtocolSelect");
    const crosspointSourceInput = document.getElementById("crosspointSource");
    const crosspointTargetInput = document.getElementById("crosspointTarget");
    const crosspointSourceSelect = document.getElementById("crosspointSourceSelect");
    const crosspointTargetSelect = document.getElementById("crosspointTargetSelect");
    const viewCrosspointBtn = document.getElementById("viewCrosspointBtn");
    const resetCrosspointBtn = document.getElementById("resetCrosspointBtn");
    const crosspointMatrixContainer = document.getElementById("crosspointMatrixContainer");
    const crosspointStatus = document.getElementById("crosspointStatus");
    const colorNodesCheckbox = document.getElementById("colorNodesByCategory");
    const colorEdgesCheckbox = document.getElementById("colorEdgesByProtocol");
    const collapseStrategySelect = document.getElementById("collapseStrategySelect");

    // Asset Details tab elements
    const assetDetailsTagInput = document.getElementById(ASSET_DETAILS_INPUT_ID);
    const viewAssetDetailsBtn = document.getElementById(ASSET_DETAILS_VIEW_BUTTON_ID);
    const assetPropertiesContainer = document.getElementById(ASSET_PROPERTIES_CONTAINER_ID);
    const inputPartnersList = document.getElementById(INPUT_PARTNERS_LIST_ID);
    const outputPartnersList = document.getElementById(OUTPUT_PARTNERS_LIST_ID);
    const knowledgeBaseIssuesTableContainer = document.getElementById(KNOWLEDGE_BASE_ISSUES_TABLE_ID);

    const performViewAssetDetails = async () => {
        const targetAssetTag = assetDetailsTagInput.value.trim();
        if (!targetAssetTag) {
            alert("Please enter an Asset Tag to view details.");
            return;
        }
        await fetchAndRenderAssetDetails(targetAssetTag);
    };

    viewAssetDetailsBtn.addEventListener("click", performViewAssetDetails);

    // Add Enter key support for asset details input
    if (assetDetailsTagInput) {
        assetDetailsTagInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                performViewAssetDetails();
            }
        });
    }

    // Knowledge Base tab elements
    const kbIssueIdSearch = document.getElementById("kbIssueIdSearch");
    const kbTagSearch = document.getElementById("kbTagSearch");
    const kbFreeformSearch = document.getElementById("kbFreeformSearch");
    const searchKnowledgeBaseBtn = document.getElementById("searchKnowledgeBaseBtn");
    const kbResultsContainer = document.getElementById("kbResultsContainer");

    const performKBSearch = async () => {
        const issueId = kbIssueIdSearch.value.trim();
        const tag = kbTagSearch.value.trim();
        const freeform = kbFreeformSearch.value.trim();

        if (!issueId && !tag && !freeform) {
            alert("Please enter at least one search criterion.");
            return;
        }

        const params = new URLSearchParams();
        if (issueId) params.append("issue_id", issueId);
        if (tag) params.append("tag", tag);
        if (freeform) params.append("freeform", freeform);

        try {
            const response = await fetch(`${API_BASE_URL}/knowledgebase/search?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const issues = await response.json();
            renderKBResults(issues);
        } catch (error) {
            console.error("Error fetching knowledge base results:", error);
            alert(`Failed to fetch knowledge base results: ${error.message}`);
        }
    };

    searchKnowledgeBaseBtn.addEventListener("click", performKBSearch);

    // Add Enter key support for KB search inputs
    [kbIssueIdSearch, kbTagSearch, kbFreeformSearch].forEach(input => {
        if (input) {
            input.addEventListener("keypress", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    performKBSearch();
                }
            });
        }
    });

    function setCrosspointInputValue(side, value) {
        const input = side === "source" ? crosspointSourceInput : crosspointTargetInput;
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (input) {
            input.value = value;
        }
        if (select && !select.classList.contains("hidden")) {
            select.value = value;
        }
    }

    function setCrosspointControlMode(side, mode, optionsList) {
        const input = side === "source" ? crosspointSourceInput : crosspointTargetInput;
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (!input || !select) return;
        if (mode === "select" && (assetTagOptions.length || (optionsList && optionsList.length))) {
            populateAssetSelect(select, side === "source" ? "Select Source Asset" : "Select Target Asset", optionsList);
            const resolved = resolveAssetDisplay(input.value);
            if (resolved) {
                select.value = resolved;
            } else {
                select.value = "";
            }
            input.classList.add("hidden");
            select.classList.remove("hidden");
        } else {
            input.classList.remove("hidden");
            select.classList.add("hidden");
        }
    }

    function resetCrosspointInputs(clearValues = false) {
        setCrosspointControlMode("source", "text");
        setCrosspointControlMode("target", "text");
        if (crosspointSourceSelect) {
            populateAssetSelect(crosspointSourceSelect, "Select Source Asset");
            crosspointSourceSelect.value = "";
        }
        if (crosspointTargetSelect) {
            populateAssetSelect(crosspointTargetSelect, "Select Target Asset");
            crosspointTargetSelect.value = "";
        }
        if (clearValues) {
            if (crosspointSourceInput) crosspointSourceInput.value = "";
            if (crosspointTargetInput) crosspointTargetInput.value = "";
            lastCrosspointQuery = null;
        }
    }

    function getCrosspointValue(side) {
        const input = side === "source" ? crosspointSourceInput : crosspointTargetInput;
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (select && !select.classList.contains("hidden") && select.value) {
            return select.value.trim();
        }
        return input ? input.value.trim() : "";
    }

    function setCrosspointStatus(message, level = "info") {
        if (!crosspointStatus) return;
        if (!message) {
            crosspointStatus.textContent = "";
            crosspointStatus.className = "status-message hidden";
            return;
        }
        const levelClass = {
            info: "status-info",
            success: "status-success",
            warn: "status-warn",
            error: "status-error"
        }[level] || "status-info";
        crosspointStatus.className = `status-message ${levelClass}`;
        crosspointStatus.textContent = message;
    }

    function populateCrosspointProtocolOptions(options, selectedValue) {
        if (!crosspointProtocolSelect) {
            return;
        }
        const fallbackOptions = options && options.length ? options : [{ value: "", label: "All Protocols" }];
        crosspointProtocolSelect.innerHTML = "";
        fallbackOptions.forEach(option => {
            const opt = document.createElement("option");
            opt.value = option.value ?? "";
            opt.textContent = option.label || option.value || "All Protocols";
            crosspointProtocolSelect.appendChild(opt);
        });
        if (selectedValue) {
            crosspointProtocolSelect.value = selectedValue;
        } else {
            crosspointProtocolSelect.selectedIndex = 0;
        }
    }

    function renderCrosspointMatrix(data) {
        if (!crosspointMatrixContainer) {
            return;
        }
        const rows = Array.isArray(data?.rows) ? data.rows : [];
        const columns = Array.isArray(data?.columns) ? data.columns : [];
        const matrix = Array.isArray(data?.matrix) ? data.matrix : [];
        if (!rows.length || !columns.length) {
            crosspointMatrixContainer.innerHTML = "<p>No connections found between the selected assets.</p>";
            return;
        }
        const table = document.createElement("table");
        table.className = "crosspoint-table";
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        const cornerCell = document.createElement("th");
        cornerCell.className = "row-header";
        cornerCell.textContent = `${data?.source_tag || "Source"} → ${data?.target_tag || "Target"}`;
        headerRow.appendChild(cornerCell);
        columns.forEach(col => {
            const th = document.createElement("th");
            th.textContent = col.label || col.port || "";
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach((row, rowIndex) => {
            const tr = document.createElement("tr");
            const rowHeader = document.createElement("td");
            rowHeader.className = "row-header";
            rowHeader.textContent = row.label || row.port || "";
            tr.appendChild(rowHeader);
            columns.forEach((col, colIndex) => {
                const td = document.createElement("td");
                const hasConnection = Boolean(matrix[rowIndex]?.[colIndex]);
                td.className = `crosspoint-cell ${hasConnection ? "has-connection" : "no-connection"}`;
                td.textContent = hasConnection ? "✔" : "";
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        crosspointMatrixContainer.innerHTML = "";
        crosspointMatrixContainer.appendChild(table);
    }

    function normalizeAssetTagValue(value) {
        if (!value) return "";
        return String(value).trim();
    }

    function getSelectedAssetColumns() {
        const columns = getSelectedOptions(assetColumnSelect, assetColumnDefaults);
        const baseColumns = columns.length ? columns : [...assetColumnDefaults];
        const set = new Set(baseColumns);
        set.add("AssetTag");
        return Array.from(set);
    }

    function renderAssetTable() {
        if (!assetTableContainer) return;
        if (!assetTableData || assetTableData.length === 0) {
            assetTableContainer.innerHTML = "<p>No results found.</p>";
            return;
        }

        const columnsToShow = getSelectedAssetColumns();
        const currentSortState = tableSortStates.assetResults;
        const sortedData = [...assetTableData];
        if (currentSortState.column) {
            sortedData.sort((a, b) => {
                const valA = a[currentSortState.column] ?? "";
                const valB = b[currentSortState.column] ?? "";
                let comparison = 0;
                if (valA > valB) comparison = 1;
                else if (valA < valB) comparison = -1;
                return currentSortState.direction === 'desc' ? comparison * -1 : comparison;
            });
        }

        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");

        const selectHeader = document.createElement("th");
        selectHeader.textContent = "Select";
        const selectAllCheckbox = document.createElement("input");
        selectAllCheckbox.type = "checkbox";
        const selectableRows = sortedData.filter(row => normalizeAssetTagValue(row.AssetTag));
        const allVisibleSelected = selectableRows.length > 0 && selectableRows.every(row => selectedAssetTags.has(normalizeAssetTagValue(row.AssetTag)));
        const someVisibleSelected = selectableRows.some(row => selectedAssetTags.has(normalizeAssetTagValue(row.AssetTag)));
        selectAllCheckbox.checked = allVisibleSelected;
        selectAllCheckbox.indeterminate = !allVisibleSelected && someVisibleSelected;
        selectAllCheckbox.addEventListener("change", () => handleSelectAllAssets(selectAllCheckbox.checked, selectableRows));
        selectHeader.appendChild(selectAllCheckbox);
        headerRow.appendChild(selectHeader);

        columnsToShow.forEach(column => {
            const th = document.createElement("th");
            th.textContent = humanizeFieldLabel(column) || column;
            th.dataset.column = column;
            th.classList.add('sortable');
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        sortedData.forEach(rowData => {
            const assetTagValue = normalizeAssetTagValue(rowData.AssetTag);
            const tr = document.createElement("tr");
            const checkboxCell = document.createElement("td");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.disabled = !assetTagValue;
            checkbox.checked = assetTagValue ? selectedAssetTags.has(assetTagValue) : false;
            checkbox.addEventListener("change", () => handleAssetCheckboxChange(assetTagValue, checkbox.checked));
            checkboxCell.appendChild(checkbox);
            tr.appendChild(checkboxCell);

            columnsToShow.forEach(column => {
                const td = document.createElement("td");
                td.textContent = rowData[column] ?? "";

                // Make AssetTag column clickable
                if (column === "AssetTag" && assetTagValue) {
                    td.style.cursor = "pointer";
                    td.style.color = "#0066cc";
                    td.style.textDecoration = "underline";
                    td.addEventListener("click", async () => {
                        // Update both Asset Details and Connectivity Diagram tabs
                        assetDetailsTagInput.value = assetTagValue;
                        targetTagFilter.value = assetTagValue;

                        // Update the diagram state
                        baseTargetTag = assetTagValue;
                        hiddenNodes.clear();
                        hiddenNodeNeighbors.clear();
                        allKnownDiagramAssetTags.clear();
                        expansionResultLog.clear();

                        currentFilters = {
                            targetTag: assetTagValue,
                            cableId: "",
                            direction: directionFilter.value,
                            cableType: cableTypeFilter.value,
                            protocol: protocolFilter ? protocolFilter.value.trim() : ""
                        };

                        initializeExpansionMap(baseTargetTag, currentFilters.direction);

                        // Fetch and render asset details
                        await fetchAndRenderAssetDetails(assetTagValue);

                        // Also update the connectivity diagram in the background
                        await fetchAndRenderDiagramAndCables(
                            currentFilters.targetTag,
                            currentFilters.direction,
                            currentFilters.cableType,
                            currentFilters.protocol,
                            currentFilters.cableId,
                            true // reset active assets on a fresh request
                        );

                        // Switch to Asset Details tab
                        document.querySelector('.tab-button[data-tab="assetDetails"]').click();
                    });
                }

                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        assetTableContainer.innerHTML = "";
        assetTableContainer.appendChild(table);

        headerRow.querySelectorAll("th.sortable").forEach(header => {
            header.addEventListener("click", () => {
                const column = header.dataset.column;
                let direction = 'asc';
                if (tableSortStates.assetResults.column === column && tableSortStates.assetResults.direction === 'asc') {
                    direction = 'desc';
                }
                tableSortStates.assetResults = { column, direction };
                renderAssetTable();
            });
        });
    }

    function handleAssetCheckboxChange(tag, checked) {
        const normalized = normalizeAssetTagValue(tag);
        if (!normalized) return;
        if (checked) {
            selectedAssetTags.add(normalized);
        } else {
            selectedAssetTags.delete(normalized);
        }
        renderAssetTable();
    }

    function handleSelectAllAssets(checked, rows) {
        rows.forEach(row => {
            const tag = normalizeAssetTagValue(row.AssetTag);
            if (!tag) return;
            if (checked) {
                selectedAssetTags.add(tag);
            } else {
                selectedAssetTags.delete(tag);
            }
        });
        renderAssetTable();
    }

    async function fetchConnectedAssetTags(tag, direction) {
        const params = new URLSearchParams();
        params.append("tag", tag);
        params.append("direction", direction);
        const response = await fetch(`${API_BASE_URL}/assets/linked?${params.toString()}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        const data = await response.json();
        const peers = Array.isArray(data?.peers) ? data.peers : [];
        return {
            peers,
            canonicalTag: data?.tag || "",
        };
    }

    async function updateOppositeOptions(side, tagValue) {
        const otherSide = side === "source" ? "target" : "source";
        const direction = side === "source" ? "outbound" : "inbound";
        const result = await fetchConnectedAssetTags(tagValue, direction);
        if (result.canonicalTag) {
            setCrosspointInputValue(side, result.canonicalTag);
        }
        if (result.peers.length) {
            setCrosspointControlMode(otherSide, "select", result.peers);
        } else {
            setCrosspointControlMode(otherSide, "text");
        }
    }

    initializeDiagramFieldSelects();
    const assetTagsReadyPromise = initializeAssetTagSelects();
    initializeAssetColumnSelect();

    const refreshDiagramAfterOptionChange = () => {
        if (!(currentFilters.targetTag || currentFilters.cableId)) {
            return;
        }
        fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType,
            currentFilters.protocol,
            currentFilters.cableId
        ).catch(error => {
            console.error("Error refreshing diagram after field change:", error);
        });
    };

    if (nodeFieldsSelect) {
        nodeFieldsSelect.addEventListener("change", refreshDiagramAfterOptionChange);
    }
    if (edgeFieldsSelect) {
        edgeFieldsSelect.addEventListener("change", refreshDiagramAfterOptionChange);
    }
    if (colorNodesCheckbox) {
        colorNodesCheckbox.addEventListener("change", refreshDiagramAfterOptionChange);
    }
    if (colorEdgesCheckbox) {
        colorEdgesCheckbox.addEventListener("change", refreshDiagramAfterOptionChange);
    }
    if (collapseStrategySelect) {
        collapseStrategySelect.addEventListener("change", refreshDiagramAfterOptionChange);
    }
    if (assetColumnSelect) {
        assetColumnSelect.addEventListener("change", () => renderAssetTable());
    }

    let baseTargetTag = "";
    let contextMenuTargetTag = null;
    let currentFilters = { targetTag: "", cableId: "", direction: "both", cableType: "", protocol: "" };
    const nodeExpansionMap = new Map(); // tag -> Set('in','out')
    let lastCrosspointQuery = null;
    let assetTagOptions = [];
    const assetTagLookup = new Map();


    const performDiagramView = async () => {
        console.log("View Diagram & Cables button clicked.");
        const targetInputValue = targetTagFilter.value.trim();

        if (!targetInputValue) {
            alert("Please enter a Target Asset Tag or Cable ID.");
            return;
        }

        const targetTag = targetInputValue;
        const cableId = "";

        baseTargetTag = targetInputValue;
        hiddenNodes.clear();
        hiddenNodeNeighbors.clear();
        allKnownDiagramAssetTags.clear();
        expansionResultLog.clear();

        currentFilters = {
            targetTag: targetTag,
            cableId: cableId, // Pass the identified cable ID
            direction: directionFilter.value,
            cableType: cableTypeFilter.value,
            protocol: protocolFilter ? protocolFilter.value.trim() : ""
        };

        initializeExpansionMap(baseTargetTag, currentFilters.direction);

        await fetchAndRenderDiagramAndCables(
            currentFilters.targetTag,
            currentFilters.direction,
            currentFilters.cableType,
            currentFilters.protocol,
            currentFilters.cableId, // Pass cableId as a new argument
            true // reset active assets on a fresh request
        );

        // Switch to diagram tab after loading (user explicitly requested to view it)
        document.querySelector('.tab-button[data-tab="diagramViewer"]').click();
    };

    viewDiagramBtn.addEventListener("click", performDiagramView);

    // Add Enter key support for diagram viewer inputs
    [targetTagFilter, cableTypeFilter, protocolFilter].forEach(input => {
        if (input) {
            input.addEventListener("keypress", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    performDiagramView();
                }
            });
        }
    });

    const performViewCrosspoint = async () => {
        const sourceTag = getCrosspointValue("source");
        const targetTag = getCrosspointValue("target");
        if (!sourceTag || !targetTag) {
            alert("Please enter both Source and Target asset tags.");
            return;
        }
        lastCrosspointQuery = { source: sourceTag, target: targetTag };
        await fetchAndRenderCrosspointMatrix(sourceTag, targetTag);
    };

    if (viewCrosspointBtn) {
        viewCrosspointBtn.addEventListener("click", performViewCrosspoint);
    }

    // Add Enter key support for crosspoint inputs
    if (crosspointSourceInput) {
        crosspointSourceInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                performViewCrosspoint();
            }
        });
    }
    if (crosspointTargetInput) {
        crosspointTargetInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                performViewCrosspoint();
            }
        });
    }

    if (resetCrosspointBtn) {
        resetCrosspointBtn.addEventListener("click", () => {
            resetCrosspointInputs(true);
            if (crosspointMatrixContainer) {
                crosspointMatrixContainer.innerHTML = "";
            }
            setCrosspointStatus("", "info");
        });
    }

    if (crosspointSourceInput) {
        crosspointSourceInput.addEventListener("input", () => {
            handleAssetInputChange("source", crosspointSourceInput.value.trim());
        });
    }
    if (crosspointTargetInput) {
        crosspointTargetInput.addEventListener("input", () => {
            handleAssetInputChange("target", crosspointTargetInput.value.trim());
        });
    }
    if (crosspointSourceSelect) {
        crosspointSourceSelect.addEventListener("change", () => handleAssetSelectChange("source"));
    }
    if (crosspointTargetSelect) {
        crosspointTargetSelect.addEventListener("change", () => handleAssetSelectChange("target"));
    }

    const handleCrosspointOptionChange = async () => {
        if (!lastCrosspointQuery) {
            return;
        }
        await fetchAndRenderCrosspointMatrix(lastCrosspointQuery.source, lastCrosspointQuery.target, true);
    };

    if (crosspointHeaderFields) {
        crosspointHeaderFields.addEventListener("change", handleCrosspointOptionChange);
    }
    if (crosspointProtocolSelect) {
        crosspointProtocolSelect.addEventListener("change", handleCrosspointOptionChange);
    }

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
    async function fetchAndRenderDiagramAndCables(targetTag, direction, cableType, protocol, cableId = "", resetActiveAssets = false, forceIncludeTags = new Set()) {
        const prevAvailableSnapshot = [...availableDiagramAssetTags];
        const expansionEntries = Array.from(nodeExpansionMap.entries());
        const selectedAssetsList = Array.from(selectedAssetTags)
            .map(tag => (tag || "").trim())
            .filter(Boolean);
        const additionalAssetsSet = new Set(
            expansionEntries
                .map(([tag]) => tag)
                .filter(tag => tag && tag !== baseTargetTag)
        );
        selectedAssetsList.forEach(tag => {
            if (tag !== baseTargetTag) {
                additionalAssetsSet.add(tag);
            }
        });
        const additionalAssetsList = Array.from(additionalAssetsSet);
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
        const colorNodesEnabled = colorNodesCheckbox ? colorNodesCheckbox.checked : false;
        const colorEdgesEnabled = colorEdgesCheckbox ? colorEdgesCheckbox.checked : false;
        const collapseStrategy = collapseStrategySelect ? collapseStrategySelect.value : "none";
        const combinedForceInclude = forceIncludeTags instanceof Set ? new Set(forceIncludeTags) : new Set();
        selectedAssetsList.forEach(tag => combinedForceInclude.add(tag));

        // --- Fetch Cable Data (also used to derive node list) ---
        const cableParams = new URLSearchParams();
        if (targetTag) cableParams.append("target_tag", targetTag);
        if (cableId) cableParams.append("cable_id", cableId); // Pass the cable ID
        cableParams.append("direction", direction);
        if (cableType) cableParams.append("cable_type", cableType);
        if (protocol) cableParams.append("protocol", protocol);
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
                baseTargetTag = responsePayload.primary_target || targetTag || cableId || "";
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
        selectedAssetsList.forEach(tag => discoveredAssetTags.add(tag));

        // Ensure any explicitly-unhidden nodes are always discoverable,
        // even if the backend didn't return their cables this fetch.
        combinedForceInclude.forEach(tag => { if (tag) discoveredAssetTags.add(tag); });

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
        selectedAssetsList.forEach(tag => {
            if (!tag) return;
            hiddenNodes.delete(tag);
            if (!activeDiagramAssetTags.includes(tag)) {
                activeDiagramAssetTags.push(tag);
            }
        });
        if (activeDiagramAssetTags.length === 0 && sortedDiscoveredTags.length > 0) {
            activeDiagramAssetTags = [...sortedDiscoveredTags];
        }

        // --- Fetch Graphviz SVG ---
        const dotParams = new URLSearchParams();
        dotParams.append("target_tag", targetTag);
        dotParams.append("direction", direction);
        if (cableType) dotParams.append("cable_type", cableType);
        if (protocol) dotParams.append("protocol", protocol);
        dotParams.append("node_fields", selectedNodeFields.join(','));
        dotParams.append("edge_fields", selectedEdgeFields.join(','));
        dotParams.append("color_nodes_by_category", colorNodesEnabled ? "true" : "false");
        dotParams.append("color_edges_by_protocol", colorEdgesEnabled ? "true" : "false");
        if (collapseStrategy && collapseStrategy !== "none") {
            dotParams.append("collapse_strategy", collapseStrategy);
        }
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
            hideContextMenu();
            
        } catch (error) {
            console.error("Error fetching or rendering Graphviz SVG:", error);
            const errMsg = `Error loading or rendering diagram: ${error.message}`;
            diagramRenderArea.innerHTML = `<p style="color: red;">${errMsg}</p>`;
            setDiagramStatus(errMsg, "error");
            return { availableChanged: false }; // Exit if SVG fetch fails
        }

        // --- Fetch and render input/output connection tables ---
        const diagramInputConnectionsContainer = document.getElementById(DIAGRAM_INPUT_CONNECTIONS_CONTAINER_ID);
        const diagramOutputConnectionsContainer = document.getElementById(DIAGRAM_OUTPUT_CONNECTIONS_CONTAINER_ID);

        if (diagramInputConnectionsContainer) diagramInputConnectionsContainer.innerHTML = '';
        if (diagramOutputConnectionsContainer) diagramOutputConnectionsContainer.innerHTML = '';

        if (targetTag && !cableId) { // Only fetch for asset tags, not cable IDs
            try {
                const inputResponse = await fetch(`${API_BASE_URL}/diagram/connections/inputs?target_tag=${encodeURIComponent(targetTag)}`);
                const inputData = await inputResponse.json();
                renderConnectionsTable(inputData, diagramInputConnectionsContainer, DIAGRAM_INPUT_CONNECTIONS_CONTAINER_ID, "Input Connections");
            } catch (error) {
                console.error("Error fetching input connections:", error);
                if (diagramInputConnectionsContainer) diagramInputConnectionsContainer.innerHTML = `<p style="color: red;">Error loading input connections: ${error.message}</p>`;
            }

            try {
                const outputResponse = await fetch(`${API_BASE_URL}/diagram/connections/outputs?target_tag=${encodeURIComponent(targetTag)}`);
                const outputData = await outputResponse.json();
                renderConnectionsTable(outputData, diagramOutputConnectionsContainer, DIAGRAM_OUTPUT_CONNECTIONS_CONTAINER_ID, "Output Connections");
            } catch (error) {
                console.error("Error fetching output connections:", error);
                if (diagramOutputConnectionsContainer) diagramOutputConnectionsContainer.innerHTML = `<p style="color: red;">Error loading output connections: ${error.message}</p>`;
            }
        }

        attachNodeContextMenuHandlers();
        const availableChanged = prevAvailableSnapshot.length !== availableDiagramAssetTags.length ||
            prevAvailableSnapshot.some((tag, idx) => tag !== availableDiagramAssetTags[idx]);
        if (availableChanged || newlyDiscovered.length > 0) {
            clearDiagramStatus();
        }
        return { availableChanged, newlyDiscoveredCount: newlyDiscovered.length };
    }

    async function fetchAndRenderCrosspointMatrix(sourceTag, targetTag) {
        if (!crosspointMatrixContainer) {
            return;
        }
        const headerFields = getSelectedOptions(crosspointHeaderFields, crosspointHeaderDefaults);
        const params = new URLSearchParams();
        params.append("source_tag", sourceTag);
        params.append("target_tag", targetTag);
        if (headerFields.length) {
            params.append("header_fields", headerFields.join(','));
        }
        const selectedProtocol = crosspointProtocolSelect ? crosspointProtocolSelect.value : "";
        if (selectedProtocol) {
            params.append("protocol", selectedProtocol);
        }
        setCrosspointStatus("Loading cross-point matrix...", "info");
        try {
            const response = await fetch(`${API_BASE_URL}/crosspoint/matrix?${params.toString()}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const data = await response.json();
            populateCrosspointProtocolOptions(data.protocols, data.protocol || "");
            renderCrosspointMatrix(data);
            setCrosspointStatus("", "info");
        } catch (error) {
            console.error("Error loading cross-point matrix:", error);
            if (crosspointMatrixContainer) {
                crosspointMatrixContainer.innerHTML = `<p style="color: red;">${error.message}</p>`;
            }
            setCrosspointStatus(`Failed to load cross-point data: ${error.message}`, "error");
        }
    }
    function attachNodeContextMenuHandlers() {
        const svgNodes = diagramRenderArea.querySelectorAll('g.node');
        svgNodes.forEach(node => {
            const titleEl = node.querySelector('title');
            if (!titleEl || !titleEl.textContent) return;
            const tag = titleEl.textContent.trim();
            if (!tag) return;
            if (tag.startsWith("__cable_junction__::")) return;
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
        if (!(currentFilters.targetTag || currentFilters.cableId)) return;
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
            currentFilters.cableType,
            currentFilters.protocol,
            currentFilters.cableId
        );
        clearDiagramStatus();
    }

    async function handleAddConnections(tag, direction) {
        if (!(currentFilters.targetTag || currentFilters.cableId)) return;
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
            currentFilters.protocol,
            currentFilters.cableId,
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

    function setCrosspointStatus(message, level = "info") {
        if (!crosspointStatus) return;
        if (!message) {
            crosspointStatus.textContent = "";
            crosspointStatus.className = "status-message hidden";
            return;
        }
        const levelClass = {
            info: "status-info",
            success: "status-success",
            warn: "status-warn",
            error: "status-error"
        }[level] || "status-info";
        crosspointStatus.className = `status-message ${levelClass}`;
        crosspointStatus.textContent = message;
    }

    function populateCrosspointProtocolOptions(options, selectedValue) {
        if (!crosspointProtocolSelect) {
            return;
        }
        const fallbackOptions = options && options.length ? options : [{ value: "", label: "All Protocols" }];
        crosspointProtocolSelect.innerHTML = "";
        fallbackOptions.forEach(option => {
            const opt = document.createElement("option");
            opt.value = option.value ?? "";
            opt.textContent = option.label || option.value || "All Protocols";
            crosspointProtocolSelect.appendChild(opt);
        });
        if (selectedValue) {
            crosspointProtocolSelect.value = selectedValue;
        } else {
            crosspointProtocolSelect.selectedIndex = 0;
        }
    }

    function renderCrosspointMatrix(data) {
        if (!crosspointMatrixContainer) {
            return;
        }
        const rows = Array.isArray(data?.rows) ? data.rows : [];
        const columns = Array.isArray(data?.columns) ? data.columns : [];
        const matrix = Array.isArray(data?.matrix) ? data.matrix : [];
        if (!rows.length || !columns.length) {
            crosspointMatrixContainer.innerHTML = "<p>No connections found between the selected assets.</p>";
            return;
        }
        const table = document.createElement("table");
        table.className = "crosspoint-table";
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        const cornerCell = document.createElement("th");
        cornerCell.className = "row-header";
        cornerCell.textContent = `${data?.source_tag || "Source"} → ${data?.target_tag || "Target"}`;
        headerRow.appendChild(cornerCell);
        columns.forEach(col => {
            const th = document.createElement("th");
            th.textContent = col.label || col.port || "";
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        rows.forEach((row, rowIndex) => {
            const tr = document.createElement("tr");
            const rowHeader = document.createElement("td");
            rowHeader.className = "row-header";
            rowHeader.textContent = row.label || row.port || "";
            tr.appendChild(rowHeader);
            columns.forEach((col, colIndex) => {
                const td = document.createElement("td");
                const hasConnection = Boolean(matrix[rowIndex]?.[colIndex]);
                td.className = `crosspoint-cell ${hasConnection ? "has-connection" : "no-connection"}`;
                td.textContent = hasConnection ? "✔" : "";
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        crosspointMatrixContainer.innerHTML = "";
        crosspointMatrixContainer.appendChild(table);
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
            const crosspointPayload = payload?.crosspoint || {};

            nodeFieldDefaults = Array.isArray(nodePayload.defaults) && nodePayload.defaults.length
                ? [...nodePayload.defaults]
                : [...DEFAULT_NODE_FIELDS];
            edgeFieldDefaults = Array.isArray(edgePayload.defaults) && edgePayload.defaults.length
                ? [...edgePayload.defaults]
                : [...DEFAULT_EDGE_FIELDS];
            crosspointHeaderDefaults = Array.isArray(crosspointPayload.defaults) && crosspointPayload.defaults.length
                ? [...crosspointPayload.defaults]
                : [...DEFAULT_CROSSPOINT_FIELDS];

            const nodeOptions = Array.isArray(nodePayload.options) && nodePayload.options.length
                ? nodePayload.options
                : buildFallbackOptions(nodeFieldDefaults);
            const edgeOptions = Array.isArray(edgePayload.options) && edgePayload.options.length
                ? edgePayload.options
                : buildFallbackOptions(edgeFieldDefaults);
            const crosspointOptions = Array.isArray(crosspointPayload.options) && crosspointPayload.options.length
                ? crosspointPayload.options
                : buildFallbackOptions(crosspointHeaderDefaults);

            populateFieldSelect(nodeFieldsSelect, nodeOptions, nodeFieldDefaults);
            populateFieldSelect(edgeFieldsSelect, edgeOptions, edgeFieldDefaults);
            if (crosspointHeaderFields) {
                populateFieldSelect(crosspointHeaderFields, crosspointOptions, crosspointHeaderDefaults);
            }
        } catch (error) {
            console.error("Error loading diagram field options:", error);
            populateFieldSelect(nodeFieldsSelect, buildFallbackOptions(nodeFieldDefaults), nodeFieldDefaults);
            populateFieldSelect(edgeFieldsSelect, buildFallbackOptions(edgeFieldDefaults), edgeFieldDefaults);
            if (crosspointHeaderFields) {
                populateFieldSelect(crosspointHeaderFields, buildFallbackOptions(crosspointHeaderDefaults), crosspointHeaderDefaults);
            }
        }
    }

    async function initializeAssetTagSelects() {
        if (!crosspointSourceSelect || !crosspointTargetSelect) {
            console.log("initializeAssetTagSelects: Crosspoint select elements not found.");
            return;
        }
        try {
            console.log("initializeAssetTagSelects: Fetching asset tags from API.");
            const response = await fetch(`${API_BASE_URL}/assets/tags`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const data = await response.json();
            assetTagOptions = Array.isArray(data.tags) ? data.tags : [];
            console.log(`initializeAssetTagSelects: Fetched ${assetTagOptions.length} asset tags.`);
        } catch (error) {
            console.error("Error loading asset tags:", error);
            assetTagOptions = [];
        }
        assetTagLookup.clear();
        assetTagOptions.forEach(tag => {
            if (!tag) return;
            assetTagLookup.set(tag.trim().toUpperCase(), tag);
        });
        console.log(`initializeAssetTagSelects: Populated assetTagLookup with ${assetTagLookup.size} entries.`);
        populateAssetSelect(crosspointSourceSelect, "Select Source Asset");
        populateAssetSelect(crosspointTargetSelect, "Select Target Asset");
        if (crosspointSourceInput && crosspointSourceInput.value.trim()) {
            handleAssetInputChange("source", crosspointSourceInput.value.trim());
        }
        if (crosspointTargetInput && crosspointTargetInput.value.trim()) {
            handleAssetInputChange("target", crosspointTargetInput.value.trim());
        }
    }

    async function initializeAssetColumnSelect() {
        if (!assetColumnSelect) {
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/assets/columns`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            const payload = await response.json();
            const columnOptions = Array.isArray(payload?.columns) && payload.columns.length
                ? payload.columns
                : buildFallbackOptions(assetColumnDefaults);
            assetColumnDefaults = Array.isArray(payload?.defaults) && payload.defaults.length
                ? payload.defaults
                : [...ASSET_TABLE_DEFAULT_COLUMNS];
            populateFieldSelect(assetColumnSelect, columnOptions, assetColumnDefaults);
        } catch (error) {
            console.error("Error loading asset column metadata:", error);
            populateFieldSelect(assetColumnSelect, buildFallbackOptions(assetColumnDefaults), assetColumnDefaults);
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

    function populateAssetSelect(selectElement, placeholderText, optionsList) {
        if (!selectElement) return;
        const sourceList = Array.isArray(optionsList) && optionsList.length ? optionsList : assetTagOptions;
        selectElement.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = placeholderText || "Select Asset";
        selectElement.appendChild(placeholder);
        sourceList.forEach(tag => {
            const opt = document.createElement("option");
            opt.value = tag;
            opt.textContent = tag;
            selectElement.appendChild(opt);
        });
    }

    function resolveAssetDisplay(value) {
        console.log(`resolveAssetDisplay: value=${value}`);
        if (!value) return null;
        const normalized = value.trim().toUpperCase();
        const resolved = assetTagLookup.get(normalized);
        console.log(`resolveAssetDisplay: normalized=${normalized}, resolved=${resolved}`);
        return resolved || null;
    }

    async function handleAssetInputChange(side, value) {
        console.log(`handleAssetInputChange: side=${side}, value=${value}`);
        if (!value) {
            console.log("handleAssetInputChange: value is empty, resetting inputs.");
            resetCrosspointInputs(false);
            return;
        }
        await assetTagsReadyPromise;
        const otherSide = side === "source" ? "target" : "source";
        const display = resolveAssetDisplay(value);
        console.log(`handleAssetInputChange: resolved display for ${value} is ${display}`);
        if (!display) {
            console.log(`handleAssetInputChange: ${value} is not a complete asset tag, setting other side to text mode.`);
            setCrosspointControlMode(otherSide, "text");
            return;
        }
        setCrosspointInputValue(side, display);
        setCrosspointControlMode(otherSide, "select");
        try {
            await updateOppositeOptions(side, display);
        } catch (error) {
            console.error("Error updating cross-point dropdown:", error);
            setCrosspointControlMode(otherSide, "text");
        }
    }

    function handleAssetSelectChange(side) {
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (!select) return;
        const value = select.value;
        if (!value) {
            resetCrosspointInputs(false);
            return;
        }
        setCrosspointInputValue(side, value);
        updateOppositeOptions(side, value).catch(error => {
            console.error("Error updating cross-point dropdown:", error);
        });
    }

    function setCrosspointControlMode(side, mode, optionsList) {
        const input = side === "source" ? crosspointSourceInput : crosspointTargetInput;
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (!input || !select) return;
        if (mode === "select" && (assetTagOptions.length || (optionsList && optionsList.length))) {
            populateAssetSelect(select, side === "source" ? "Select Source Asset" : "Select Target Asset", optionsList);
            const resolved = resolveAssetDisplay(input.value);
            if (resolved) {
                select.value = resolved;
            } else {
                select.value = "";
            }
            input.classList.add("hidden");
            select.classList.remove("hidden");
        } else {
            input.classList.remove("hidden");
            select.classList.add("hidden");
        }
    }

    function resetCrosspointInputs(clearValues = false) {
        setCrosspointControlMode("source", "text");
        setCrosspointControlMode("target", "text");
        if (crosspointSourceSelect) {
            populateAssetSelect(crosspointSourceSelect, "Select Source Asset");
            crosspointSourceSelect.value = "";
        }
        if (crosspointTargetSelect) {
            populateAssetSelect(crosspointTargetSelect, "Select Target Asset");
            crosspointTargetSelect.value = "";
        }
        if (clearValues) {
            if (crosspointSourceInput) crosspointSourceInput.value = "";
            if (crosspointTargetInput) crosspointTargetInput.value = "";
            lastCrosspointQuery = null;
        }
    }

    function getCrosspointValue(side) {
        const input = side === "source" ? crosspointSourceInput : crosspointTargetInput;
        const select = side === "source" ? crosspointSourceSelect : crosspointTargetSelect;
        if (select && !select.classList.contains("hidden") && select.value) {
            return select.value.trim();
        }
        return input ? input.value.trim() : "";
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

    // --- Utility: Render Connections Table ---
    function humanizeConnectionsFieldLabel(value) {
        if (!value) return "";
        if (FALLBACK_FIELD_LABELS[value]) {
            return FALLBACK_FIELD_LABELS[value];
        }
        const spaced = value.replace(/([A-Z])/g, ' $1').trim();
        return spaced.charAt(0).toUpperCase() + spaced.slice(1);
    }

    function renderConnectionsTable(data, container, tableId, title) {
        if (!container) return;
        
        container.innerHTML = ''; // Clear previous content

        if (!data || data.length === 0) {
            const h4 = document.createElement("h4");
            h4.textContent = title;
            container.appendChild(h4);
            container.innerHTML += `<p>No ${title.toLowerCase()} found for this asset.</p>`;
            return;
        }

        const h4 = document.createElement("h4");
        h4.textContent = title;
        container.appendChild(h4);

        const table = document.createElement("table");
        table.className = "connections-table";
        const thead = document.createElement("thead");
        const tbody = document.createElement("tbody");

        // Create table headers
        const headers = Object.keys(data[0]);
        const headerRow = document.createElement("tr");
        headers.forEach(headerText => {
            const th = document.createElement("th");
            th.textContent = humanizeConnectionsFieldLabel(headerText);
            th.dataset.column = headerText;
            th.classList.add('sortable');
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Sort data based on current state
        const currentSortState = tableSortStates[tableId];
        if (currentSortState.column) {
            data.sort((a, b) => {
                const valA = a[currentSortState.column] ?? "";
                const valB = b[currentSortState.column] ?? "";
                let comparison = 0;
                if (valA > valB) comparison = 1;
                else if (valA < valB) comparison = -1;
                return currentSortState.direction === 'desc' ? comparison * -1 : comparison;
            });
        }

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

        container.appendChild(table);

        // Add event listeners to headers for sorting
        thead.querySelectorAll('th.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                let direction = 'asc';

                if (tableSortStates[tableId].column === column && tableSortStates[tableId].direction === 'asc') {
                    direction = 'desc';
                }

                tableSortStates[tableId] = { column, direction };
                // Re-render the specific table
                renderConnectionsTable(data, container, tableId, title);
            });
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
        // Initialize sort state if it doesn't exist
        if (!tableSortStates[tableId]) {
            tableSortStates[tableId] = { column: null, direction: 'asc' };
        }
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

                // Special handling for IssueID in knowledge base issues table
                if (tableId === "knowledgeBaseIssuesTable" && headerText === "IssueID") {
                    const issueId = rowData[headerText];
                    if (issueId) {
                        td.style.cursor = "pointer";
                        td.style.color = "#0066cc";
                        td.style.textDecoration = "underline";
                        td.textContent = issueId;
                        td.addEventListener("click", async () => {
                            // Switch to Knowledge Base tab
                            document.querySelector('.tab-button[data-tab="knowledgeBase"]').click();

                            // Populate the IssueID search field
                            if (kbIssueIdSearch) kbIssueIdSearch.value = issueId;
                            if (kbTagSearch) kbTagSearch.value = '';
                            if (kbFreeformSearch) kbFreeformSearch.value = '';

                            // Perform the search
                            await performKBSearch();
                        });
                    } else {
                        td.textContent = rowData[headerText];
                    }
                } else {
                    td.textContent = rowData[headerText];
                }

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

    async function fetchAndRenderAssetDetails(assetTag) {
        const assetPropertiesContainer = document.getElementById(ASSET_PROPERTIES_CONTAINER_ID);
        const inputPartnersList = document.getElementById(INPUT_PARTNERS_LIST_ID);
        const outputPartnersList = document.getElementById(OUTPUT_PARTNERS_LIST_ID);
        const knowledgeBaseIssuesTableContainer = document.getElementById(KNOWLEDGE_BASE_ISSUES_TABLE_ID);

        // Clear previous content from individual containers only
        if (assetPropertiesContainer) assetPropertiesContainer.innerHTML = '<p>Loading asset details...</p>';
        if (inputPartnersList) inputPartnersList.innerHTML = '';
        if (outputPartnersList) outputPartnersList.innerHTML = '';
        if (knowledgeBaseIssuesTableContainer) knowledgeBaseIssuesTableContainer.innerHTML = '';

        document.querySelector(`.tab-button[data-tab="${ASSET_DETAILS_TAB_ID}"]`).click(); // Switch to asset details tab

        try {
            const response = await fetch(`${API_BASE_URL}/assets/${encodeURIComponent(assetTag)}/details`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            renderAssetProperties(data.asset, assetPropertiesContainer);
            renderPartnersList(data.input_partners, inputPartnersList, "input");
            renderPartnersList(data.output_partners, outputPartnersList, "output");
            renderKnowledgeBaseIssues(data.knowledge_base_issues, knowledgeBaseIssuesTableContainer);
        } catch (error) {
            console.error("Error fetching asset details:", error);
            if (assetPropertiesContainer) assetPropertiesContainer.innerHTML = `<p style="color: red;">Error loading asset details: ${error.message}</p>`;
            if (inputPartnersList) inputPartnersList.innerHTML = '';
            if (outputPartnersList) outputPartnersList.innerHTML = '';
            if (knowledgeBaseIssuesTableContainer) knowledgeBaseIssuesTableContainer.innerHTML = '';
        }
    }

    function renderAssetProperties(asset, container) {
        if (!container || !asset) return;
        container.innerHTML = '<h3>Properties</h3>';

        const getValue = (key) => asset[key] || "";
        const hasValue = (key) => asset[key] && String(asset[key]).trim() !== "";

        // Define field groups
        const basicFields = ["AssetTag", "Type", "Category", "InService", "Manufacturer", "Model", "SN", "AcqYear", "EOLYear", "Usage", "Desc"];
        const locationFields = ["Building", "Floor", "Room", "Location", "Rack", "RackU", "RackHeight"];
        const financialFields = ["Qty", "Unit", "AcqValue", "PurchaseDate", "PurcForm", "Invoice"];
        const dispositionFields = ["Disposition", "DispositionDate", "DispositionDestination", "DispositionNotes"];

        const allGroupedFields = new Set([
            ...basicFields, ...locationFields, ...financialFields, ...dispositionFields
        ]);

        const content = document.createElement("div");
        content.className = "asset-properties-content";

        // Helper function to create a table with headers and values
        function createPropertyTable(fields) {
            // Filter to only fields that have values
            const fieldsWithValues = fields.filter(field => hasValue(field));
            if (fieldsWithValues.length === 0) return null;

            const table = document.createElement("table");
            table.className = "property-table";

            // Create header row
            const thead = document.createElement("thead");
            const headerRow = document.createElement("tr");
            fieldsWithValues.forEach(field => {
                const th = document.createElement("th");
                th.textContent = humanizeFieldLabel(field);
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            // Create value row
            const tbody = document.createElement("tbody");
            const valueRow = document.createElement("tr");
            fieldsWithValues.forEach(field => {
                const td = document.createElement("td");
                td.textContent = getValue(field);
                valueRow.appendChild(td);
            });
            tbody.appendChild(valueRow);
            table.appendChild(tbody);

            return table;
        }

        // Basic Information Table
        const basicSection = document.createElement("div");
        basicSection.className = "property-section";
        basicSection.innerHTML = "<h4>Basic Information</h4>";

        // Row 1: AssetTag, Type, Category, InService
        const row1Table = createPropertyTable(["AssetTag", "Type", "Category", "InService"]);
        if (row1Table) basicSection.appendChild(row1Table);

        // Row 2: Manufacturer, Model, SN
        const row2Table = createPropertyTable(["Manufacturer", "Model", "SN"]);
        if (row2Table) basicSection.appendChild(row2Table);

        // Row 3: AcqYear, EOLYear, Usage, Desc
        const row3Table = createPropertyTable(["AcqYear", "EOLYear", "Usage", "Desc"]);
        if (row3Table) basicSection.appendChild(row3Table);

        content.appendChild(basicSection);

        // Location Table
        const hasLocation = locationFields.some(field => hasValue(field));
        if (hasLocation) {
            const locationSection = document.createElement("div");
            locationSection.className = "property-section";
            locationSection.innerHTML = "<h4>Location</h4>";

            const locationTable = createPropertyTable(locationFields);
            if (locationTable) locationSection.appendChild(locationTable);

            content.appendChild(locationSection);
        }

        // Financial Table (including "Other" fields except EOLYear which is already in Basic)
        const otherFields = Object.keys(asset).filter(key => !allGroupedFields.has(key) && hasValue(key));
        const allFinancialFields = [...financialFields, ...otherFields];

        const hasFinancial = allFinancialFields.some(field => hasValue(field));
        if (hasFinancial) {
            const financialSection = document.createElement("div");
            financialSection.className = "property-section";
            financialSection.innerHTML = "<h4>Financial</h4>";

            const financialTable = createPropertyTable(allFinancialFields);
            if (financialTable) financialSection.appendChild(financialTable);

            content.appendChild(financialSection);
        }

        // Disposition (only if Disposition is not "N")
        const disposition = getValue("Disposition").toUpperCase();
        if (disposition && disposition !== "N") {
            const dispSection = document.createElement("div");
            dispSection.className = "property-section";
            dispSection.innerHTML = "<h4>Disposition</h4>";

            const dispTable = createPropertyTable(dispositionFields);
            if (dispTable) dispSection.appendChild(dispTable);

            content.appendChild(dispSection);
        }

        container.appendChild(content);
    }

    function renderPartnersList(partners, container, direction) {
        if (!container) return;
        container.innerHTML = ''; // Clear previous content
        if (!partners || partners.length === 0) {
            container.textContent = `No ${direction} partners found.`;
            return;
        }
        const ul = document.createElement("ul");
        ul.className = "partner-list";
        partners.forEach(partner => {
            const li = document.createElement("li");
            li.className = "partner-item";
            li.textContent = `${partner.AssetTag} (${partner.Manufacturer} ${partner.Model} - ${partner.Usage})`;
            li.dataset.assetTag = partner.AssetTag;
            li.addEventListener("click", async (event) => {
                const newTargetTag = event.target.dataset.assetTag;
                if (newTargetTag) {
                    // Update both Asset Details and Connectivity Diagram tabs
                    assetDetailsTagInput.value = newTargetTag;
                    targetTagFilter.value = newTargetTag;

                    // Update the diagram state
                    baseTargetTag = newTargetTag;
                    hiddenNodes.clear();
                    hiddenNodeNeighbors.clear();
                    allKnownDiagramAssetTags.clear();
                    expansionResultLog.clear();

                    currentFilters = {
                        targetTag: newTargetTag,
                        cableId: "",
                        direction: directionFilter.value,
                        cableType: cableTypeFilter.value,
                        protocol: protocolFilter ? protocolFilter.value.trim() : ""
                    };

                    initializeExpansionMap(baseTargetTag, currentFilters.direction);

                    // Reload asset details for the clicked partner
                    await fetchAndRenderAssetDetails(newTargetTag);

                    // Also update the connectivity diagram in the background
                    await fetchAndRenderDiagramAndCables(
                        currentFilters.targetTag,
                        currentFilters.direction,
                        currentFilters.cableType,
                        currentFilters.protocol,
                        currentFilters.cableId,
                        true // reset active assets on a fresh request
                    );
                }
            });
            ul.appendChild(li);
        });
        container.appendChild(ul);
    }

    function renderKnowledgeBaseIssues(issues, container) {
        if (!container) return;
        container.innerHTML = '<h3>Relevant Knowledge Base Issues</h3>';
        if (!issues || issues.length === 0) {
            container.innerHTML += "<p>No relevant knowledge base issues found.</p>";
            return;
        }
        renderTable(issues, container, "knowledgeBaseIssuesTable"); // Reuse renderTable
    }

    function renderKBResults(issues) {
        if (!kbResultsContainer) return;

        kbResultsContainer.innerHTML = '';

        if (!issues || issues.length === 0) {
            kbResultsContainer.innerHTML = '<p>No knowledge base issues found matching your search criteria.</p>';
            return;
        }

        const autoExpand = issues.length === 1;

        issues.forEach((issue, index) => {
            const issueSection = document.createElement('div');
            issueSection.className = 'kb-issue-section';

            // Create header (always visible)
            const header = document.createElement('div');
            header.className = 'kb-issue-header';
            header.innerHTML = `
                <span class="kb-issue-id">${escapeHtml(issue.IssueID || '')}</span>
                <span class="kb-issue-title">${escapeHtml(issue.Title || '')}</span>
                <span class="kb-expand-icon">${autoExpand ? '▼' : '▶'}</span>
            `;

            // Create details section (expandable)
            const details = document.createElement('div');
            details.className = autoExpand ? 'kb-issue-details expanded' : 'kb-issue-details';

            // Build the details content
            const fieldsToDisplay = [
                { label: 'Category', value: issue.Category },
                { label: 'Subcategory', value: issue.Subcategory },
                { label: 'Symptom', value: issue.Symptom },
                { label: 'Trigger Conditions', value: issue.TriggerConditions },
                { label: 'Likely Cause', value: issue.LikelyCause },
                { label: 'Recovery Steps', value: issue.RecoverySteps },
                { label: 'Applies to Asset Type', value: issue.AppliesToAssetType },
                { label: 'Applies to Asset Tag', value: issue.AppliesToAssetTag },
                { label: 'Tags', value: issue.Tags },
                { label: 'Notes', value: issue.Notes }
            ];

            fieldsToDisplay.forEach(field => {
                if (field.value && field.value !== '' && field.value !== 'N/A') {
                    const fieldDiv = document.createElement('div');
                    fieldDiv.className = 'kb-field';

                    const label = document.createElement('strong');
                    label.textContent = field.label + ': ';
                    fieldDiv.appendChild(label);

                    const valueSpan = document.createElement('span');
                    valueSpan.className = 'kb-field-value';

                    // Special handling for Applies to Asset Tag - make tags clickable
                    if (field.label === 'Applies to Asset Tag') {
                        // Parse comma-separated tags
                        const tags = field.value.split(',').map(t => t.trim()).filter(t => t.length > 0);
                        tags.forEach((tag, tagIndex) => {
                            if (tagIndex > 0) {
                                valueSpan.appendChild(document.createTextNode(', '));
                            }
                            const tagLink = document.createElement('span');
                            tagLink.textContent = tag;
                            tagLink.style.cursor = 'pointer';
                            tagLink.style.color = '#0066cc';
                            tagLink.style.textDecoration = 'underline';
                            tagLink.addEventListener('click', async () => {
                                // Update Asset Details and Connectivity Diagram
                                assetDetailsTagInput.value = tag;
                                targetTagFilter.value = tag;

                                // Update the diagram state
                                baseTargetTag = tag;
                                hiddenNodes.clear();
                                hiddenNodeNeighbors.clear();
                                allKnownDiagramAssetTags.clear();
                                expansionResultLog.clear();

                                currentFilters = {
                                    targetTag: tag,
                                    cableId: "",
                                    direction: directionFilter.value,
                                    cableType: cableTypeFilter.value,
                                    protocol: protocolFilter ? protocolFilter.value.trim() : ""
                                };

                                initializeExpansionMap(baseTargetTag, currentFilters.direction);

                                // Fetch and render asset details
                                await fetchAndRenderAssetDetails(tag);

                                // Update connectivity diagram in background
                                await fetchAndRenderDiagramAndCables(
                                    currentFilters.targetTag,
                                    currentFilters.direction,
                                    currentFilters.cableType,
                                    currentFilters.protocol,
                                    currentFilters.cableId,
                                    true
                                );

                                // Switch to Asset Details tab
                                document.querySelector('.tab-button[data-tab="assetDetails"]').click();
                            });
                            valueSpan.appendChild(tagLink);
                        });
                    } else {
                        // Render markdown if marked library is available
                        if (typeof marked !== 'undefined' && marked.parse) {
                            valueSpan.innerHTML = marked.parse(field.value);
                        } else {
                            valueSpan.textContent = field.value;
                        }
                    }

                    fieldDiv.appendChild(valueSpan);

                    details.appendChild(fieldDiv);
                }
            });

            // Add click handler to toggle expansion
            header.addEventListener('click', () => {
                const isExpanded = details.classList.contains('expanded');
                details.classList.toggle('expanded');
                const icon = header.querySelector('.kb-expand-icon');
                if (icon) {
                    icon.textContent = isExpanded ? '▶' : '▼';
                }
            });

            issueSection.appendChild(header);
            issueSection.appendChild(details);
            kbResultsContainer.appendChild(issueSection);
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
