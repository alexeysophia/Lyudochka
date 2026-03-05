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
    if issue_type.lower() == "epic":
        fields["customfield_15501"] = summary  # Epic Name — обязательное поле для Epic
    if labels:
        fields["labels"] = labels

    payload = {"fields": fields}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    log.debug("Jira request payload: %s", payload)
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)

    log.debug("Jira response status: %s", response.status_code)
    if response.status_code >= 400:
        raw = response.text
        log.error("Jira API error %s: %s", response.status_code, raw)
        raise ValueError(f"Jira {response.status_code}: {raw}")
    data = response.json()

    key: str = data["key"]
    log.info("Jira issue created: %s", key)
    return key
