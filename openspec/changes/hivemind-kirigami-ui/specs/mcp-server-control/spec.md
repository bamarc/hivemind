## ADDED Requirements

### Requirement: Start the MCP server from the UI
The system SHALL provide a button to start the Hivemind MCP server.

#### Scenario: User starts the server
- **WHEN** the server is stopped and the user clicks "Start Server"
- **THEN** the backend starts the MCP server process
- **AND** the server status updates to "running" with a green indicator

### Requirement: Stop the MCP server from the UI
The system SHALL provide a button to stop the running MCP server.

#### Scenario: User stops the server
- **WHEN** the server is running and the user clicks "Stop Server"
- **THEN** the backend stops the MCP server process
- **AND** the server status updates to "stopped" with a red indicator

### Requirement: Display server statistics
The server page SHALL show: current status, number of connected clients, total requests served, and server uptime.

#### Scenario: Server stats are visible on the page
- **WHEN** the user views the Server page
- **THEN** the page displays server status, connected clients count, requests served count, and uptime duration

### Requirement: List registered MCP tools
The server page SHALL list all MCP tools registered by the server.

#### Scenario: Registered tools are shown
- **WHEN** the user views the Server page while the server is running
- **THEN** the page lists all registered MCP tools (semantic_code_search, get_file_tree, analyze_code_complexity, generate_blueprint, run_verification)

### Requirement: View server logs
The system SHALL provide an OverlaySheet dialog showing recent server log entries.

#### Scenario: User views server logs
- **WHEN** the user clicks "View Log"
- **THEN** an OverlaySheet opens showing recent server log entries in a monospace text area
