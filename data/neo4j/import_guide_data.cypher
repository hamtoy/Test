// Neo4j Cypher Script: Guide Data Import
// CSV: guide.csv
// Strategy: MERGE for deduplication, optimized relationships
// ===========================
// 1. Create Unique Constraints
// ===========================
CREATE CONSTRAINT unique_category_name IF NOT EXISTS
FOR (c:Category)
REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT unique_subcategory_path IF NOT EXISTS
FOR (s:Subcategory)
REQUIRE (s.categoryName, s.name) IS UNIQUE;

CREATE CONSTRAINT unique_item_path IF NOT EXISTS
FOR (i:Item)
REQUIRE (i.categoryName, i.subcategoryName, i.name) IS UNIQUE;

// ===========================
// 2. Load Data with MERGE
// ===========================

// Load Guide CSV
LOAD CSV WITH HEADERS FROM 'file:///guide.csv' AS row
WITH row
WHERE row.`대분류` IS NOT NULL AND trim(row.`대분류`) <> ''

// Merge Category (대분류)
MERGE (cat:Category {name: trim(row.`대분류`)})

// Merge Subcategory (중분류)
WITH cat, row
WHERE row.`중분류` IS NOT NULL AND trim(row.`중분류`) <> ''
MERGE (sub:Subcategory {categoryName: cat.name, name: trim(row.`중분류`)})

// Create relationship: Category -> Subcategory
MERGE (cat)-[:HAS_SUBCATEGORY]->(sub)

// Merge Item (소분류)
WITH cat, sub, row
WHERE row.`소분류` IS NOT NULL AND trim(row.`소분류`) <> ''
MERGE
  (item:Item
    {categoryName: cat.name, subcategoryName: sub.name, name: trim(row.`소분류`)})
SET item.content = row.`내용`

// Create relationship: Subcategory -> Item
MERGE (sub)-[:HAS_ITEM]->(item);

// ===========================
// 3. Create Indexes for Performance
// ===========================

CREATE INDEX category_name_idx IF NOT EXISTS
FOR (c:Category)
ON (c.name);

CREATE INDEX subcategory_name_idx IF NOT EXISTS
FOR (s:Subcategory)
ON (s.name);

CREATE INDEX item_name_idx IF NOT EXISTS
FOR (i:Item)
ON (i.name);