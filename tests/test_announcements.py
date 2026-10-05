import json

import httpx
import pytest

from freshservice.v2.client import FreshserviceClient
from freshservice.v2.errors import NotFoundError, RateLimitError, ValidationError

ANNOUNCEMENT = {"id": 122, "title": "Scheduled maintenance", "workspace_id": 3}


@pytest.mark.parametrize(
    ("operation", "method", "path"),
    [
        ("create", "POST", "/api/v2/announcements"),
        ("get", "GET", "/api/v2/announcements/122"),
        ("update", "PUT", "/api/v2/announcements/122"),
    ],
)
def test_announcement_methods_use_documented_routes_and_unwrap(operation, method, path):
    seen = []
    payload = {"title": "Scheduled maintenance", "body_html": "<p>Test notice</p>"}

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"announcement": ANNOUNCEMENT})

    with FreshserviceClient(
        "acme", "test-key", transport=httpx.MockTransport(handler)
    ) as client:
        if operation == "create":
            result = client.create_announcement(payload)
        elif operation == "update":
            result = client.update_announcement(122, payload)
        else:
            result = client.get_announcement(122)
    assert result == ANNOUNCEMENT
    assert seen[0].method == method
    assert seen[0].url.path == path
    assert not seen[0].url.query
    if operation != "get":
        assert json.loads(seen[0].content) == payload


@pytest.mark.parametrize(
    ("default", "override", "expected"),
    [(None, None, None), (3, None, "3"), (3, 4, "4"), (3, 0, "0")],
)
def test_list_filters_pagination_and_workspace(default, override, expected):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"announcements": [ANNOUNCEMENT]})

    with FreshserviceClient(
        "acme", "test-key", workspace_id=default, transport=httpx.MockTransport(handler)
    ) as client:
        result = client.list_announcements(
            state="unread", page=2, per_page=10, workspace_id=override
        )
    assert result == [ANNOUNCEMENT]
    assert seen[0].url.path == "/api/v2/announcements"
    assert seen[0].url.params.get("workspace_id") == expected
    assert seen[0].url.params["state"] == "unread"
    assert seen[0].url.params["page"] == "2"
    assert seen[0].url.params["per_page"] == "10"


def test_list_omits_unspecified_filters_and_accepts_empty_results():
    def handler(request):
        assert not request.url.query
        return httpx.Response(200, json={"announcements": []})

    with FreshserviceClient(
        "acme", "test-key", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.list_announcements() == []


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize(
    ("default", "payload_workspace", "override", "expected"),
    [(None, None, None, None), (3, None, None, 3), (3, 4, None, 4), (3, 4, 5, 5)],
)
def test_write_workspace_precedence_and_payload_is_not_mutated(
    operation, default, payload_workspace, override, expected
):
    payload = {"title": "Test"}
    if payload_workspace is not None:
        payload["workspace_id"] = payload_workspace
    original = dict(payload)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        assert not request.url.query
        return httpx.Response(200, json={"announcement": ANNOUNCEMENT})

    with FreshserviceClient(
        "acme", "test-key", workspace_id=default, transport=httpx.MockTransport(handler)
    ) as client:
        if operation == "create":
            client.create_announcement(payload, workspace_id=override)
        else:
            client.update_announcement(122, payload, workspace_id=override)
    assert seen[0].get("workspace_id") == expected
    assert payload == original


@pytest.mark.parametrize("status", [200, 204])
def test_delete_accepts_empty_success_body_without_workspace_query(status):
    def handler(request):
        assert request.method == "DELETE"
        assert request.url.path == "/api/v2/announcements/122"
        assert not request.url.query
        assert not request.content
        return httpx.Response(status)

    with FreshserviceClient(
        "acme", "test-key", workspace_id=3, transport=httpx.MockTransport(handler)
    ) as client:
        assert client.delete_announcement(122) is None


def test_get_does_not_send_default_workspace():
    def handler(request):
        assert not request.url.query
        return httpx.Response(200, json={"announcement": ANNOUNCEMENT})

    with FreshserviceClient(
        "acme", "test-key", workspace_id=3, transport=httpx.MockTransport(handler)
    ) as client:
        assert client.get_announcement(122) == ANNOUNCEMENT


@pytest.mark.parametrize(
    ("status", "error"), [(404, NotFoundError), (400, ValidationError)]
)
def test_resource_methods_preserve_mapped_errors(status, error):
    def handler(request):
        return httpx.Response(status, json={"description": "Synthetic failure"})

    with (
        FreshserviceClient(
            "acme", "test-key", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(error),
    ):
        client.create_announcement({"title": "Test"})


def test_default_workspace_does_not_change_generic_requests():
    def handler(request):
        assert dict(request.url.params) == {"page": "2"}
        return httpx.Response(200, json={"tickets": []})

    with FreshserviceClient(
        "acme", "test-key", workspace_id=3, transport=httpx.MockTransport(handler)
    ) as client:
        assert client.get("tickets", params={"page": 2}).json() == {"tickets": []}


def test_list_preserves_rate_limit_retry_after():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "12"})

    with (
        FreshserviceClient(
            "acme", "test-key", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(RateLimitError) as error,
    ):
        client.list_announcements()
    assert error.value.retry_after == 12


def test_create_preserves_documented_optional_payload_fields():
    payload = {
        "title": "Synthetic notice",
        "body_html": "<p>Synthetic maintenance</p>",
        "visible_from": "2026-10-05T09:00:00Z",
        "visible_till": "2026-10-05T10:00:00Z",
        "visibility": "grouped_visibility",
        "departments": [12],
        "groups": [34],
        "visible_to_workspace_ids": [4],
        "send_email": False,
        "additional_emails": ["test@example.com"],
    }

    def handler(request):
        assert json.loads(request.content) == payload
        return httpx.Response(201, json={"announcement": {"id": "122", **payload}})

    with FreshserviceClient(
        "acme", "test-key", transport=httpx.MockTransport(handler)
    ) as client:
        result = client.create_announcement(payload)
    assert result["id"] == "122"
    assert result["body_html"] == payload["body_html"]
    assert result["send_email"] is False


def test_numeric_string_id_from_official_examples_is_accepted():
    def handler(request):
        assert request.url.path == "/api/v2/announcements/122"
        return httpx.Response(200, json={"announcement": ANNOUNCEMENT})

    with FreshserviceClient(
        "acme", "test-key", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.get_announcement("122") == ANNOUNCEMENT


@pytest.mark.parametrize("announcement_id", [0, -1, True, "", "../tickets", "1?x=2"])
def test_invalid_ids_are_rejected_without_sending(announcement_id):
    def handler(request):
        pytest.fail("Invalid IDs must not send a request")

    with FreshserviceClient(
        "acme", "test-key", transport=httpx.MockTransport(handler)
    ) as client:
        for operation in (
            lambda: client.get_announcement(announcement_id),
            lambda: client.update_announcement(announcement_id, {"title": "Test"}),
            lambda: client.delete_announcement(announcement_id),
        ):
            with pytest.raises(ValueError, match="positive integer"):
                operation()
