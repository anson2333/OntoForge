"""
FastAPI Server for SSP JSON-RPC 2.0 Protocol
HTTP transport for Scientific Service Protocol.
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from jsonrpcserver import async_dispatch, dispatch
from dotenv import load_dotenv

# Import methods to register them
from backend.server import jsonrpc_methods  # noqa: F401
from backend.database import init_db, close_db


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

QUIET_JSONRPC_METHODS = {"getLLMStatus"}

# Create FastAPI app
app = FastAPI(
    title="OntoForge SSP Server",
    description="Scientific Service Protocol JSON-RPC 2.0 Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "null",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    try:
        db = init_db(neo4j_uri, neo4j_user, neo4j_password)
        if db.verify_connectivity():
            print(f"✅ Connected to Neo4j at {neo4j_uri}")
        else:
            print(f"⚠️  Neo4j connection verification failed")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        print("⚠️  Server starting without database connection")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    close_db()
    print("✅ Database connection closed")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "OntoForge SSP Server",
        "version": "1.0.0",
        "protocol": "JSON-RPC 2.0",
        "methods": [
            "sspInitialize",
            "sspIngest",
            "sspExtract",
            "sspQuery",
            "parseUserIntent",
            "listWorkspaces",
            "getWorkspace",
            "createWorkspace",
            "getPapers",
            "getAssertions",
            "bootstrapDomainPack",
            "validateDomainPack",
            "uploadPdf",
            "parsePdfWithDomainPack",
            "commitParsedPdf",
            "getLLMStatus",
            "listAgentCapabilities",
        ],
    }


@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: Request) -> Response:
    """
    JSON-RPC 2.0 endpoint.

    Handles all SSP method calls via POST requests.
    """
    try:
        # Get request body
        body = await request.body()
        request_text = body.decode()
        request_json = json.loads(request_text)

        method_name = request_json.get("method") if isinstance(request_json, dict) else "<unknown>"
        request_id = request_json.get("id") if isinstance(request_json, dict) else "<no-id>"
        params = request_json.get("params", {}) if isinstance(request_json, dict) else {}
        should_log_rpc = method_name not in QUIET_JSONRPC_METHODS
        
        # Sanitize params for logging (hide sensitive data)
        sanitized_params = params
        if isinstance(params, dict):
            sanitized_params = {
                k: ("<binary>" if isinstance(v, bytes) else 
                    ("<file>" if k == "file_content" else 
                     (str(v)[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)))
                for k, v in params.items()
            }
        
        if should_log_rpc:
            print(f"\n📥 JSON-RPC Request [id={request_id}]")
            print(f"   Method: {method_name}")
            params_str = json.dumps(sanitized_params, indent=2)
            if len(params_str) > 500:
                print(f"   Params: {params_str[:500]}...")
            else:
                print(f"   Params: {params_str}")

        # Dispatch based on method type
        if method_name == "parseUserIntent":
            response = await async_dispatch(request_text)
        else:
            response = dispatch(request_text)

        # Log response
        try:
            response_json = json.loads(response)
            if "result" in response_json:
                if should_log_rpc:
                    result_str = str(response_json["result"])
                    print(f"✅ JSON-RPC Response [id={request_id}]")
                    print(f"   Method: {method_name}")
                    if len(result_str) > 300:
                        print(f"   Result: {result_str[:300]}...")
                    else:
                        print(f"   Result: {result_str}")
            elif "error" in response_json:
                print(f"❌ JSON-RPC Error [id={request_id}]")
                print(f"   Method: {method_name}")
                print(f"   Error: {json.dumps(response_json['error'], indent=2)}")
        except:
            pass  # If response parsing fails, skip logging

        # jsonrpcserver.dispatch already returns a serialized JSON string.
        return Response(content=response, media_type="application/json", status_code=200)
    except json.JSONDecodeError as e:
        print(f"❌ JSON-RPC Invalid JSON: {str(e)}")
        error_response = json.dumps(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}
        )
        return Response(content=error_response, media_type="application/json", status_code=200)
    except Exception as e:
        print(f"❌ JSON-RPC Internal Error: {str(e)}")
        import traceback
        traceback.print_exc()
        error_response = json.dumps(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Internal error: {str(e)}"}, "id": None}
        )
        return Response(content=error_response, media_type="application/json", status_code=500)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns server status and database connectivity.
    """
    from backend.database import get_db

    try:
        db = get_db()
        db_connected = db.verify_connectivity()
    except Exception:
        db_connected = False

    return {
        "status": "healthy" if db_connected else "degraded",
        "database": "connected" if db_connected else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.server.app:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        log_level="info",
    )
