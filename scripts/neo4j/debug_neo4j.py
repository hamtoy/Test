import os
import sys

sys.path.append(os.getcwd())

from neo4j import GraphDatabase

from src.config.settings import AppConfig

print("Start debug script", flush=True)

try:
    config = AppConfig()
    print("Config loaded", flush=True)
except Exception as e:
    print(f"Config error: {e}", flush=True)
    sys.exit(1)

uri = config.neo4j_uri
user = config.neo4j_user
password = config.neo4j_password

print(f"URI: {uri}", flush=True)

if not uri or not user or not password:
    print("Missing Neo4j configuration (uri/user/password)", flush=True)
    sys.exit(1)

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("Connection verified", flush=True)
except Exception as e:
    print(f"Connection failed: {e}", flush=True)
    sys.exit(1)

print("Defining query...", flush=True)
query = "RETURN 1 as val"

print("Running query...", flush=True)
with driver.session() as session:
    result = session.run(query)
    record = result.single()
    if record is None:
        print("No result returned", flush=True)
    else:
        print(f"Result: {record[0]}", flush=True)

print("End debug script", flush=True)
driver.close()
