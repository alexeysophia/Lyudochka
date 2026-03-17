import json
import logging
import re
import urllib.parse
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
    Returns {
        "issue_types": [{"id", "name"}],
        "fields": [{"id", "name", "multi", "allowed_values": [{"id", "name"}]}]
    }.
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
            schema = fmeta.get("schema", {})
            multi = schema.get("type") == "array"
            is_insight = "insight" in schema.get("custom", "").lower()
            raw_av = fmeta.get("allowedValues", [])
            allowed_values = [
                {"id": str(av.get("id", "")), "name": av.get("name") or av.get("value") or str(av.get("id", ""))}
                for av in raw_av
                if av.get("id") is not None
            ]
            fields.append({
                "id": fid,
                "name": fmeta.get("name", fid),
                "multi": multi,
                "allowed_values": allowed_values,
                "insight": is_insight,
            })

    fields.sort(key=lambda f: f["name"])
    insight_count = sum(1 for f in fields if f["insight"])
    log.debug(
        "Project %s: %d issue types, %d fields (%d insight)",
        project_key, len(issue_types), len(fields), insight_count,
    )
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
    epic_name: str = "",
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
        fields["customfield_15501"] = epic_name if epic_name else summary  # Epic Name
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


async def get_link_types(jira_url: str, token: str) -> list[dict]:
    """Fetch all issue link types available in the Jira instance.
    Returns [{"id", "name", "inward", "outward"}].
    """
    url = f"{jira_url.rstrip('/')}/rest/api/2/issueLinkType"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")
    if resp.status_code == 401:
        raise ValueError("Jira: неверный токен (401 Unauthorized)")
    if resp.status_code == 403:
        raise ValueError("Jira: нет прав для просмотра типов связей (403 Forbidden)")
    if resp.status_code >= 400:
        raise ValueError(f"Jira {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    result = [
        {
            "id": lt["id"],
            "name": lt["name"],
            "inward": lt.get("inward", lt["name"]),
            "outward": lt.get("outward", lt["name"]),
        }
        for lt in data.get("issueLinkTypes", [])
    ]
    log.debug("Loaded %d link types", len(result))
    return result


