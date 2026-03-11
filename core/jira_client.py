import json
import logging
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

# JQL field name → Jira REST API v2 field name
_JQL_TO_API: dict[str, str] = {
    "affectedversion": "versions",
    "affectedversions": "versions",
    "fixversion": "fixVersions",
    "fixversions": "fixVersions",
    "component": "components",
    "type": "issuetype",
    "issuetype": "issuetype",
    "priority": "priority",
    "assignee": "assignee",
    "reporter": "reporter",
    "duedate": "duedate",
    "due": "duedate",
    "environment": "environment",
    "resolution": "resolution",
    "status": "status",
}

# API field names whose plain-string value should become {"name": "value"}
_NAME_OBJECT_FIELDS = {
    "priority", "assignee", "reporter", "issuetype", "resolution", "status",
    "security",
}

# API field names whose plain-string value should become [{"name": "value"}]
_NAME_ARRAY_FIELDS = {
    "versions", "fixVersions", "components",
}


def _normalize_field(raw_key: str, raw_value: str) -> tuple[str, Any]:
    """Convert a JQL-style field name and plain string value to Jira API format."""
    # 1. Resolve API field name
    api_key = _JQL_TO_API.get(raw_key.lower(), raw_key)

    # 2. If value is already JSON — parse and use as-is
    stripped = raw_value.strip()
    if stripped.startswith(("[", "{")):
        try:
            return api_key, json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 3. Handle cf[12345] → customfield_12345
    cf_match = re.fullmatch(r"cf\[(\d+)\]", api_key, re.IGNORECASE)
    if cf_match:
        api_key = f"customfield_{cf_match.group(1)}"

    # 4. Apply value conversion based on known field type
    if api_key in _NAME_ARRAY_FIELDS:
        return api_key, [{"name": stripped}]
    if api_key in _NAME_OBJECT_FIELDS:
        return api_key, {"name": stripped}

    # 5. Unknown field — pass as plain string
    return api_key, stripped


_SKIP_FIELD_IDS = {
    "summary", "description", "project", "issuetype", "labels", "attachment",
    "sub-tasks", "issuelinks", "comment", "watches", "votes", "worklog",
    "timetracking", "thumbnail",
}


async def get_project_meta(jira_url: str, token: str, project_key: str) -> dict:
    """Fetch issue types and available fields for a Jira project via createmeta.
    Returns {"issue_types": [{"id", "name"}], "fields": [{"id", "name"}]}.
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    base = jira_url.rstrip("/")
    url = (
        f"{base}/rest/api/2/issue/createmeta"
        f"?projectKeys={project_key}&expand=projects.issuetypes.fields"
    )
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")
    if resp.status_code >= 400:
        raise ValueError(f"Jira {resp.status_code}: {resp.text}")

    data = resp.json()
    projects = data.get("projects", [])
    if not projects:
        raise ValueError(f"Проект '{project_key}' не найден или нет доступа")

    project_data = projects[0]
    issue_types = [{"id": t["id"], "name": t["name"]} for t in project_data.get("issuetypes", [])]

    # Collect unique fields across all issue types, excluding handled ones
    seen: set[str] = set()
    fields: list[dict] = []
    for itype in project_data.get("issuetypes", []):
        for fid, fmeta in itype.get("fields", {}).items():
            if fid in seen or fid in _SKIP_FIELD_IDS or fid.startswith("__"):
                continue
            seen.add(fid)
            fields.append({"id": fid, "name": fmeta.get("name", fid)})

    fields.sort(key=lambda f: f["name"])
    log.debug("Project %s: %d issue types, %d fields", project_key, len(issue_types), len(fields))
    return {"issue_types": issue_types, "fields": fields}


async def create_jira_issue(
    jira_url: str,
    token: str,
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Story",
    issue_type_id: str = "",
    labels: list[str] | None = None,
    extra_fields: dict | None = None,
) -> str:
    """Create a Jira issue via REST API v2. Returns the issue key (e.g. 'PROJ-123')."""
    url = f"{jira_url.rstrip('/')}/rest/api/2/issue"

    # Prefer numeric ID (avoids locale-specific name rejection by Jira Server)
    issuetype_value = {"id": issue_type_id} if issue_type_id else {"name": issue_type}

    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "description": description,
        "issuetype": issuetype_value,
    }
    if issue_type.lower() == "epic":
        fields["customfield_15501"] = summary  # Epic Name — обязательное поле для Epic
    if labels:
        fields["labels"] = labels
    if extra_fields:
        for raw_k, raw_v in extra_fields.items():
            api_k, api_v = _normalize_field(raw_k, str(raw_v))
            fields[api_k] = api_v

    payload = {"fields": fields}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    log.debug("Jira request payload: %s", payload)
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")

    log.debug("Jira response status: %s", response.status_code)
    if response.status_code >= 400:
        raw = response.text
        log.error("Jira API error %s: %s", response.status_code, raw)
        status = response.status_code
        if status == 401:
            raise ValueError("Jira: неверный токен (401 Unauthorized)")
        elif status == 403:
            raise ValueError("Jira: нет прав для создания задачи (403 Forbidden)")
        elif status == 500:
            raise ValueError("Jira: внутренняя ошибка сервера (500)")
        elif status == 503:
            raise ValueError("Jira: сервер временно недоступен (503)")
        raise ValueError(f"Jira {status}: {raw}")
    data = response.json()

    key: str = data["key"]
    log.info("Jira issue created: %s", key)
    return key
