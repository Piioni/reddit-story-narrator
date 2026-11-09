from data_processor.narrative_builder import NarrativeBuilder
from utils.models import RedditPost


def make_post(**overrides) -> RedditPost:
    data = dict(
        post_id="abc123",
        title="My neighbour parked on my lawn",
        text="It happened again today.",
        author="some_user",
        subreddit="stories",
        upvotes=1200,
        url="https://reddit.com/r/stories/abc123",
        created_utc="2025-01-01",
        is_nsfw=False,
        status="new",
        updates=[],
        comments=[],
    )
    data.update(overrides)
    return RedditPost(**data)


def test_clean_text_removes_reddit_formatting_and_links():
    raw = "**bold** and *italic* with [a link](https://example.com) and https://example.org plain"

    assert NarrativeBuilder()._clean_text(raw) == "bold and italic with a link and plain"


def test_clean_text_of_nothing_is_empty():
    assert NarrativeBuilder()._clean_text("") == ""


def test_narrative_starts_with_the_title_and_the_author():
    content = NarrativeBuilder().build_narrative(make_post(), "stories")

    assert content.segments[0] == "My neighbour parked on my lawn. Posted by u/some_user"
    assert content.segments[1] == "It happened again today."


def test_empty_title_and_text_are_skipped():
    content = NarrativeBuilder().build_narrative(make_post(title="", text=""), "stories")

    assert content.segments == []
    assert content.narrative_text == ""


def test_updates_get_a_time_context():
    updates = [
        {"text": "The first update has enough words."},
        {"text": "The second update also has enough words."},
    ]

    content = NarrativeBuilder().build_narrative(make_post(updates=updates), "stories")

    assert "Update a few hours later. The first update has enough words." in content.segments
    assert "Update the next day. The second update also has enough words." in content.segments


def test_very_short_updates_are_ignored():
    content = NarrativeBuilder().build_narrative(make_post(updates=[{"text": "ok"}]), "stories")

    assert len(content.segments) == 2


def test_updates_beyond_the_known_contexts_are_numbered():
    builder = NarrativeBuilder()
    updates = [{"text": f"This is update number {i} with enough text."} for i in range(6)]

    segments = builder._process_updates_with_context(updates)

    assert segments[5].startswith("Update update 6.")


def test_a_single_comment_is_introduced_as_top_comment():
    content = NarrativeBuilder().build_narrative(
        make_post(comments=[{"text": "Great story."}]), "stories"
    )

    assert content.segments[-2:] == ["Top comment.", "Great story."]


def test_only_the_first_two_comments_are_narrated():
    comments = [{"text": "First."}, {"text": "Second."}, {"text": "Third."}]

    content = NarrativeBuilder().build_narrative(make_post(comments=comments), "stories")

    assert "Third." not in content.segments
    assert content.segments[-3:] == ["Top/Relevant comments.", "First.", "Second."]


def test_metrics_and_metadata_are_computed():
    post = make_post(
        updates=[{"text": "An update with enough words."}],
        comments=[{"text": "Nice."}],
    )

    content = NarrativeBuilder(words_per_minute=100).build_narrative(post, "stories")

    assert content.word_count == len(content.narrative_text.split())
    assert content.estimated_duration == content.word_count / 100 * 60
    assert content.category == "stories"
    assert content.metadata == {
        "author": "some_user",
        "subreddit": "stories",
        "upvotes": 1200,
        "updates_count": 1,
        "comments_count": 1,
    }
