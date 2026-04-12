# Web Application Requirements

This document outlines the requirements for the interactive web application.

## 1. Core Functionality

-   **Interactive Data Query:** The application must allow users to query asset and cable data dynamically.
-   **Asset Search:**
    -   Searchable by asset tag, manufacturer, and model.
    -   Results displayed in a tabular format.
    -   Asset tags in the results table are clickable links that navigate to the Asset Details tab for that asset and update the Connectivity Diagram in the background.
    -   Pressing Enter in any search input field triggers the search.
    -   "In Service Only" checkbox filters results to only show assets with InService="Y" (checked by default).
-   **Cable Filtering:**
    -   Filterable by a target asset tag or a cable ID.
    -   Filterable by connection direction: in-bound, out-bound, or both.
    -   Filterable by cable type.
    -   Filtered cable data displayed in a tabular format.
-   **Connectivity Diagram Rendering:**
    -   Dynamically generate and display connectivity diagrams based on filtered cable data.
    -   Diagrams should visually represent connections between assets.
    -   The diagramming technique should render the actual diagram, not just DOT code.
    -   Asset tags must be handled case-insensitively to avoid duplicate nodes when casing differs between data sources.
    -   Each node label must include the asset tag, manufacturer, model, and usage fields centered in the body.
    -   **Cable-to-Cable Connections:** When a cable terminates at another cable (for example one row references another row's `Tag` in `SrcTag` or `DstTag`), the splice/junction must be depicted as a small dot (`shape=point`) node. The contributing cable segments remain separate labeled edges and the connection continues through the dot to the next cable segment or final destination asset. This pattern can repeat for multiple intermediate cables.

## 2. User Interface (UI)

-   **Structure:** The application will be a single-page web application.
-   **Navigation:** Separate tabs must be provided for:
    -   Asset Search Results.
    -   Cable Filtering Results (table).
    -   Connectivity Diagram (visual rendering).
    -   Cross-point matrix exploration.
    -   Asset Details.
    -   Knowledge Base.
-   **Input Controls:**
    -   Text input fields for asset tag, manufacturer, model searches.
    -   Text input field for target asset tag or cable ID for cable filtering.
    -   Dropdown/selection for connection direction (in-bound, out-bound, both).
    -   Text input field for cable type filtering.
    -   Text input field for protocol filtering so users can isolate specific logical paths (e.g., Dante, SDI).
    -   All text input fields support pressing Enter to trigger the associated action button (search, view diagram, view details, etc.).
    -   Multi-select control (located on the Asset Results tab) for asset search results to choose which columns appear in the table (defaulting to Asset Tag, Model, Manufacturer, Description, Usage).
    -   A persistent "Select" checkbox column in the asset table so users can add rows to the diagram/cable view regardless of which columns are displayed; selected assets must always be honored in downstream views even when they are not adjacent to the current target.
    -   A globally accessible "Reload Data" button so users can refresh the asset and cable sources without restarting services.
    -   Diagram nodes must expose a context menu for hiding nodes or expanding them in-bound/out-bound. Right-clicking a node must expose options to hide the node or expand its in-bound/out-bound connections; these expansions should be reflected immediately in both the cable table and the rendered diagram.
    -   Multi-select controls must allow users to choose which asset fields (Tag, Manufacturer, Model, Usage) appear on node labels and which cable fields (Tag, Type, In-Port→Out-Port, Usage) appear on cable labels. Each list must include every available field from the underlying dataset with the default values pinned to the top (Tag/Manufacturer/Model/Usage for nodes; Tag/Type/In-Port→Out-Port/Usage for cables) and the remaining fields sorted alphabetically.
    -   Checkboxes must allow users to toggle color-coded treatment of node backgrounds (based on asset Category) and cable link colors (based on Protocol) using industry-appropriate palettes. The "Color Edges by Protocol" option is checked by default to provide visual differentiation of cable types.
    -   A grouping selector must allow users to collapse diagram connections by Protocol or Cable Type; when collapsed, the port labels must show the grouping value (e.g., “dante”) instead of individual port names so the diagram stays readable.
    -   The Cross-point tab must provide Source and Target asset tag inputs, a multi-select that controls which cable fields appear in the row/column headers (default Port + Usage), and a protocol dropdown containing only the protocols observed between those two assets. Entering a valid asset tag into either Source or Target must automatically convert the opposite control into a single-select dropdown of only the directly connected assets (based on direction), and a reset button or clearing the text input must restore both controls to standard text entries when needed.
    -   Changing any diagram option must immediately refresh both the cable table and the rendered diagram so the selected labels are reflected without extra button clicks.
-   **Output Display:**
    -   Results for asset search and cable filtering will be displayed in clear, readable tables. Column headers must be sort-able.
    -   Connectivity diagrams will be rendered interactively or as images within the UI. When grouping is enabled, multiple ports of the same Protocol/Type must collapse into a single connection that displays the grouping label and the number of collapsed cables, while keeping inbound/outbound sides distinct.
    -   The asset table must always expose a Select column; any checked assets must automatically be included alongside the typed target when loading the cable table and diagram, even if they have no current adjacency in the rendered graph.
    -   The Cross-point tab must render a matrix with Source ports for rows and Target ports for columns, highlighting each intersecting cell in green when a connection exists for the selected protocol and white otherwise.
    -   Below the connectivity diagram, two text tables must be displayed for the target device: one for input connection details and one for output connection details. Each table should include the target port, partner port (source for inputs, destination for outputs), protocol, cable ID, and the partner device's asset tag, manufacturer, model, and usage. All columns in these tables must be sortable by clicking their headers. These tables must be included in the print view, with a page break inserted before each table.
    -   **Asset Details Tab:**
        -   Provides an input field for an Asset Tag and a button to "View Details".
        -   Displays all fields from the asset table for the target device in a table-based layout with logical grouping:
            -   **Basic Information** (displayed as multiple tables):
                -   Row 1: Asset Tag, Type, Category, InService
                -   Row 2: Manufacturer, Model, SN
                -   Row 3: AcqYear, EOLYear, Usage, Desc
            -   **Location**: Building, Floor, Room, Location, Rack, RackU, RackHeight (single table spanning horizontally)
            -   **Financial**: Qty, Unit, AcqValue, PurchaseDate, PurcForm, Invoice, and any other fields not in Basic/Location/Disposition (single table spanning horizontally)
            -   **Disposition**: Disposition fields only displayed in a table format if Disposition is not "N"
        -   Shows a distinct list of all input partners (AssetTag, Manufacturer, Model, Usage). Each partner item must be clickable.
        -   Shows a distinct list of all output partners (AssetTag, Manufacturer, Model, Usage). Each partner item must be clickable.
        -   Clicking an input or output partner in the list should update both the Asset Details view and the Connectivity Diagram tab with the selected partner's AssetTag. The Asset Details tab remains active while the Connectivity Diagram is updated in the background, allowing users to seamlessly navigate through connected assets while keeping both views synchronized.
        -   Displays a table of all relevant issues from `data/knowledgebase.xlsx` where the target asset's tag is present in the `AppliesToAssetTag` column. This table should include `IssueID`, `Title`, `Category`, and `Subcategory`, and be sortable by column headers. The `IssueID` values are clickable and navigate to the Knowledge Base tab with the clicked issue automatically loaded.
    -   **Knowledge Base Tab:**
        -   Provides three search fields: IssueID, Tag (Asset Tag), and freeform text search.
        -   Pressing Enter in any search field triggers the search, as does clicking the Search button.
        -   Freeform text search searches across all fields in the knowledge base, ignoring whitespace, case, and punctuation.
        -   Search results are sorted by Category, Subcategory, and SortOrder.
        -   Each issue is displayed as an expandable section showing the IssueID and Title when collapsed.
        -   When expanded, the issue displays all fields including Symptom, Trigger Conditions, Likely Cause, Recovery Steps, and other relevant information.
        -   Fields support markdown formatting for rich text display.
        -   If only one issue is found in the search results, it is automatically expanded.
        -   Clicking an IssueID in the Asset Details tab navigates to the Knowledge Base tab and automatically searches for and displays that issue.
        -   Asset tags listed in the "Applies to Asset Tag" field are clickable and behave the same as clicking asset tags elsewhere - they update both the Asset Details view and the Connectivity Diagram in the background, then switch to the Asset Details tab.
    -   When printing from the browser, only the connectivity diagram should appear to produce clean hard copies.
## 3. Technology Stack

-   **Frontend:** HTML, CSS, JavaScript (lightweight, no heavy frameworks required unless specified).
-   **Backend:** Python with FastAPI.
-   **Data Processing:** Pandas library for handling Excel data.
-   **Diagramming:** Graphviz DOT language generated by backend, rendered by a suitable frontend library (e.g., Viz.js) or server-side.

## 4. Data Sources

-   `uac_assets.xlsx`: Contains asset inventory information.
-   `uac_cables.xlsx`: Contains cable connectivity details.

## 5. Deployment

-   The entire web application (frontend and backend) will reside in a subdirectory named `webapp` within the main project.
-   Backend will run on port `9000`.

## 6. Testing

-   Provide a test suite that exercises key back-end endpoints and reports clearly logged PASS/FAIL results so developers can diagnose regressions quickly.
-   Test suite needs to allow terminal-driven test exedcution (e.g., `python3 tests/run_tests.py`)

## 7. Current Known Issues / Bugs / TODOs

-   Some nodes support an in-bound and out-bound connection on the same port (for example Floor Boxes). The diagram currently only renders such ports twice but makes all connections to only one side. Put the inbound connection on the left side, and the out-bound on the right. (Or top and Bottom depnding on diagram orientation)

## 8. Pending Enhancements

-   Add support for multiple diagram layouts (e.g., hierarchical, radial) to improve readability for complex connectivity.
-   Provide a context menu on the individual diagram lines to hide. The node context menu should also provide a reshow option with a sublist of available lines that can be readded to the diagram.
-   Allow the input list to be a comma-separated list of asset tags to support. This would allow users to explore connectivity between multiple assets simultaneously without needing to perform separate queries for each one.
-   Some nodes have a large number of connections (e.g., the 2507-0700 has 20+ cables). The diagram can become cluttered and difficult to read. Implementing a more sophisticated layout algorithm or allowing users to selectively collapse/expand groups of connections would improve readability, collapsing should be done be grouping cables of the same type or protocol (to be implemented). When showing a collapsed group, replace the port labels with the grouping value. For example if the collapsed line represented the dante connections, show the labels as dante. Be sure to keep the inbound and outbound labels distinct.
-   Provide a diagram option to export as jpg or png for easy sharing and documentation purposes. This would allow users to save and share connectivity diagrams without needing to share the entire web application or access to the backend data.
-   Provide a diagram option to layout the diagram top-to-bottom or left-to-right. This would allow users to choose the layout that best suits their needs and improves readability, especially for diagrams with many connections.
-   Add a new field to the cable data for "Protocol" (e.g., SDI, HDMI, Ethernet) and refactor the existing Type field to be specific about the cable type and not conflate it with the protocol. This would allow users to filter and label cables based on the protocol they carry, which is often more relevant for understanding connectivity than the physical cable type alone. For example, a cable could be labeled as "Type: Cat6, Protocol: Ethernet" to provide clearer information about its function in the system.
-   On the "Cable and Diagram Viewer" pane , change the cable type filter to a protocol filter and ensure it is case in-sensitive.
-   Add a hover text for the cables that displays the cableid.
-   Add context menu options for the nodes for hide-inbound, and hide-outbound.
-   Add a new tab called "Cross-point" This tab should have two entry fields, "Source" and "Target" which accept valid asset tags. The body of this tab should be a cross-point matrix with source ports as the rows, and target ports as the columns. There should be a drop-down multi-select list which determines which fields to show as the row and column headers, with the default being a concatenation of port and usage. There should be a selection box where the protocol type can be specified; the list should be populated with the subset of protocols that exists between Source and Target. Highlight the intersection cell in green if there is a connection, white otherwise.
-   The "Diagram Options" UI panel should be with the Diagram Tab, not global.
-   Add a select field to the Asset Table. The selected items from that table should all be included in the diagram and cable table views. This is in addition to what ever assets or cables are included via the text entry field
-   Add a column selection multi-select dropdown list to the "Asset Results" table. The selected columns will be the columns displayed in the table. The pre-selected defaults will be the asset Tag, Make, Manufacturer, Description and Usage. There is another enhancement for there to be a select checkbox, that should always be visible and usable.\
