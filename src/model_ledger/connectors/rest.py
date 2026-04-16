"""rest_connector — config-driven REST API model discovery.

Returns a SourceConnector that queries a REST API and maps JSON items to DataNodes.
"""

from __future__ import annotations

from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from model_ledger.graph.models import DataNode, DataPort


def _get_nested(data: dict, path: str) -> Any:
    """Navigate a dot-separated path into nested dicts."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def rest_connector(
    *,
    name: str,
    url: str,
    items_path: str,
    name_field: str,
    headers: dict[str, str] | None = None,
    input_fields: list[str] | None = None,
    output_fields: list[str] | None = None,
    metadata_fields: dict[str, str] | None = None,
    pagination: dict[str, str] | None = None,
) -> _RESTConnector:
    """Create a SourceConnector that discovers models from a REST API.

    Args:
        name: Platform name for discovered DataNodes.
        url: API endpoint URL.
        items_path: Dot-path to the array of items in JSON response.
        name_field: Field containing the model name.
        headers: HTTP headers (auth goes here).
        input_fields: Dot-paths to input identifiers.
        output_fields: Dot-paths to output identifiers.
        metadata_fields: Explicit {metadata_key: field_path} mapping.
            If omitted, all unmapped fields become metadata automatically.
        pagination: Config dict with keys: type (token/offset), token_field, param.

    Returns:
        A SourceConnector with a discover() method.
    """
    return _RESTConnector(
        name=name,
        url=url,
        items_path=items_path,
        name_field=name_field,
        headers=headers or {},
        input_fields=input_fields or [],
        output_fields=output_fields or [],
        metadata_fields=metadata_fields,
        pagination=pagination,
    )


class _RESTConnector:
    def __init__(
        self,
        *,
        name: str,
        url: str,
        items_path: str,
        name_field: str,
        headers: dict[str, str],
        input_fields: list[str],
        output_fields: list[str],
        metadata_fields: dict[str, str] | None,
        pagination: dict[str, str] | None,
    ) -> None:
        self.name = name
        self._url = url
        self._items_path = items_path
        self._name_field = name_field
        self._headers = headers
        self._input_fields = input_fields
        self._output_fields = output_fields
        self._metadata_fields = metadata_fields
        self._pagination = pagination

    def discover(self) -> list[DataNode]:
        if httpx is None:  # pragma: no cover
            raise ImportError(
                "httpx is required for rest_connector. Install it with: pip install httpx"
            )

        all_items: list[dict] = []
        url = self._url
        extra_params: dict[str, str] = {}

        while True:
            resp = httpx.get(url, headers=self._headers, params=extra_params or None, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            items = _get_nested(data, self._items_path)
            if items and isinstance(items, list):
                all_items.extend(items)

            # Handle pagination
            if self._pagination and self._pagination.get("type") == "token":
                token_field = self._pagination["token_field"]
                next_token = _get_nested(data, token_field)
                if next_token:
                    extra_params[self._pagination["param"]] = next_token
                    continue
            break

        return [self._to_node(item) for item in all_items]

    def _to_node(self, item: dict[str, Any]) -> DataNode:
        model_name = str(_get_nested(item, self._name_field) or "")

        inputs = [
            DataPort(str(_get_nested(item, f)).lower())
            for f in self._input_fields
            if _get_nested(item, f)
        ]
        outputs = [
            DataPort(str(_get_nested(item, f)).lower())
            for f in self._output_fields
            if _get_nested(item, f)
        ]

        reserved = {self._name_field}
        reserved.update(self._input_fields)
        reserved.update(self._output_fields)

        if self._metadata_fields is not None:
            metadata = {
                meta_key: _get_nested(item, field_path)
                for meta_key, field_path in self._metadata_fields.items()
                if _get_nested(item, field_path) is not None
            }
        else:
            metadata = {k: v for k, v in item.items() if k not in reserved and v is not None}

        metadata["node_type"] = metadata.get("node_type", self.name)

        return DataNode(
            name=model_name,
            platform=self.name,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )
