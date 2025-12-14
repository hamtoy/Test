// Neo4j Index Setup Script for shining-quasar
// Run this script in Neo4j browser or via cypher-shell to create indexes
// for frequently queried node properties.
// =============================================================================
// Entity Indexes
// =============================================================================
// Index for Entity name lookups (most common query pattern)
CREATE INDEX entity_name_idx IF NOT EXISTS
FOR (n:Entity)
ON (n.name);

// Index for Entity type filtering
CREATE INDEX entity_type_idx IF NOT EXISTS
FOR (n:Entity)
ON (n.type);

// =============================================================================
// Rule Indexes
// =============================================================================

// Index for Rule category filtering
CREATE INDEX rule_category_idx IF NOT EXISTS
FOR (n:Rule)
ON (n.category);

// Index for Rule type filtering
CREATE INDEX rule_type_idx IF NOT EXISTS
FOR (n:Rule)
ON (n.rule_type);

// Fulltext index for Rule descriptions (semantic search)
CREATE FULLTEXT INDEX rule_description_ft IF NOT EXISTS
FOR (n:Rule)
ON EACH [n.description, n.content];

// =============================================================================
// Constraint Indexes
// =============================================================================

// Index for Constraint category
CREATE INDEX constraint_category_idx IF NOT EXISTS
FOR (n:Constraint)
ON (n.category);

// =============================================================================
// Example Indexes
// =============================================================================

// Index for Example category
CREATE INDEX example_category_idx IF NOT EXISTS
FOR (n:Example)
ON (n.category);

// =============================================================================
// Relationship Property Indexes (Neo4j 5.0+)
// =============================================================================

// Index for relationship weights (if using weighted edges)
// CREATE INDEX rel_weight_idx IF NOT EXISTS
// FOR ()-[r:RELATED_TO]-() ON (r.weight);

// =============================================================================
// Usage Notes
// =============================================================================
//
// To run this script:
// 1. Neo4j Browser: Copy and paste the entire script
// 2. cypher-shell: cypher-shell -f scripts/setup_indexes.cypher
//
// To verify indexes were created:
// SHOW INDEXES;
//
// To drop an index if needed:
// DROP INDEX <index_name>;