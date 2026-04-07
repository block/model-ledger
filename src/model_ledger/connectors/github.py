"""github_connector — discover models from config files in GitHub repos.

The factory handles GitHub API plumbing. You provide a parser function
that converts file content into DataNodes.
"""
from __future__ import annotations

import base64
from typing import Any, Callable

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from model_ledger.graph.models import DataNode


def github_connector(
    *,
    name: str,
    repos: list[str],
    project_path: str,
    config_file: str,
    parser: Callable[[str, str], DataNode | None],
    token: str | None = None,
) -> _GitHubConnector:
    """Create a SourceConnector that discovers models from GitHub repos.

    For each repo, lists subdirectories under project_path, reads config_file
    from each, and passes the content to parser to produce DataNodes.

    Args:
        name: Platform name for discovered DataNodes.
        repos: List of GitHub repos (org/repo format).
        project_path: Directory containing project subdirectories.
        config_file: Filename to read in each project directory.
        parser: Function (project_name, file_content) -> DataNode | None.
        token: GitHub personal access token (optional).

    Returns:
        A SourceConnector with a discover() method.
    """
    return _GitHubConnector(
        name=name, repos=repos, project_path=project_path,
        config_file=config_file, parser=parser, token=token,
    )


class _GitHubConnector:
    def __init__(
        self, *, name: str, repos: list[str], project_path: str,
        config_file: str, parser: Callable[[str, str], DataNode | None],
        token: str | None,
    ) -> None:
        self.name = name
        self._repos = repos
        self._project_path = project_path
        self._config_file = config_file
        self._parser = parser
        self._token = token

    def discover(self) -> list[DataNode]:
        if httpx is None:  # pragma: no cover
            raise ImportError("httpx is required for github_connector. Install it with: pip install httpx")

        nodes = []
        for repo in self._repos:
            projects = self._list_projects(repo)
            for project_name in projects:
                node = self._discover_project(repo, project_name)
                if node:
                    nodes.append(node)
        return nodes

    def _list_projects(self, repo: str) -> list[str]:
        items = self._gh_api(f"repos/{repo}/contents/{self._project_path}")
        if not items or not isinstance(items, list):
            return []
        return [item["name"] for item in items if item.get("type") == "dir"]

    def _discover_project(self, repo: str, project: str) -> DataNode | None:
        path = f"{self._project_path}/{project}/{self._config_file}"
        content = self._read_file(repo, path)
        if content is None:
            return None
        return self._parser(project, content)

    def _read_file(self, repo: str, path: str) -> str | None:
        data = self._gh_api(f"repos/{repo}/contents/{path}")
        if not data or "content" not in data:
            return None
        try:
            return base64.b64decode(data["content"]).decode()
        except Exception:
            return None

    def _gh_api(self, endpoint: str) -> Any:
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = httpx.get(
                f"https://api.github.com/{endpoint}",
                headers=headers, timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None
