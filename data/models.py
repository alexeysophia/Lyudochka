from dataclasses import dataclass, field


@dataclass
class Team:
    name: str
    jira_project: str       # e.g. "BACKEND"
    default_task_type: str  # e.g. "Story", "Bug", "Task"
    rules: str              # Free-form rules text shown to AI
    team_lead: str          # Team lead name
    context: str = ""       # Team context: products, responsibilities


@dataclass
class Settings:
    default_llm: str = "anthropic"   # "anthropic" | "gemini"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    jira_url: str = ""               # e.g. "https://jira.company.com"
    jira_token: str = ""             # Personal Access Token


@dataclass
class AIResponse:
    status: str                           # "ready" | "need_clarification"
    task_text: str = ""                   # Formatted task body (if ready)
    task_title: str = ""                  # Task title (if ready)
    jira_params: dict = field(default_factory=dict)   # project, type, priority, labels (if ready)
    questions: list[str] = field(default_factory=list)  # Clarifying questions (if need_clarification)


@dataclass
class VoiceResult:
    description: str
    team_name: str | None = None  # None = не удалось определить команду из записи


@dataclass
class Draft:
    id: str
    created_at: str                       # ISO format datetime
    team_name: str
    user_input: str
    stage: str                            # "input" | "clarification" | "ready"
    questions: list[str] = field(default_factory=list)
    answers: list[list[str]] = field(default_factory=list)  # [[question, answer], ...]
    ai_response: AIResponse | None = None
