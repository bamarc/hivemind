## ADDED Requirements

### Requirement: Display index overview statistics
The dashboard SHALL display key index statistics at a glance: total indexed chunks, total indexed files, and average search response time.

#### Scenario: Dashboard shows current stats on load
- **WHEN** the user navigates to the Dashboard page
- **THEN** the dashboard displays indexed chunks count, indexed files count, and average search time
- **AND** all values update dynamically from the backend

### Requirement: Show server operational status
The dashboard SHALL display the current MCP server status (running/stopped) with appropriate color coding.

#### Scenario: Server status indicator reflects current state
- **WHEN** the server is running
- **THEN** the dashboard shows "Running" in green
- **WHEN** the server is stopped
- **THEN** the dashboard shows "Stopped" in red

### Requirement: Show recent search activity
The dashboard SHALL list the most recent semantic searches performed through the UI.

#### Scenario: Recent searches appear chronologically
- **WHEN** a search is performed on the Search page
- **THEN** it appears at the top of the recent activity list on the Dashboard
