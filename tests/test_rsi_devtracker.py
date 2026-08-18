from src.rsi_devtracker import DevPost, parse_devposts

SAMPLE_HTML = """
      <a href="/spectrum/community/SC/forum/190049/thread/bugfix-and-issue-discussion-4-10-ptu-10/9086979" class="devpost js-lock">
    <div class="devpost-wrapper">
      <div class="info">
        <img src="https://robertsspaceindustries.com/media/to3sa6d6ydkrsr/heap_infobox/Pacvinyl-Clear-600x600.png?v=1617059850" width="45" height="45" />
        <div class="poster">
          <div class="nickname">Wakapedia-CIG</div>
          <div class="handle">Wakapedia-CIG</div>
        </div>
        <div class="date">
          <span class="label">Date</span>
          <span class="time">5 hours ago</span>
        </div>
      </div>
      <div class="topic">
        <span class="category">Focus Testing</span>
        <span class="thread">[Bugfix and Issue Discussion] 4.10 PTU 12464883</span>
      </div>
      <p class="details">Here is a great place to discuss new bugfixes, new issues encountered, as well as IC reports affecting the latest PTU release!</p>
    </div>
    <div class="glow-corners top-corners"></div>
<div class="glow-corners bottom-corners"></div>
  </a>
      <a href="/spectrum/community/SC/forum/190048/thread/star-citizen-alpha-4-10-ptu-patch-notes-16/9086976" class="devpost js-lock">
    <div class="devpost-wrapper">
      <div class="info">
        <img src="https://robertsspaceindustries.com/media/to3sa6d6ydkrsr/heap_infobox/Pacvinyl-Clear-600x600.png?v=1617059850" width="45" height="45" />
        <div class="poster">
          <div class="nickname">Wakapedia-CIG</div>
          <div class="handle">Wakapedia-CIG</div>
        </div>
      </div>
      <div class="topic">
        <span class="category">Patch Notes</span>
        <span class="thread">[All Waves] Star Citizen Alpha 4.10 PTU Patch Notes 12464883</span>
      </div>
      <p class="details">Star Citizen Alpha Patch 4.10 has been released and is now available to test on the PTU environment!</p>
    </div>
  </a>
"""


def test_parse_devposts_extracts_all_fields():
    posts = parse_devposts(SAMPLE_HTML)
    assert len(posts) == 2
    first = posts[0]
    assert first.post_id == 9086979
    assert first.url == (
        "https://robertsspaceindustries.com/spectrum/community/SC/forum/190049"
        "/thread/bugfix-and-issue-discussion-4-10-ptu-10/9086979"
    )
    assert first.author == "Wakapedia-CIG"
    assert first.avatar_url.startswith("https://robertsspaceindustries.com/media/")
    assert first.category == "Focus Testing"
    assert first.thread == "[Bugfix and Issue Discussion] 4.10 PTU 12464883"
    assert first.details.startswith("Here is a great place")


def test_parse_devposts_preserves_order_newest_first():
    posts = parse_devposts(SAMPLE_HTML)
    assert [p.post_id for p in posts] == [9086979, 9086976]


def test_parse_devposts_empty_or_garbage_returns_empty():
    assert parse_devposts("") == []
    assert parse_devposts("<div>nothing here</div>") == []
    assert parse_devposts("not even html") == []


def test_parse_devposts_skips_block_without_numeric_id():
    html = '<a href="/spectrum/community/SC" class="devpost"><div class="nickname">X</div></a>'
    assert parse_devposts(html) == []


def test_devpost_is_frozen():
    post = DevPost(
        post_id=1, url="u", author="a", avatar_url=None, category=None, thread=None, details=None
    )
    assert post.post_id == 1
