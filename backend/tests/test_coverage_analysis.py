"""Tests for entity normalization and method × scenario × metric coverage analysis."""

import json

import pytest

from backend.schemas.domain_pack import (
    DomainInfo,
    DomainPackConfig,
    MetricDefinition,
    TaxonomyDimension,
    ValidationRules,
)
from backend.server.app import app
from backend.tests.conftest import SyncASGIClient
from backend.services import auth_service
from backend.services.coverage_analysis import (
    analyze_workspace_coverage,
    build_assertion_rows,
    build_coverage_report,
    collect_dimensions,
    derive_method,
    derive_scenario,
)
from backend.services.normalization import (
    canonical_metric_from_subject,
    normalize_dimension_value,
    normalize_unit,
    resolve_metric_name,
)


@pytest.fixture
def config():
    return DomainPackConfig(
        schema_version="1.0",
        domain=DomainInfo(
            id="domain.networking.optical",
            name="Optical Networking",
            taxonomy_tree=[],
        ),
        core_metrics=[
            MetricDefinition(
                name="reconfiguration_delay",
                aliases=["switching_delay", "reconfiguration_time"],
                expected_unit="ms",
            ),
            MetricDefinition(
                name="insertion_loss",
                aliases=["optical_loss"],
                expected_unit="dB",
            ),
        ],
        validation=ValidationRules(
            required_context_keys=["topology"],
            unit_normalization={"ms": ["milliseconds", "msec"], "dB": ["decibels", "db"]},
        ),
    )


class TestEntityNormalization:
    def test_aliases_resolve_to_canonical_metric(self, config):
        assert resolve_metric_name("Switching Delay", config) == "reconfiguration_delay"
        assert resolve_metric_name("reconfiguration_time", config) == "reconfiguration_delay"
        assert resolve_metric_name("unknown_metric", config) is None

    def test_subject_prefix_is_stripped_before_resolution(self, config):
        assert (
            canonical_metric_from_subject("optical:optical_loss", config) == "insertion_loss"
        )

    def test_units_resolve_to_canonical_form(self, config):
        assert normalize_unit("milliseconds", config) == "ms"
        assert normalize_unit("db", config) == "dB"
        assert normalize_unit("", config, fallback="ms") == "ms"

    def test_dimension_values_are_snake_case(self):
        assert normalize_dimension_value("Access Network") == "access_network"
        assert normalize_dimension_value("  WDM ") == "wdm"
        assert normalize_dimension_value(None) == "unspecified"


class TestAssertionRows:
    def test_context_is_parsed_and_dimensions_derived(self, config):
        records = [
            {
                "assertion_id": "a1",
                "subject": "optical:switching_delay",
                "status": "pending",
                "context_conditions": json.dumps(
                    {"method": "WDM", "topology": "Access Network", "confidence": 0.8}
                ),
                "paper_id": "paper_1",
            }
        ]

        rows = build_assertion_rows(records, config)

        assert rows == [
            {
                "assertion_id": "a1",
                "paper_id": "paper_1",
                "metric": "reconfiguration_delay",
                "method": "wdm",
                "scenario": "access_network",
                "status": "pending",
            }
        ]

    def test_duplicate_assertion_records_are_deduplicated(self, config):
        record = {
            "assertion_id": "a1",
            "subject": "optical:insertion_loss",
            "context_conditions": {},
            "paper_id": "paper_1",
        }
        assert len(build_assertion_rows([record, dict(record)], config)) == 1

    def test_missing_context_falls_back_to_unspecified(self):
        assert derive_method({}) == "unspecified"
        assert derive_scenario({}) == "unspecified"
        assert derive_scenario({"topology": "ring"}) == "ring"


