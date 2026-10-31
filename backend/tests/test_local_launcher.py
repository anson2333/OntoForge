"""Lifecycle safeguards for the regular Windows double-click launcher."""
import argparse
import importlib.util
from pathlib import Path
import socket
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("local_launcher", Path(__file__).resolve().parents[2] / "scripts/local_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_occupied_port_is_detected():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        assert not launcher.port_free(occupied.getsockname()[1])


def test_cmd_entries_keep_windows_line_endings():
    for name in ["启动OntoForge.cmd", "停止OntoForge.cmd"]:
        content = (Path(__file__).resolve().parents[2] / name).read_bytes()
        assert content.startswith(b"@echo off\r\n")
        assert b"\n" not in content.replace(b"\r\n", b"")


def test_stop_never_terminates_reused_or_unknown_pid(monkeypatch):
    command = Mock()
    monkeypatch.setattr(launcher, "run", command)
    monkeypatch.setattr(launcher, "process_stamp", lambda _: 200)
    launcher.stop_process({"pid": 42, "created": 100})
    launcher.stop_process(None)
    command.assert_not_called()
    launcher.stop_process({"pid": 42, "created": 200})
    assert command.call_args.args[0] == ["taskkill", "/PID", "42", "/T", "/F"]


def test_repeated_start_opens_existing_page_without_starting_services(monkeypatch):
    state = {"url": "http://127.0.0.1:5173"}
    monkeypatch.setattr(launcher, "read_state", lambda: state)
    monkeypatch.setattr(launcher, "services_ready", lambda _: True)
    database, process, browser = Mock(), Mock(), Mock()
    monkeypatch.setattr(launcher, "ensure_database", database)
    monkeypatch.setattr(launcher, "launch", process)
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    launcher.start(argparse.Namespace(no_browser=False))
    database.assert_not_called()
    process.assert_not_called()
    browser.assert_called_once_with(state["url"])


def test_configuration_preserves_existing_env_and_data_paths(monkeypatch, tmp_path):
    source = 'NEO4J_URI=bolt://localhost:17687\nNEO4J_PASSWORD="test-password"\nONTOFORGE_USER_STORE=custom-users.json\n'
    (tmp_path / ".env").write_text(source, encoding="utf-8")
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    for key in ["NEO4J_URI", "NEO4J_PASSWORD", "ONTOFORGE_USER_STORE"]:
        monkeypatch.delenv(key, raising=False)
    env, backend, frontend = launcher.configuration(argparse.Namespace(backend_port=18765, frontend_port=15173))
    assert env["ONTOFORGE_USER_STORE"] == "custom-users.json"
    assert env["NEO4J_URI"] == "bolt://localhost:17687"
    assert env["VITE_ONTOFORGE_BACKEND_URL"] == "http://127.0.0.1:18765"
    assert (backend, frontend) == (18765, 15173)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == source


def test_failed_start_cleans_up_only_owned_processes(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    monkeypatch.setattr(launcher, "STATE", state)
    monkeypatch.setattr(launcher, "read_state", lambda: {})
    monkeypatch.setattr(launcher, "services_ready", lambda _: False)
    monkeypatch.setattr(launcher, "configuration", lambda _: ({}, 18001, 18002))
    monkeypatch.setattr(launcher, "port_free", lambda _: True)
    monkeypatch.setattr(launcher, "ensure_database", lambda _: None)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "node")
    monkeypatch.setattr(launcher, "launch", Mock(side_effect=[{"pid": 10, "created": 100}, RuntimeError("frontend launch failed")]))
    stopped = Mock()
    monkeypatch.setattr(launcher, "stop_process", stopped)
    with pytest.raises(RuntimeError, match="frontend launch failed"):
        launcher.start(argparse.Namespace(no_browser=True))
    assert any(call.args == ({"pid": 10, "created": 100},) for call in stopped.call_args_list)
    assert not state.exists()
