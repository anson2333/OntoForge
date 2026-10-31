"""Full JSON-RPC flow against an isolated Neo4j database, using a synthetic PDF."""
import base64

from backend.server.app import app
from backend.tests.conftest import SyncASGIClient
from backend.tests.test_auth import _rpc, _register_and_login
from backend.tests.test_integration import neo4j_db, neo4j_container  # noqa: F401
from backend.tests.test_llm_foundation import _build_single_page_text_pdf


def test_two_user_pdf_preview_commit_and_evidence(neo4j_db, tmp_path, monkeypatch):
    monkeypatch.setenv("ONTOFORGE_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("ONTOFORGE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("ONTOFORGE_LLM_PROVIDER", "disabled")
    client = SyncASGIClient(app)
    alice = _register_and_login(client, "alice")
    bob = _register_and_login(client, "bob")

    def rpc(method, params, user=alice):
        return _rpc(client, method, params, token=user["token"]).json()

    workspace = rpc("createWorkspace", {"name": "API acceptance", "root": "test"})["result"]["workspace"]
    workspace_id = workspace["id"]
    raw = _build_single_page_text_pdf(["The reconfiguration delay is 12.5 ms."])
    upload = rpc("uploadPdf", {"workspace_id": workspace_id, "file_name": "synthetic-regression.pdf",
        "content_base64": base64.b64encode(raw).decode()})["result"]
    params = {"workspace_id": workspace_id, "domain_pack_namespace": "optical", "upload_id": upload["upload_id"]}
    preview = rpc("parsePdfWithDomainPack", params)["result"]
    assert preview["assertion_extraction_method"] == "heuristic"
    assert preview["assertions"]
    params["preview_id"] = preview["preview_id"]
    committed = rpc("commitParsedPdf", params)["result"]
    assert committed["assertions_created"] > 0
    assert committed["extraction_run_id"].startswith("run_")
    assert committed["experiments_created"] > 0
    assert committed["measurements_created"] > 0

    experiments = rpc("getExperiments", {"workspace_id": workspace_id})["result"]
    assert experiments["count"] > 0
    ontology_experiment = experiments["experiments"][0]
    assert ontology_experiment["measurements"]
    subgraph = rpc("getEntitySubgraph", {
        "workspace_id": workspace_id,
        "entity_id": ontology_experiment["experiment"]["id"],
    })["result"]["subgraph"]
    assert subgraph["root"]["id"] == ontology_experiment["experiment"]["id"]
    assert subgraph["edges"]

    second_preview = rpc("parsePdfWithDomainPack", {
        "workspace_id": workspace_id,
        "domain_pack_namespace": "optical",
        "upload_id": upload["upload_id"],
    })["result"]
    second_commit = rpc("commitParsedPdf", {
        "workspace_id": workspace_id,
        "domain_pack_namespace": "optical",
        "upload_id": upload["upload_id"],
        "preview_id": second_preview["preview_id"],
    })["result"]
    assert second_commit["paper_id"] == committed["paper_id"]
    assert second_commit["extraction_run_id"] != committed["extraction_run_id"]
    assert second_commit["assertions_created"] == 0
    active_experiments = rpc("getExperiments", {"workspace_id": workspace_id})["result"]
    assert active_experiments["count"] == experiments["count"]
    assert all(
        item["experiment"]["extraction_run_id"] == second_commit["extraction_run_id"]
        for item in active_experiments["experiments"]
    )

    analysis = rpc("analyzeResearchGaps", {"workspace_id": workspace_id})["result"]["analysis"]
    assert analysis["input_counts"]["total"] > 0
    assert analysis["input_counts"]["trusted"] == 0
    assert analysis["candidate_count"] == 0

    resolution = rpc("resolveEntityMentions", {
        "workspace_id": workspace_id,
        "domain_pack_namespace": "cv_detection",
        "mentions": [{
            "id": "mention_vgg", "text": "VGG-16", "entity_type": "Backbone",
            "evidence_ids": [], "context": {},
        }],
    })["result"]["decisions"][0]
    assert resolution["decision"] == "same_entity"
    review = rpc("reviewResolution", {
        "workspace_id": workspace_id,
        "decision_id": resolution["id"],
        "action": "retract",
        "reason": "integration test rollback",
    })["result"]
    assert review["decision"]["active"] is False
    source_params = {"workspace_id": workspace_id, "paper_id": committed["paper_id"]}
    preserved = rpc("getPaperSource", source_params)["result"]
    assert base64.b64decode(preserved["content_base64"]) == raw
    assert rpc("getPaperSource", source_params, user=bob)["error"]["code"] == -32003
    assert rpc("commitParsedPdf", params)["result"]["assertions_created"] == 0
    still_active = rpc("getExperiments", {"workspace_id": workspace_id})["result"]
    assert all(
        item["experiment"]["extraction_run_id"] == second_commit["extraction_run_id"]
        for item in still_active["experiments"]
    )
    evidence = rpc("getEvidence", {"workspace_id": workspace_id, "paper_id": committed["paper_id"],
        "metric_name": "optical:reconfiguration_delay"})["result"]
    assert evidence  # actual DB evidence, not a browser fixture
    evidence_id = evidence["evidence"][0]["id"]
    assert evidence["evidence"][0]["verification_status"] == "raw"
    verified = rpc("sspVerifyNode", {"params": {"node_id": evidence_id, "action": "approve", "verified_by": "session"}})
    assert "result" in verified, verified
    reloaded = rpc("getEvidence", {"workspace_id": workspace_id, "paper_id": committed["paper_id"],
        "metric_name": "optical:reconfiguration_delay"})["result"]
    assert reloaded["evidence"][0]["verification_status"] == "verified"
    assert rpc("getPapers", {"workspace_id": workspace_id}, user=bob)["error"]["code"] == -32003
    assert rpc("getExperiments", {"workspace_id": workspace_id}, user=bob)["error"]["code"] == -32003
    bob_workspace = rpc("createWorkspace", {"name": "Bob", "root": "test"}, user=bob)["result"]["workspace"]
    foreign = rpc("commitParsedPdf", {**params, "workspace_id": bob_workspace["id"]}, user=bob)
    assert foreign["error"]["code"] == -32003
    assert "error" in _rpc(client, "getPapers", {"workspace_id": workspace_id}).json()