class TestCoverageReport:
    def _rows(self):
        return [
            {
                "assertion_id": "a1",
                "paper_id": "p1",
                "metric": "reconfiguration_delay",
                "method": "wdm",
                "scenario": "access_network",
                "status": "pending",
            },
            {
                "assertion_id": "a2",
                "paper_id": "p2",
                "metric": "reconfiguration_delay",
                "method": "wdm",
                "scenario": "metro_network",
                "status": "pending",
            },
        ]

    def test_matrix_counts_and_coverage_ratio(self):
        report = build_coverage_report(
            self._rows(),
            metrics=["reconfiguration_delay", "insertion_loss"],
            methods=["wdm", "optical_packet"],
            scenarios=["access_network", "metro_network"],
            gap_limit=10,
        )

        assert report["coverage"]["total_cells"] == 8
        assert report["coverage"]["covered_cells"] == 2
        assert report["coverage"]["ratio"] == 0.25
        assert report["coverage"]["by_metric"]["reconfiguration_delay"]["covered_cells"] == 2
        assert report["coverage"]["by_metric"]["insertion_loss"]["covered_cells"] == 0

        cells = {
            (row["method"], row["scenario"]): row["cells"] for row in report["matrix"]
        }
        assert cells[("wdm", "access_network")]["reconfiguration_delay"]["count"] == 1
        assert cells[("wdm", "access_network")]["reconfiguration_delay"]["paper_ids"] == ["p1"]

    def test_gaps_exclude_covered_cells_and_unspecified_dimensions(self):
        rows = self._rows() + [
            {
                "assertion_id": "a3",
                "paper_id": "p3",
                "metric": "insertion_loss",
                "method": "unspecified",
                "scenario": "access_network",
                "status": "pending",
            }
        ]
        report = build_coverage_report(
            rows,
            metrics=["reconfiguration_delay", "insertion_loss"],
            methods=["wdm", "optical_packet", "unspecified"],
            scenarios=["access_network", "metro_network"],
            gap_limit=100,
        )

        gap_keys = {(gap["method"], gap["scenario"], gap["metric"]) for gap in report["gaps"]}
        assert ("wdm", "access_network", "reconfiguration_delay") not in gap_keys
        assert ("optical_packet", "access_network", "reconfiguration_delay") in gap_keys
        assert all(gap["method"] != "unspecified" for gap in report["gaps"])

    def test_gap_scores_are_non_negative_and_ranked(self):
        report = build_coverage_report(
            self._rows(),
            metrics=["reconfiguration_delay", "insertion_loss"],
            methods=["wdm", "optical_packet"],
            scenarios=["access_network", "metro_network"],
            gap_limit=100,
        )

        scores = [gap["score"] for gap in report["gaps"]]
        assert scores
        assert all(score >= 1 for score in scores)
        assert scores == sorted(scores, reverse=True)
        assert all(gap["metric_demand"] >= 0 for gap in report["gaps"])
        assert all(gap["method_activity"] >= 0 for gap in report["gaps"])
        assert all(gap["scenario_activity"] >= 0 for gap in report["gaps"])

    def test_gap_limit_is_respected(self):
        report = build_coverage_report(
            [],
            metrics=["m1", "m2"],
            methods=["a", "b"],
            scenarios=["s1", "s2"],
            gap_limit=3,
        )
        assert len(report["gaps"]) == 3
        assert report["gap_count"] == 8


class FakeDb:
    """Minimal stand-in for Neo4jConnection used by coverage analysis."""

    def __init__(self, assertion_records, workspace_record=None):
        self.assertion_records = assertion_records
        self.workspace_record = workspace_record
        self.params_seen = []

    def execute_query(self, query, parameters=None):
        self.params_seen.append(parameters or {})
        if "WorkspaceNode" in query:
            return [{"w": self.workspace_record}] if self.workspace_record else []
        return list(self.assertion_records)


