"""Static types for the documented Freshservice Announcements JSON objects.

https://api.freshservice.com/#announcements
"""

from typing import Literal, TypedDict

AnnouncementState = Literal["active", "archived", "scheduled"]
AnnouncementFilter = Literal["active", "archived", "scheduled", "unread"]


class AnnouncementPayload(TypedDict, total=False):
    """Create/edit fields; Freshservice validates required fields and visibility."""

    title: str
    body_html: str
    visible_from: str
    visible_till: str
    visibility: str
    departments: list[int]
    groups: list[int]
    visible_to_workspace_ids: list[int]
    send_email: bool
    additional_emails: list[str]
    workspace_id: int


class Announcement(AnnouncementPayload, total=False):
    """Response fields, including server-owned metadata.

    IDs are numeric in the attribute table but strings in some official examples.
    Timestamp strings and product-specific visibility values are kept unchanged.
    """

    id: int | str
    body: str
    created_by: int
    state: AnnouncementState
    is_read: bool
    created_at: str
    updated_at: str
