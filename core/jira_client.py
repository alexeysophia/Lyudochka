import logging

import httpx

log = logging.getLogger(__name__)


async def create_jira_issue(
    jira_url: str,
    token: str,
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Story",
    priority: str | None = None,
    labels: list[str] | None = None,
) -> str:
    """Create a Jira issue via REST API v2. Returns the issue key (e.g. 'PROJ-123')."""
    url = f"{jira_url.rstrip('/')}/rest/api/2/issue"

    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issue_type},
    }
    if priority:
        fields["priority"] = {"name": priority}
    if labels:
        fields["labels"] = labels

    payload = {"fields": fields}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    key: str = data["key"]
    log.info("Jira issue created: %s", key)
    return key