class TestAnalyzeWorkspaceCoverage:
    def test_query_is_scoped_to_workspace_and_namespace(self):
        db = FakeDb(
            [
                {
                    "assertion_id": "a1",
                    "subject": "optical:reconfiguration_delay",
                    "status": "pending",
                    "context_conditions": {"method": "wdm", "scenario": "access_network"},
                    "paper_id": "p1",
                }
            ]
        )

        report = analyze_workspace_coverage(
            db,
            "workspace_demo",
            None,
            metrics=["reconfiguration_delay"],
            methods=["wdm"],
            scenarios=["access_network"],
        )

        assert report["coverage"]["covered_cells"] == 1
        assert db.params_seen[-1] == {"workspace_id": "workspace_demo"}

    def test_namespace_filter_is_applied(self):
        db = FakeDb([])
        analyze_workspace_coverage(
            db,
            "workspace_demo",
            "optical",
            metrics=["reconfiguration_delay"],
            methods=["wdm"],
            scenarios=["access_network"],
        )
        assert db.params_seen[-1] == {
            "workspace_id": "workspace_demo",
            "namespace": "optical",
        }


class TestCoverageRpc:
    @pytest.fixture
    def client(self):
        return SyncASGIClient(app)

    def _register_and_login(self, client):
        client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "authRegister",
                "params": {"username": "coverage_user", "password": "coverage-pass-1"},
                "id": 1,
            },
        )
        login = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "authLogin",
                "params": {"username": "coverage_user", "password": "coverage-pass-1"},
                "id": 2,
            },
        )
        return login.json()["result"]

    def test_requires_authentication(self, client):
        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "getCoverageAnalysis",
                "params": {"workspace_id": "workspace_demo"},
                "id": 3,
            },
        )
        assert response.json()["error"]["code"] == auth_service.CODE_AUTH_REQUIRED

    def test_returns_coverage_for_accessible_workspace(self, client, monkeypatch):
        session = self._register_and_login(client)
        user_id = session["user"]["user_id"]
        db = FakeDb(
            [
                {
                    "assertion_id": "a1",
                    "subject": "optical:reconfiguration_delay",
                    "status": "pending",
                    "context_conditions": {"method": "wdm", "scenario": "access_network"},
                    "paper_id": "p1",
                }
            ],
            workspace_record={
                "id": "workspace_demo",
                "name": "Demo",
                "owner_id": user_id,
                "metadata": {"members": {}},
            },
        )
        monkeypatch.setattr("backend.server.jsonrpc_methods.get_db", lambda: db)

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "getCoverageAnalysis",
                "params": {
                    "workspace_id": "workspace_demo",
                    "metrics": ["reconfiguration_delay"],
                    "methods": ["wdm", "optical_packet"],
                    "scenarios": ["access_network"],
                },
                "id": 4,
            },
            headers={"Authorization": f"Bearer {session['token']}"},
        )

        payload = response.json()
        assert "result" in payload, payload
        coverage = payload["result"]["coverage"]
        assert coverage["coverage"]["covered_cells"] == 1
        assert coverage["gaps"][0]["method"] == "optical_packet"

    def test_gap_candidates_requires_membership(self, client, monkeypatch):
        session = self._register_and_login(client)
        db = FakeDb(
            [],
            workspace_record={
                "id": "workspace_private",
                "name": "Private",
                "owner_id": "user_someone_else",
                "metadata": {"members": {}},
            },
        )
        monkeypatch.setattr("backend.server.jsonrpc_methods.get_db", lambda: db)

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "getGapCandidates",
                "params": {"workspace_id": "workspace_private"},
                "id": 5,
            },
            headers={"Authorization": f"Bearer {session['token']}"},
        )

        assert response.json()["error"]["code"] == auth_service.CODE_FORBIDDEN


