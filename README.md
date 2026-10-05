# Fresh Service API

This project essentially aims to allow developers to interface with the fresh service api via code. 

Official fresh service api documentation can be found here https://api.freshservice.com/

## Announcements

The [Announcements API](https://api.freshservice.com/#announcements) is available
through typed helpers. Configure credentials in your environment, then:

```python
import os

from freshservice.v2.client import FreshserviceClient

with FreshserviceClient(
    os.environ["FRESHSERVICE_DOMAIN"],
    os.environ["FRESHSERVICE_API_KEY"],
    workspace_id=3,
) as client:
    announcements = client.list_announcements(state="active", page=1, per_page=30)
    for announcement in announcements:
        print(announcement.get("id"), announcement.get("title"))
```

`create_announcement(payload)`, `get_announcement(id)`,
`update_announcement(id, payload)`, and `delete_announcement(id)` cover the other
operations. Create, view, and update return the unwrapped announcement dictionary;
list returns one page, and delete returns `None`.

`Announcement` and `AnnouncementPayload` in `freshservice.v2.models` describe the
JSON fields for static type checking; they do not replace server validation.
For create/update, the workspace precedence is the per-call `workspace_id`,
then a workspace in the payload, then the client default. List uses the client
default unless overridden; `workspace_id=0` lists across accessible workspaces.
View/delete and generic request methods do not inject a workspace parameter.
