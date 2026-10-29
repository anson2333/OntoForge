"""
SSP Server Package
JSON-RPC 2.0 server implementation for Scientific Service Protocol.
"""

from . import jsonrpc_methods
from .app import app

__all__ = ["jsonrpc_methods", "app"]
