## ADDED Requirements

### Requirement: Show real-time indexing progress
When indexing is active, the Indexer page SHALL display a progress bar, current file name, files done/total, and estimated time remaining.

#### Scenario: Indexing progress updates live
- **WHEN** the indexer is processing files
- **THEN** a progress card shows the current file name
- **AND** a progress bar shows completion percentage
- **AND** the file count (done/total) and ETA are displayed
- **AND** all values update in real-time as files are processed

### Requirement: Configure chunker parameters
The Indexer page SHALL allow the user to configure the chunker type, max chunk size, and overlap.

#### Scenario: User changes chunker config
- **WHEN** the user selects a different chunker type from the dropdown
- **THEN** the selection is stored for the next indexing run
- **WHEN** the user changes max chunk size or overlap via spin boxes
- **THEN** the new values are stored for the next indexing run

### Requirement: Pause and stop indexing
The system SHALL provide pause and stop controls for an active indexing run.

#### Scenario: User pauses indexing
- **WHEN** the user clicks "Pause" during indexing
- **THEN** indexing pauses and the button text changes to "Resume"

#### Scenario: User stops indexing
- **WHEN** the user clicks "Stop" during indexing
- **THEN** indexing is cancelled immediately
- **AND** the progress card is hidden
