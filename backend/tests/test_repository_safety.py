"""Safety regression tests for graph repository operations."""

from backend.database.node_repository import NodeRepository


class RecordingDatabase:
    def __init__(self):
        self.query = ""
        self.parameters = {}

    def execute_query(self, query, parameters=None):
        self.query = query
        self.parameters = parameters or {}
        return [{"deleted_count": 1}]


def test_workspace_delete_is_bounded_to_owned_paper_hierarchy():
    database = RecordingDatabase()
    repository = NodeRepository(database)

    assert repository.delete_workspace_node("workspace-a") is True
    assert database.parameters == {"workspace_id": "workspace-a"}
    assert "[:CONTAINS_PAPER]" in database.query
    assert "[:CONTAINS]" in database.query
    assert "-[r1*]-" not in database.query
