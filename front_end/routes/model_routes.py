"""
Model management API routes for local LLM model lifecycle.
"""

import asyncio
import json
import logging
import os
import sys

from quart import Blueprint, jsonify, make_response

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import local_model_manager
from invoice_extractor import (
    _copilot_cli_path,
    _get_copilot_auth_status,
    _is_azure_configured,
    _is_copilot_available,
    _reset_copilot_client,
    _resolve_extraction_provider,
)

model_bp = Blueprint("model", __name__)
logger = logging.getLogger(__name__)


@model_bp.route("/status", methods=["GET"])
async def model_status():
    """Return current model download/status info."""
    try:
        status = local_model_manager.get_model_status()
        copilot_installed = _is_copilot_available()
        copilot_authed = False
        copilot_login = None
        if copilot_installed:
            try:
                auth = await asyncio.wait_for(_get_copilot_auth_status(), timeout=20)
                copilot_authed = auth.get("authenticated", False)
                copilot_login = auth.get("login")
            except Exception as e:
                logger.warning(f"Copilot auth check skipped: {e}")
        return jsonify(
            {
                "success": True,
                **status,
                "azure_configured": _is_azure_configured(),
                "copilot_installed": copilot_installed,
                "copilot_available": copilot_installed and copilot_authed,
                "copilot_login": copilot_login,
                "extraction_provider": _resolve_extraction_provider(),
            }
        )
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        return jsonify({"error": "Failed to get model status", "message": str(e)}), 500


@model_bp.route("/download", methods=["POST"])
async def model_download():
    """Download the model, streaming progress via SSE."""

    async def generate():
        yield 'data: {"status": "starting"}\n\n'
        try:
            # Run the blocking download in a thread
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, local_model_manager.download_model)
            status = local_model_manager.get_model_status()
            yield f"data: {json.dumps({**status, 'status': 'complete'})}\n\n"
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    response = await make_response(generate(), 200)
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    return response


@model_bp.route("/delete", methods=["DELETE"])
async def model_delete():
    """Delete the downloaded model files."""
    try:
        local_model_manager.delete_model()
        return jsonify({"success": True, "message": "Model deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        return jsonify({"error": "Failed to delete model", "message": str(e)}), 500


@model_bp.route("/copilot-login", methods=["POST"])
async def copilot_login():
    """Run `copilot login` (GitHub OAuth device flow), streaming output via SSE."""

    async def generate():
        yield 'data: {"status": "starting"}\n\n'
        try:
            cli = _copilot_cli_path()
            if not cli:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Copilot CLI not found'})}\n\n"
                return
            proc = await asyncio.create_subprocess_exec(
                cli,
                "login",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
            )
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield f"data: {json.dumps({'line': line})}\n\n"
            await proc.wait()

            # Re-spawn the client so it picks up the freshly stored token.
            await _reset_copilot_client()
            auth = await _get_copilot_auth_status(force_refresh=True)
            yield "data: " + json.dumps(
                {
                    "status": "complete",
                    "authenticated": auth.get("authenticated", False),
                    "login": auth.get("login"),
                }
            ) + "\n\n"
        except FileNotFoundError:
            yield f"data: {json.dumps({'status': 'error', 'message': 'copilot CLI not found on PATH'})}\n\n"
        except Exception as e:
            logger.error(f"Copilot login error: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    response = await make_response(generate(), 200)
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    return response
