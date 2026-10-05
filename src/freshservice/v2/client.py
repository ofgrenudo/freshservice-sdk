from __future__ import annotations

from typing import Any, cast

import httpx

from .errors import raise_for_response
from .models import Announcement, AnnouncementFilter, AnnouncementPayload

# Freshservice ignores the password when authenticating with an API key.
_DUMMY_PASSWORD = "X"


def _announcement_path(announcement_id: int | str) -> str:
    value = str(announcement_id)
    if not value.isascii() or not value.isdigit() or int(value) <= 0:
        raise ValueError("announcement_id must be a positive integer")
    return f"announcements/{value}"


def _build_base_url(endpoint: str) -> str:
    """
    Accepts "acme", "acme.freshservice.com" or "https://acme.freshservice.com"
    (with or without a trailing slash or /api/v2) and returns the API root.
    """
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint:
        raise ValueError("endpoint must not be empty")
    if endpoint.startswith("http://"):
        raise ValueError("Freshservice only supports HTTPS")
    if not endpoint.startswith("https://"):
        if "." not in endpoint:
            endpoint = f"{endpoint}.freshservice.com"
        endpoint = f"https://{endpoint}"
    if not endpoint.endswith("/api/v2"):
        endpoint = f"{endpoint}/api/v2"
    return endpoint


class FreshserviceClient:
    """
    Thin httpx wrapper that authenticates against the Freshservice v2 API.

    https://api.freshservice.com/#authentication
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        workspace_id: int | None = None,
    ):
        if not api_key:
            raise ValueError("api_key must not be empty")
        self.base_url = _build_base_url(endpoint)
        self.workspace_id = workspace_id
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=httpx.BasicAuth(api_key, _DUMMY_PASSWORD),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send a request relative to the API root; raises FreshserviceError on failure."""
        response = self._client.request(method, path.lstrip("/"), **kwargs)
        raise_for_response(response)
        return response

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def _announcement_payload(
        self, payload: AnnouncementPayload, workspace_id: int | None
    ) -> dict[str, Any]:
        body: dict[str, Any] = dict(payload)
        if workspace_id is not None:
            body["workspace_id"] = workspace_id
        elif "workspace_id" not in body and self.workspace_id is not None:
            body["workspace_id"] = self.workspace_id
        return body

    def create_announcement(
        self, payload: AnnouncementPayload, *, workspace_id: int | None = None
    ) -> Announcement:
        """Create an announcement and return the unwrapped JSON object.

        Workspace precedence is per-call argument, payload, then client default.
        https://api.freshservice.com/#create_an_announcement
        """
        response = self.post(
            "announcements", json=self._announcement_payload(payload, workspace_id)
        )
        return cast(Announcement, response.json()["announcement"])

    def get_announcement(self, announcement_id: int | str) -> Announcement:
        """View one announcement by ID; no workspace parameter is documented.

        https://api.freshservice.com/#view_an_announcement
        """
        response = self.get(_announcement_path(announcement_id))
        return cast(Announcement, response.json()["announcement"])

    def list_announcements(
        self,
        *,
        state: AnnouncementFilter | None = None,
        page: int | None = None,
        per_page: int | None = None,
        workspace_id: int | None = None,
    ) -> list[Announcement]:
        """Return one page of announcements, optionally filtered by state/workspace.

        The client workspace is the default; a per-call 0 selects all workspaces.
        https://api.freshservice.com/#list_all_announcements
        """
        workspace = self.workspace_id if workspace_id is None else workspace_id
        params = {
            key: value
            for key, value in (
                ("state", state),
                ("page", page),
                ("per_page", per_page),
                ("workspace_id", workspace),
            )
            if value is not None
        }
        return cast(
            list[Announcement],
            self.get("announcements", params=params).json()["announcements"],
        )

    def update_announcement(
        self,
        announcement_id: int | str,
        payload: AnnouncementPayload,
        *,
        workspace_id: int | None = None,
    ) -> Announcement:
        """Edit an announcement; workspace precedence matches create_announcement.

        https://api.freshservice.com/#edit_an_announcement
        """
        response = self.put(
            _announcement_path(announcement_id),
            json=self._announcement_payload(payload, workspace_id),
        )
        return cast(Announcement, response.json()["announcement"])

    def delete_announcement(self, announcement_id: int | str) -> None:
        """Delete an announcement; successful empty response bodies are not parsed.

        https://api.freshservice.com/#delete_an_announcement
        """
        self.delete(_announcement_path(announcement_id))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FreshserviceClient:  # noqa: PYI034 (Self needs py3.11)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