async def create_issue_link(
    jira_url: str,
    token: str,
    link_type_id: str,
    outward_issue: str,
    inward_issue: str,
) -> None:
    """Create an issue link via Jira REST API v2.

    outward_issue — the issue that "does" the relation (e.g. "blocks")
    inward_issue  — the issue that "receives" the relation (e.g. "is blocked by")
    Raises ValueError on any API error.
    """
    url = f"{jira_url.rstrip('/')}/rest/api/2/issueLink"
    payload = {
        "type": {"id": link_type_id},
        "outwardIssue": {"key": outward_issue},
        "inwardIssue": {"key": inward_issue},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    log.debug("Creating issue link: %s → %s (type %s)", outward_issue, inward_issue, link_type_id)
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")
    if resp.status_code == 401:
        raise ValueError("Неверный токен (401)")
    if resp.status_code == 403:
        raise ValueError("Нет прав для создания связи (403)")
    if resp.status_code == 404:
        raise ValueError(f"Задача не найдена (404)")
    if resp.status_code >= 400:
        try:
            errors = resp.json().get("errors", {}) or resp.json().get("errorMessages", [])
            detail = "; ".join(str(v) for v in errors.values()) if isinstance(errors, dict) else "; ".join(errors)
        except Exception:
            detail = resp.text[:200]
        raise ValueError(detail or f"Jira {resp.status_code}")
    log.info("Issue link created: %s → %s (type_id=%s)", outward_issue, inward_issue, link_type_id)


async def update_jira_issue(
    jira_url: str,
    token: str,
    issue_key: str,
    extra_fields: dict[str, str],
) -> None:
    """Update a Jira issue via REST API v2.

    extra_fields: {field_id: json_value_string} — values already in Jira API format
    (e.g. '{"id":"10001"}' or '[{"id":"1"},{"id":"2"}]' or plain string).
    Raises ValueError on any API error.
    """
    url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{issue_key}"

    fields: dict = {}
    for fid, raw_val in extra_fields.items():
        stripped = raw_val.strip()
        if stripped.startswith(("[", "{")):
            try:
                fields[fid] = json.loads(stripped)
                continue
            except json.JSONDecodeError:
                pass
        fields[fid] = stripped

    payload = {"fields": fields}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    log.debug("Jira update %s payload: %s", issue_key, payload)
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.put(url, json=payload, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")

    if resp.status_code == 204:
        log.info("Jira issue updated: %s", issue_key)
        return
    if resp.status_code == 401:
        raise ValueError("Неверный токен (401)")
    if resp.status_code == 403:
        raise ValueError("Нет прав для изменения задачи (403)")
    if resp.status_code == 404:
        raise ValueError(f"Задача {issue_key} не найдена (404)")
    if resp.status_code >= 400:
        try:
            body = resp.json()
            errors = body.get("errors", {}) or body.get("errorMessages", [])
            detail = (
                "; ".join(str(v) for v in errors.values())
                if isinstance(errors, dict)
                else "; ".join(errors)
            )
        except Exception:
            detail = resp.text[:200]
        raise ValueError(detail or f"Jira {resp.status_code}")


async def _get_insight_field_config(
    jira_url: str, token: str, field_id: str
) -> list[int]:
    """Return objectTypeIds from Insight field config, or empty list on failure."""
    url = f"{jira_url.rstrip('/')}/rest/insight/1.0/config/field/{field_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
        log.debug("Insight field config %s: status=%s body=%s", field_id, resp.status_code, resp.text[:300])
        if resp.status_code == 200:
            data = resp.json()
            ids = data.get("objectTypeIds", [])
            log.debug("Insight field config for %s: objectTypeIds=%s", field_id, ids)
            return [int(i) for i in ids if i is not None]
    except Exception as exc:
        log.debug("Could not fetch Insight field config for %s: %s", field_id, exc)
    return []


async def get_insight_objects(
    jira_url: str, token: str, field_name: str, field_id: str = "",
    object_type_id: int | None = None,
) -> list[dict]:
    """Fetch Insight/Assets objects for a field.

    Priority for IQL building:
    1. object_type_id (explicit, most precise): objectTypeId = {id}
    2. field_id → config endpoint: objectTypeId = {id from config}
    3. Fallback: objectType = "{derived name}"
    Returns [{"id": objectKey, "name": label, "schema_id": ...}].
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    base = jira_url.rstrip("/")

    # Always derive type_name as fallback label for error messages
    type_name = re.sub(r"\s*\(.*?\)\s*$", "", field_name).strip()

    iql: str
    if object_type_id is not None:
        iql = f"objectTypeId = {object_type_id}"
        log.debug("Insight IQL by explicit objectTypeId: %s", iql)
    elif field_id:
        type_ids = await _get_insight_field_config(jira_url, token, field_id)
        if type_ids:
            cond = " OR ".join(f"objectTypeId = {tid}" for tid in type_ids)
            iql = f"({cond})" if len(type_ids) > 1 else f"objectTypeId = {type_ids[0]}"
            log.debug("Insight IQL by objectTypeId from config: %s", iql)
        else:
            iql = f'objectType = "{type_name}"'
            log.debug("Insight IQL fallback by name: %s", iql)
    else:
        iql = f'objectType = "{type_name}"'

    url = (
        f"{base}/rest/insight/1.0/iql/objects"
        f"?iql={urllib.parse.quote(iql)}&maxResults=200&includeAttributes=false"
    )

    log.debug("Insight IQL request: %s", url)
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.ConnectTimeout:
        raise ValueError("Сервер Jira недоступен: превышено время подключения")
    except httpx.TimeoutException:
        raise ValueError("Сервер Jira не ответил вовремя (таймаут)")
    except httpx.ConnectError as e:
        raise ValueError(f"Не удалось подключиться к Jira: {e}")

    if resp.status_code >= 400:
        raise ValueError(f"Insight API {resp.status_code}: {resp.text[:300]}")

    raw = resp.json()
    entries = raw.get("objectEntries", [])
    result: list[dict] = [
        {
            "id": obj.get("objectKey", ""),
            "name": obj.get("label", obj.get("objectKey", "")),
            "schema_id": obj.get("objectType", {}).get("objectSchemaId"),
        }
        for obj in entries
        if obj.get("objectKey")
    ]

    if not result:
        raise ValueError(
            f"Insight: объекты типа «{type_name}» не найдены.\n"
            "Возможно, имя типа объекта в Insight не совпадает с названием поля."
        )

    log.debug("Insight: got %d objects for type '%s'", len(result), type_name)
    # Log full detail to diagnose wrong-schema issues
    for obj in entries[:50]:
        obj_type = obj.get("objectType", {})
        schema = obj_type.get("objectSchemaId", "?")
        type_n = obj_type.get("name", "?")
        log.debug(
            "  Insight obj: key=%s label=%r schema=%s type=%s",
            obj.get("objectKey"), obj.get("label"), schema, type_n,
        )
    return result
