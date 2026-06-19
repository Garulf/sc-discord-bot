"""Unit tests for src.rsi_status — _clean, _text, StatusEntry.from_item."""

from xml.etree import ElementTree

from src.rsi_status import StatusEntry, _clean, _text


def _item(*children_xml: str) -> ElementTree.Element:
    """Build an XML <item> element from raw child XML strings."""
    xml = "<item>" + "".join(children_xml) + "</item>"
    return ElementTree.fromstring(xml)


class TestClean:
    def test_none_returns_none(self):
        assert _clean(None) is None

    def test_empty_string_returns_none(self):
        assert _clean("") is None

    def test_plain_text_passthrough(self):
        assert _clean("Hello world") == "Hello world"

    def test_strips_html_tags(self):
        assert _clean("<p>Hello</p>") == "Hello"

    def test_strips_nested_html_tags(self):
        assert _clean("<div><p>Content</p></div>") == "Content"

    def test_unescapes_html_entities(self):
        assert _clean("&amp;") == "&"

    def test_unescapes_html_entity_in_text(self):
        # "&gt;" in plain text becomes ">", which is not a tag, so it survives
        assert _clean("5 &gt; 3") == "5 > 3"

    def test_collapses_multiple_spaces(self):
        assert _clean("  hello   world  ") == "hello world"

    def test_strips_tags_and_collapses_whitespace(self):
        result = _clean("<p>  Hello   </p>  <p>  World  </p>")
        assert result == "Hello World"

    def test_whitespace_only_after_stripping_returns_none(self):
        assert _clean("<br/>   <br/>") is None


class TestText:
    def test_returns_element_text(self):
        elem = _item("<title>Test Title</title>")
        assert _text(elem, "title") == "Test Title"

    def test_returns_none_for_missing_tag(self):
        elem = _item()
        assert _text(elem, "title") is None

    def test_strips_whitespace_from_text(self):
        elem = _item("<title>  Padded  </title>")
        assert _text(elem, "title") == "Padded"

    def test_returns_none_for_empty_tag(self):
        elem = _item("<title/>")
        assert _text(elem, "title") is None


class TestStatusEntryFromItem:
    def test_parses_title(self):
        elem = _item("<title>Outage Alert</title>", "<guid>id-1</guid>")
        entry = StatusEntry.from_item(elem)
        assert entry.title == "Outage Alert"

    def test_defaults_title_to_untitled(self):
        elem = _item("<guid>id-1</guid>")
        entry = StatusEntry.from_item(elem)
        assert entry.title == "Untitled"

    def test_parses_guid(self):
        elem = _item("<title>T</title>", "<guid>abc-123</guid>")
        entry = StatusEntry.from_item(elem)
        assert entry.guid == "abc-123"

    def test_falls_back_to_link_when_no_guid(self):
        elem = _item("<title>T</title>", "<link>https://example.com/</link>")
        entry = StatusEntry.from_item(elem)
        assert entry.guid == "https://example.com/"

    def test_empty_guid_when_no_guid_or_link(self):
        elem = _item("<title>T</title>")
        entry = StatusEntry.from_item(elem)
        assert entry.guid == ""

    def test_parses_link(self):
        elem = _item("<title>T</title>", "<guid>g</guid>", "<link>https://status.rsi.com/</link>")
        entry = StatusEntry.from_item(elem)
        assert entry.link == "https://status.rsi.com/"

    def test_parses_published_date(self):
        elem = _item("<title>T</title>", "<guid>g</guid>", "<pubDate>Mon, 01 Jan 2025 12:00:00 GMT</pubDate>")
        entry = StatusEntry.from_item(elem)
        assert entry.published == "Mon, 01 Jan 2025 12:00:00 GMT"

    def test_parses_summary_and_strips_html(self):
        # RSS <description> carries HTML-escaped content, not real child elements
        elem = _item("<title>T</title>", "<guid>g</guid>",
                     "<description>&lt;p&gt;Service degraded.&lt;/p&gt;</description>")
        entry = StatusEntry.from_item(elem)
        assert entry.summary == "Service degraded."

    def test_missing_description_gives_none_summary(self):
        elem = _item("<title>T</title>", "<guid>g</guid>")
        entry = StatusEntry.from_item(elem)
        assert entry.summary is None
