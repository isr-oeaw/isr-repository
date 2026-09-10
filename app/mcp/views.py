"""Stateless Streamable HTTP MCP endpoint."""

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .auth import authenticate_request
from .tools import McpToolError, TOOL_DEFINITIONS, call_tool

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = '2024-11-05'
SERVER_NAME = 'isr-repository'
SERVER_VERSION = '1.0.0'


def _jsonrpc_error(request_id, code, message):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': {
            'code': code,
            'message': message,
        },
    }


def _jsonrpc_result(request_id, result):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'result': result,
    }


def _tool_result_payload(text, *, is_error=False):
    return {
        'content': [{'type': 'text', 'text': text}],
        'isError': is_error,
    }


def _handle_initialize(params):
    return {
        'protocolVersion': MCP_PROTOCOL_VERSION,
        'capabilities': {
            'tools': {},
        },
        'serverInfo': {
            'name': SERVER_NAME,
            'version': SERVER_VERSION,
        },
    }


def _handle_tools_list():
    return {'tools': TOOL_DEFINITIONS}


def _handle_tools_call(user, params):
    if not isinstance(params, dict):
        raise ValueError('tools/call params must be an object.')

    name = params.get('name')
    if not name:
        raise ValueError('tools/call requires name.')

    arguments = params.get('arguments') or {}
    if not isinstance(arguments, dict):
        raise ValueError('tools/call arguments must be an object.')

    try:
        text = call_tool(user, name, arguments)
        return _tool_result_payload(text, is_error=False)
    except McpToolError as exc:
        return _tool_result_payload(exc.message, is_error=True)


@csrf_exempt
@require_http_methods(['GET', 'POST', 'DELETE'])
def mcp_endpoint(request):
    if request.method == 'GET':
        return HttpResponse(
            'MCP endpoint. Send JSON-RPC POST requests with an API key.',
            status=405,
            content_type='text/plain',
        )

    if request.method == 'DELETE':
        return HttpResponse(status=204)

    user = authenticate_request(request)
    if user is None:
        return JsonResponse(
            {'error': 'Authentication required. Provide a valid API key.'},
            status=401,
        )

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse(_jsonrpc_error(None, -32700, 'Parse error'), status=400)

    if not isinstance(payload, dict):
        return JsonResponse(_jsonrpc_error(None, -32600, 'Invalid Request'), status=400)

    request_id = payload.get('id')
    method = payload.get('method')
    params = payload.get('params') or {}

    if payload.get('jsonrpc') != '2.0' or not method:
        response = _jsonrpc_error(request_id, -32600, 'Invalid Request')
        return JsonResponse(response, status=400)

    if method.startswith('notifications/'):
        return HttpResponse(status=204)

    try:
        if method == 'initialize':
            result = _handle_initialize(params)
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = _handle_tools_list()
        elif method == 'tools/call':
            result = _handle_tools_call(user, params)
        else:
            response = _jsonrpc_error(request_id, -32601, f'Method not found: {method}')
            return JsonResponse(response, status=404)
    except ValueError as exc:
        response = _jsonrpc_error(request_id, -32602, str(exc))
        return JsonResponse(response, status=400)
    except Exception:
        logger.exception('Unhandled MCP error for method %s', method)
        response = _jsonrpc_error(request_id, -32603, 'Internal error')
        return JsonResponse(response, status=500)

    return JsonResponse(_jsonrpc_result(request_id, result))
