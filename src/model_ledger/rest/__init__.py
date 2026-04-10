"""FastAPI REST API for model-ledger.

Wraps the 6 agent protocol tools as HTTP endpoints with
auto-generated OpenAPI docs at ``/docs``.

    >>> from model_ledger.rest.app import create_app
    >>> app = create_app()
"""

from model_ledger.rest.app import create_app

__all__ = ["create_app"]
