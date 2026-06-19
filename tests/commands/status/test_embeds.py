"""Unit tests for src.commands.status.embeds — pure text helpers and embed builders."""

from src.commands.status.shared import MAX_ISSUE_MESSAGE, OVERVIEW_COLOR, STATUS_LABEL
from src.commands.status.shared import (
    build_overview_embed,
    build_status_embed,
    normalize_link,
    status_text,
    truncate,
)
from src.rsi_status import STATUS_PAGE_URL, StatusEntry, StatusOverview, StatusSystem

# ── status_text ───────────────────────────────────────────────────────────────

class TestStatusText:
    def test_known_status_returns_label(self):
        for key, label in STATUS_LABEL.items():
            assert status_text(key) == label

    def test_unknown_status_title_cases_with_spaces(self):
        assert status_text("under_investigation") == "Under Investigation"

    def test_single_unknown_word_title_cased(self):
        assert status_text("degraded_performance") == "Degraded Performance"


# ── truncate ─────────────────────────────────────────────────────────────────

class TestTruncate:
    def test_short_text_returned_unchanged(self):
        assert truncate("Hello.", 100) == "Hello."

    def test_exact_limit_returned_unchanged(self):
        text = "A" * 50
        assert truncate(text, 50) == text

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence goes on much longer than the limit."
        result = truncate(text, 20)
        assert result.endswith(" …")
        assert len(result) <= 20 + 2

    def test_truncates_at_word_boundary_when_no_sentence(self):
        text = "one two three four five six seven eight nine ten"
        result = truncate(text, 20)
        assert result.endswith(" …")

    def test_hard_truncation_when_no_boundaries(self):
        text = "a" * 200
        result = truncate(text, 50)
        assert len(result) <= 51  # 50 chars + ellipsis


# ── normalize_link ────────────────────────────────────────────────────────────

class TestNormalizeLink:
    def test_none_returns_empty_string(self):
        assert normalize_link(None) == ""

    def test_plain_url_unchanged(self):
        assert normalize_link("https://example.com/incident") == "https://example.com/incident"

    def test_strips_trailing_slash(self):
        assert normalize_link("https://example.com/") == "https://example.com"

    def test_strips_index_html(self):
        # After removing index.html the trailing "/" is also stripped
        assert normalize_link("https://example.com/index.html") == "https://example.com"

    def test_strips_index_html_and_trailing_slash(self):
        result = normalize_link("https://example.com/path/index.html")
        assert not result.endswith("index.html")
        assert not result.endswith("/")

    def test_strips_leading_and_trailing_whitespace(self):
        assert normalize_link("  https://example.com  ") == "https://example.com"


# ── build_overview_embed ──────────────────────────────────────────────────────

def _overview(status: str = "operational", systems: list[StatusSystem] | None = None) -> StatusOverview:
    return StatusOverview(summary_status=status, systems=systems or [])


def _system(name: str, status: str = "operational") -> StatusSystem:
    return StatusSystem(name=name, status=status, unresolved=[])


class TestBuildOverviewEmbed:
    def test_title_is_rsi_server_status_without_changes(self):
        embed = build_overview_embed(_overview())
        assert embed.title == "RSI Server Status"

    def test_title_is_rsi_status_alert_with_changes(self):
        embed = build_overview_embed(_overview(), changes=[("Platform", "operational", "degraded")])
        assert embed.title == "RSI Status Alert"

    def test_url_is_status_page(self):
        embed = build_overview_embed(_overview())
        assert embed.url == STATUS_PAGE_URL

    def test_color_matches_summary_status(self):
        for status, color in OVERVIEW_COLOR.items():
            embed = build_overview_embed(_overview(status=status))
            assert embed.color.value == color

    def test_description_contains_overall_status(self):
        embed = build_overview_embed(_overview("operational"))
        assert "Operational" in embed.description

    def test_systems_added_as_fields(self):
        overview = _overview(systems=[_system("Platform"), _system("Persistent Universe")])
        embed = build_overview_embed(overview)
        field_names = [f.name for f in embed.fields]
        assert "Platform" in field_names
        assert "Persistent Universe" in field_names

    def test_changes_appear_in_description(self):
        embed = build_overview_embed(_overview(), changes=[("Platform", "operational", "degraded")])
        assert "Platform" in embed.description
        assert "→" in embed.description

    def test_incident_field_added_when_provided(self):
        incident = ("Outage", "The service is down.", "https://example.com/")
        embed = build_overview_embed(_overview(), incident=incident)
        field_names = [f.name for f in embed.fields]
        assert "Outage" in field_names

    def test_incident_body_truncated_to_limit(self):
        long_message = "X" * (MAX_ISSUE_MESSAGE + 100)
        incident = ("Title", long_message, None)
        embed = build_overview_embed(_overview(), incident=incident)
        incident_field = next(f for f in embed.fields if f.name == "Title")
        assert len(incident_field.value) <= MAX_ISSUE_MESSAGE + 10  # truncate adds " …"

    def test_incident_link_appended_when_provided(self):
        incident = ("Title", "Short message.", "https://example.com/")
        embed = build_overview_embed(_overview(), incident=incident)
        field = next(f for f in embed.fields if f.name == "Title")
        assert "https://example.com/" in field.value

    def test_footer_is_status_domain(self):
        embed = build_overview_embed(_overview())
        assert "status.robertsspaceindustries.com" in embed.footer.text


# ── build_status_embed ────────────────────────────────────────────────────────

def _entry(title: str = "Test", guid: str = "g", **kwargs) -> StatusEntry:
    return StatusEntry(guid=guid, title=title, link=None, published=None, summary=None, **kwargs)


class TestBuildStatusEmbed:
    def test_title_from_entry(self):
        embed = build_status_embed(_entry("Platform Degraded"))
        assert embed.title == "Platform Degraded"

    def test_url_from_entry_link(self):
        entry = StatusEntry(guid="g", title="T", link="https://status.rsi.com/1", published=None, summary=None)
        embed = build_status_embed(entry)
        assert embed.url == "https://status.rsi.com/1"

    def test_no_url_when_no_link(self):
        embed = build_status_embed(_entry())
        assert embed.url is None

    def test_summary_in_description(self):
        entry = StatusEntry(guid="g", title="T", link=None, published=None, summary="The service is degraded.")
        embed = build_status_embed(entry)
        assert "The service is degraded." in embed.description

    def test_no_description_when_no_summary(self):
        embed = build_status_embed(_entry())
        assert embed.description is None

    def test_footer_includes_rsi_status(self):
        embed = build_status_embed(_entry())
        assert "RSI Status" in embed.footer.text

    def test_footer_includes_published_date(self):
        entry = StatusEntry(guid="g", title="T", link=None, published="Mon, 01 Jan 2025", summary=None)
        embed = build_status_embed(entry)
        assert "Mon, 01 Jan 2025" in embed.footer.text

    def test_long_summary_truncated_with_ellipsis(self):
        from src.commands.status.shared import MAX_SUMMARY
        long_summary = "Word " * 200
        entry = StatusEntry(guid="g", title="T", link=None, published=None, summary=long_summary)
        embed = build_status_embed(entry)
        assert embed.description.endswith("…")
        assert len(embed.description) <= MAX_SUMMARY + 1
