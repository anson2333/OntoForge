"""Actual Neo4j regressions; use only an isolated test database (fixtures erase it)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest

from backend.tests.test_integration import neo4j_container, neo4j_db  # noqa: F401
from backend.tests.test_ingestion_regressions import prepare  # noqa: F401
from backend.database import NodeRepository, EdgeRepository
from backend.schemas.nodes import WorkspaceNode
from backend.services.pdf_ingestion_service import commit_parsed_pdf


def workspace(db, name):
    now = datetime.now(timezone.utc)
    NodeRepository(db).create_workspace_node(WorkspaceNode(id=name, name=name, owner_id="alice", root_path="test",
                                                         created_at=now, last_modified_at=now))


def test_actual_database_cross_workspace_and_idempotence(neo4j_db, prepare):
    db = neo4j_db
    for name in ["workspace_a", "workspace_b"]:
        workspace(db, name)
    nodes, edges = NodeRepository(db), EdgeRepository(db)
    first, _ = prepare("workspace_a")
    second, _ = prepare("workspace_b")
    a = commit_parsed_pdf(first, nodes, edges)
    b = commit_parsed_pdf(second, nodes, edges)
    repeated = commit_parsed_pdf(second, nodes, edges)
    assert a.paper_id != b.paper_id
    assert b.assertions_created > 0 and repeated.assertions_created == 0
    assert db.execute_query("MATCH (:WorkspaceNode)-[:CONTAINS_PAPER]->(p:PaperNode) RETURN count(p) AS count")[0]["count"] == 2
    assert db.execute_query("MATCH (:ChunkNode)-[:EVIDENCED_BY]->(:AssertionNode) RETURN count(*) AS count")[0]["count"] > 0


def test_actual_database_rollback_on_edge_failure(neo4j_db, prepare, monkeypatch):
    workspace(neo4j_db, "workspace_a")
    nodes, edges = NodeRepository(neo4j_db), EdgeRepository(neo4j_db)
    request, _ = prepare()
    monkeypatch.setattr(edges, "create_evidenced_by_edge", lambda _: None)
    with pytest.raises(ValueError, match="endpoint missing"):
        commit_parsed_pdf(request, nodes, edges)
    assert neo4j_db.execute_query("MATCH (p:PaperNode) RETURN count(p) AS count")[0]["count"] == 0
    assert neo4j_db.execute_query("MATCH (c:ChunkNode) RETURN count(c) AS count")[0]["count"] == 0


def test_actual_database_concurrent_duplicate_commit(neo4j_db, prepare):
    workspace(neo4j_db, "workspace_a")
    request, _ = prepare()
    def commit(_):
        return commit_parsed_pdf(request, NodeRepository(neo4j_db), EdgeRepository(neo4j_db))
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(commit, range(2)))
    assert len({r.paper_id for r in results}) == 1
    assert sum(r.assertions_created for r in results) > 0
    assert neo4j_db.execute_query("MATCH (p:PaperNode) RETURN count(p) AS count")[0]["count"] == 1
