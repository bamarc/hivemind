## ADDED Requirements

### Requirement: List indexed repositories
The system SHALL display all repositories configured for indexing, showing each repo's name, path, indexing status, and chunk count.

#### Scenario: Repositories page shows all configured repos
- **WHEN** the user opens the Repositories page
- **THEN** the page displays a list of all configured repositories
- **AND** each entry shows the repo name, path, whether it is indexed, and chunk count

### Requirement: Add a new repository for indexing
The system SHALL allow the user to add a new repository by specifying its filesystem path and a chunker strategy.

#### Scenario: User adds a repo via the OverlaySheet dialog
- **WHEN** the user clicks the "Add Repository" action
- **THEN** an OverlaySheet opens with a path text field and chunker dropdown
- **WHEN** the user enters a valid path, selects a chunker, and clicks "Add & Index"
- **THEN** the repository is added to the config and indexing begins

### Requirement: Remove a repository
The system SHALL allow the user to remove a repository from the index.

#### Scenario: User removes a repo with confirmation
- **WHEN** the user clicks "Remove" on a repository entry
- **THEN** the repository is removed from the config and the list updates

### Requirement: Trigger re-indexing on a repository
The system SHALL allow the user to re-index an already-indexed repository.

#### Scenario: User re-indexes an existing repo
- **WHEN** the user clicks "Reindex" on an already-indexed repository
- **THEN** a new indexing run starts for that repository
- **AND** the indexing progress appears on the Indexer page
