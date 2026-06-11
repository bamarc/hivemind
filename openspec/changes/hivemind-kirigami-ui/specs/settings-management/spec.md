## ADDED Requirements

### Requirement: Configure Qdrant connection
The settings page SHALL provide fields for Qdrant host, port, and collection name.

#### Scenario: User updates Qdrant settings
- **WHEN** the user enters a new Qdrant host, port, or collection name
- **AND** clicks "Save"
- **THEN** the values are persisted to Hivemind's config.yaml

### Requirement: Configure embedding model provider
The settings page SHALL provide fields for embedding provider (LM Studio, OpenAI, Ollama), model name, and endpoint URL.

#### Scenario: User updates embedding model settings
- **WHEN** the user selects a provider from the dropdown
- **AND** enters a model name and endpoint URL
- **AND** clicks "Save"
- **THEN** the values are persisted to Hivemind's config.yaml

### Requirement: Configure file watcher
The settings page SHALL provide a toggle for the file watcher and a debounce interval spinner.

#### Scenario: User updates watcher settings
- **WHEN** the user toggles the file watcher switch
- **AND** adjusts the debounce interval
- **AND** clicks "Save"
- **THEN** the values are persisted to Hivemind's config.yaml

### Requirement: Save and reset settings
The settings page SHALL provide Save and Reset toolbar actions with passive notification feedback.

#### Scenario: User saves settings
- **WHEN** the user clicks the Save action in the toolbar
- **THEN** a passive notification appears confirming settings were saved

#### Scenario: User resets to defaults
- **WHEN** the user clicks the Reset action in the toolbar
- **THEN** all fields revert to default values from the Hivemind config
- **AND** a passive notification confirms defaults were restored
