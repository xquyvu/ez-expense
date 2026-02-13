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
from invoice_extractor import _is_azure_configured

model_bp = Blueprint("model", __name__)
logger = logging.getLogger(__name__)


@model_bp.route("/status", methods=["GET"])
async def model_status():
    """Return current model download/status info."""
    try:
        status = local_model_manager.get_model_status()
        return jsonify({"success": True, **status, "azure_configured": _is_azure_configured()})
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
