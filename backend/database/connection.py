"""
Neo4j Database Connection Manager
Handles connection pooling and session management.
"""

from typing import Optional
from neo4j import GraphDatabase, Driver, Session
from contextlib import contextmanager
from contextvars import ContextVar


class Neo4jConnection:
    """Manages Neo4j database connection and provides session context."""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Database username
            password: Database password
        """
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: Optional[Driver] = None
        self._transaction = ContextVar(f"neo4j_transaction_{id(self)}", default=None)

    def connect(self) -> None:
        """Establish connection to Neo4j database."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password)
            )

    def close(self) -> None:
        """Close database connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def verify_connectivity(self) -> bool:
        """
        Test database connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    @contextmanager
    def session(self, database: str = "neo4j") -> Session:
        """
        Context manager for database sessions.

        Args:
            database: Database name (default: "neo4j")

        Yields:
            Neo4j session

        Example:
            with db.session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 1")
        """
        if self._driver is None:
            raise RuntimeError("Database connection not established. Call connect() first.")

        session = self._driver.session(database=database)
        try:
            yield session
        finally:
            session.close()

    def execute_query(self, query: str, parameters: dict = None, database: str = "neo4j"):
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters (optional)
            database: Database name

        Returns:
            List of records from query result
        """
        transaction = self._transaction.get()
        if transaction is not None:
            return [record.data() for record in transaction.run(query, parameters or {})]
        with self.session(database=database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    @contextmanager
    def transaction(self, database: str = "neo4j"):
        """Make repository calls on this connection part of one atomic write."""
        if self._transaction.get() is not None:
            raise RuntimeError("Nested graph transactions are not supported")
        with self.session(database) as session:
            tx = session.begin_transaction()
            token = self._transaction.set(tx)
            try:
                yield self
                tx.commit()
            except BaseException:
                tx.rollback()
                raise
            finally:
                self._transaction.reset(token)
                tx.close()

    def execute_write(self, query: str, parameters: dict = None, database: str = "neo4j"):
        """
        Execute a write transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters (optional)
            database: Database name

        Returns:
            Query result summary
        """
        with self.session(database=database) as session:
            result = session.run(query, parameters or {})
            return result.consume()


# Global connection instance (initialized in server startup)
_db_connection: Optional[Neo4jConnection] = None


def get_db() -> Neo4jConnection:
    """
    Get the global database connection instance.

    Returns:
        Neo4jConnection instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_connection


def init_db(uri: str, user: str, password: str) -> Neo4jConnection:
    """
    Initialize global database connection.

    Args:
        uri: Neo4j connection URI
        user: Database username
        password: Database password

    Returns:
        Neo4jConnection instance
    """
    global _db_connection
    _db_connection = Neo4jConnection(uri, user, password)
    _db_connection.connect()
    return _db_connection


def close_db() -> None:
    """Close global database connection."""
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
