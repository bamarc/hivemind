## ADDED Requirements

### Requirement: Perform semantic search with text query
The system SHALL accept a natural language query and return semantically relevant code results from the indexed corpus.

#### Scenario: User enters a query and gets results
- **WHEN** the user types a query in the search field and presses Enter or clicks "Search"
- **THEN** the system performs a semantic search via the backend
- **AND** results appear in a CardsListView below the search bar

### Requirement: Display search results as cards
Each search result SHALL be displayed as a card showing: file path with line number, a content snippet, a relevance score, and the programming language.

#### Scenario: Search result card shows all fields
- **WHEN** search results are returned
- **THEN** each result card shows the file path and line number in monospace
- **AND** displays the matching content snippet
- **AND** shows a percentage relevance score
- **AND** shows the programming language label

### Requirement: Filter results by programming language
The system SHALL provide checkboxes to filter search results by programming language.

#### Scenario: User filters results by language
- **WHEN** the user unchecks a language filter (e.g., "JavaScript")
- **THEN** results of that language are hidden from the list
- **WHEN** the user re-checks that language filter
- **THEN** those results reappear
