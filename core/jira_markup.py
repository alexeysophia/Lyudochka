"""Conversions between Markdown and Jira wiki markup."""
import re


def markdown_to_jira(text: str) -> str:
    """Convert Markdown formatting to Jira wiki markup.

    Handles: ** bold, # headings, ---, *italic*, `code`, ~~strike~~, <u>underline</u>.
    """
    # 1. Headings (longest match first to avoid partial substitution)
    for level in range(6, 0, -1):
        hashes = "#" * level
        text = re.sub(rf"^{hashes}\s+(.+)$", rf"h{level}. \1", text, flags=re.MULTILINE)

    # 2. Markdown bold **text** → Jira bold *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text, flags=re.DOTALL)

    # 5. Inline code `text` → {{text}}
    text = re.sub(r"`([^`]+)`", r"{{\1}}", text)

    # 6. Strikethrough ~~text~~ → -text-
    text = re.sub(r"~~(.+?)~~", r"-\1-", text, flags=re.DOTALL)

    # 7. Underline <u>text</u> → +text+
    text = re.sub(r"<u>(.+?)</u>", r"+\1+", text, flags=re.DOTALL)

    # 8. Horizontal rule --- → remove
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)

    # 9. Unordered list "- item" → "* item"
    text = re.sub(r"^- (.+)$", r"* \1", text, flags=re.MULTILINE)

    # 10. Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def jira_to_md(text: str) -> str:
    """Convert Jira wiki markup to Markdown for in-app preview (ft.Markdown)."""
    # 1. Headings h1..h6
    for level in range(1, 7):
        text = re.sub(rf"^h{level}\. (.+)$", "#" * level + r" \1", text, flags=re.MULTILINE)

    # 2. Bullet list "* item" → "- item" (before bold to avoid collision)
    text = re.sub(r"^\* (.+)$", r"- \1", text, flags=re.MULTILINE)

    # 3. Bold *text* → **text**
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"**\1**", text, flags=re.DOTALL)

    # 4. Italic _text_ → *text*
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"*\1*", text, flags=re.DOTALL)

    # 5. Code {{text}} → `text`
    text = re.sub(r"\{\{(.+?)\}\}", r"`\1`", text, flags=re.DOTALL)

    # 6. Underline +text+ → <u>text</u>
    text = re.sub(r"\+(.+?)\+", r"<u>\1</u>", text, flags=re.DOTALL)

    # 7. Strikethrough -text- → ~~text~~  (only when surrounded by word chars or space)
    text = re.sub(r"(?<=\s)-(\S.+?\S)-(?=\s|$)", r"~~\1~~", text)

    return text
