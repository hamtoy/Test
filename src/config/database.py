"""Database Configuration Settings.

Handles Neo4j (graph database) and Redis (message queue) configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettingsMixin(BaseSettings):
    """Database configuration settings (Mixin).

    Handles Neo4j (graph database) and Redis (message queue) configuration.
    """

    neo4j_uri: str | None = Field(None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(None, alias="NEO4J_PASSWORD")
    redis_url: str = Field(
        "redis://localhost:6379",
        alias="REDIS_URL",
        description="Redis URL for FastStream",
    )
