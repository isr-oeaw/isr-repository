"""Authentication helpers for the MCP endpoint."""

from user.authentication import APIKeyBackend


def authenticate_request(request):
    """Return the user authenticated via API key, or None."""
    backend = APIKeyBackend()
    return backend.authenticate(request)
