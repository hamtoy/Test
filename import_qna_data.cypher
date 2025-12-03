// Neo4j Cypher Script: QnA Data Import
// CSV: qna.csv
// Strategy: MERGE for deduplication, optimized relationships
// ===========================
// 1. Create Unique Constraints
// ===========================
CREATE CONSTRAINT unique_qa_category_name IF NOT EXISTS
FOR (c:QACategory)
REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT unique_qa_subcategory_path IF NOT EXISTS
FOR (s:QASubcategory)
REQUIRE (s.categoryName, s.name) IS UNIQUE;

CREATE CONSTRAINT unique_qa_topic_path IF NOT EXISTS
FOR (t:QATopic)
REQUIRE (t.categoryName, t.subcategoryName, t.name) IS UNIQUE;

// ===========================
// 2. Load Data with MERGE
// ===========================

// Load QnA CSV
LOAD CSV WITH HEADERS FROM 'file:///qna.csv' AS row
WITH row
WHERE row.`대분류` IS NOT NULL AND trim(row.`대분류`) <> ''

// Merge QA Category (대분류)
MERGE (cat:QACategory {name: trim(row.`대분류`)})

// Merge QA Subcategory (중분류)
WITH cat, row
WHERE row.`중분류` IS NOT NULL AND trim(row.`중분류`) <> ''
MERGE (sub:QASubcategory {categoryName: cat.name, name: trim(row.`중분류`)})

// Create relationship: QACategory -> QASubcategory
MERGE (cat)-[:HAS_SUBCATEGORY]->(sub)

// Merge QA Topic (소분류)
WITH cat, sub, row
WHERE row.`소분류` IS NOT NULL AND trim(row.`소분류`) <> ''
MERGE
  (topic:QATopic
    {categoryName: cat.name, subcategoryName: sub.name, name: trim(row.`소분류`)})
SET topic.content = row.`내용`

// Create relationship: QASubcategory -> QATopic
MERGE (sub)-[:HAS_TOPIC]->(topic);

// ===========================
// 3. Create Indexes for Performance
// ===========================

CREATE INDEX qa_category_name_idx IF NOT EXISTS
FOR (c:QACategory)
ON (c.name);

CREATE INDEX qa_subcategory_name_idx IF NOT EXISTS
FOR (s:QASubcategory)
ON (s.name);

CREATE INDEX qa_topic_name_idx IF NOT EXISTS
FOR (t:QATopic)
ON (t.name);

// ===========================
// 4. Optional: Link Related Topics
// ===========================

// Example: Link topics with similar keywords (can be customized)
MATCH (t1:QATopic), (t2:QATopic)
WHERE
  id(t1) < id(t2) AND
  t1.name = t2.name AND
  t1.subcategoryName <> t2.subcategoryName
MERGE (t1)-[:RELATED_TO]-(t2);