class EvidenceDb:
    """Fake DB that serves workspace, evidence and domain-pack queries."""

    def __init__(self, owner_id):
        self.owner_id = owner_id

    def execute_query(self, query, parameters=None):
        if "WorkspaceNode" in query:
            return [
                {
                    "w": {
                        "id": "workspace_demo",
                        "name": "Demo",
                        "owner_id": self.owner_id,
                        "metadata": {"members": {}},
                    }
                }
            ]
        return [
            {
                "assertion_id": "paper_1::assert_llm_reconfiguration_delay_b0_0",
                "value": "12.5",
                "unit": "ms",
                "status": "pending",
                "context_conditions": json.dumps({"confidence": 0.93}),
                "evidence_id": "paper_1::chunk_p1_0",
                "labels": ["ChunkNode"],
                "raw_text": "The reconfiguration delay is 12.5 ms.",
                "latex_string": None,
                "bounding_box": json.dumps({"page": 1, "x": 0, "y": 0, "width": 10, "height": 10}),
                "confidence": 0.93,
            }
        ]


class TestEvidenceAndDomainPackRpc:
    @pytest.fixture
    def client(self):
        return SyncASGIClient(app)

    def _login(self, client):
        client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "authRegister",
                "params": {"username": "evidence_user", "password": "evidence-pass-1"},
                "id": 1,
            },
        )
        login = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "authLogin",
                "params": {"username": "evidence_user", "password": "evidence-pass-1"},
                "id": 2,
            },
        )
        return login.json()["result"]

    def test_get_evidence_returns_chunks(self, client, monkeypatch):
        session = self._login(client)
        db = EvidenceDb(session["user"]["user_id"])
        monkeypatch.setattr("backend.server.jsonrpc_methods.get_db", lambda: db)

        response = client.post(
            "/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "getEvidence",
                "params": {
                    "workspace_id": "workspace_demo",
                    "paper_id": "paper_1",
                    "metric_name": "optical:reconfiguration_delay",
                },
                "id": 3,
            },
            headers={"Authorization": f"Bearer {session['token']}"},
        )

        result = response.json()["result"]
        assert result["assertion"]["value"] == "12.5"
        assert result["evidence"] == [
            {
                "id": "paper_1::chunk_p1_0",
                "type": "chunk",
                "text": "The reconfiguration delay is 12.5 ms.",
                "confidence": 0.93,
                "bounding_box": {"page": 1, "x": 0, "y": 0, "width": 10, "height": 10},
            }
        ]

    def test_list_domain_packs_returns_backend_config(self, client):
        session = self._login(client)
        response = client.post(
            "/jsonrpc",
            json={"jsonrpc": "2.0", "method": "listDomainPacks", "params": {}, "id": 4},
            headers={"Authorization": f"Bearer {session['token']}"},
        )

        packs = response.json()["result"]["domain_packs"]
        assert packs
        optical = next(pack for pack in packs if pack["namespace"] == "optical")
        assert any(metric["name"] == "reconfiguration_delay" for metric in optical["config"]["core_metrics"])


class TestDomainPackResolution:
    def test_namespace_selects_matching_pack(self):
        from backend.services.pdf_ingestion_service import load_domain_pack_config

        optical = load_domain_pack_config("optical")
        wireless = load_domain_pack_config("wireless")

        assert optical is not None
        assert optical.domain.id == "domain.networking.optical"
        assert wireless is not None
        assert wireless.domain.id == "domain.networking.wireless"
        assert any(metric.name == "latency" for metric in wireless.core_metrics)

    def test_unknown_namespace_returns_none(self):
        from backend.services.pdf_ingestion_service import load_domain_pack_config

        assert load_domain_pack_config("quantum_networking") is None

    def test_technology_dimension_declares_methods(self):
        config = DomainPackConfig(
            schema_version="1.0",
            domain=DomainInfo(
                id="domain.networking.wireless",
                name="Wireless",
                taxonomy_tree=[
                    TaxonomyDimension(
                        name="technology",
                        values=["Beamforming", "MIMO"],
                    )
                ],
            ),
            core_metrics=[MetricDefinition(name="latency", expected_unit="ms")],
            validation=ValidationRules(required_context_keys=[], unit_normalization={}),
        )

        dimensions = collect_dimensions(config, [])

        assert dimensions["methods"] == ["beamforming", "mimo"]
