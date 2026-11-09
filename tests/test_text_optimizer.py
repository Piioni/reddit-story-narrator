from data_processor.text_optimizer import TextOptimizer
from utils.models import ProcessedContent


def make_content(narrative: str, segments: list[str]) -> ProcessedContent:
    return ProcessedContent(
        post_id="abc123",
        original_title="Title",
        category="stories",
        narrative_text=narrative,
        optimized_text="",
        estimated_duration=0.0,
        word_count=len(narrative.split()),
        segments=segments,
        metadata={},
    )


def test_empty_text_stays_empty():
    assert TextOptimizer()._optimize_text("") == ""


def test_reddit_abbreviations_are_expanded():
    result = TextOptimizer()._optimize_text("My BF said NTA.")

    assert result == "My boyfriend said Not The A-hole."


def test_contractions_are_expanded():
    result = TextOptimizer()._optimize_text("I can't go and they don't care.")

    assert result == "I cannot go and they do not care."


def test_internet_slang_is_spelled_out():
    assert TextOptimizer()._optimize_text("OMG that was crazy.") == "Oh my god that was crazy."


def test_long_all_caps_words_are_lowercased_for_tts():
    assert TextOptimizer()._optimize_text("This is AMAZING news.") == "This is amazing news."


def test_comma_is_added_after_an_introductory_phrase():
    assert TextOptimizer()._optimize_text("Honestly I was tired.") == "Honestly, I was tired."


def test_existing_comma_after_an_introductory_phrase_is_not_doubled():
    assert TextOptimizer()._optimize_text("Honestly, I was tired.") == "Honestly, I was tired."


def test_repeated_punctuation_is_collapsed():
    assert TextOptimizer()._optimize_text("wait... what??") == "wait. what?"


def test_text_without_final_punctuation_gets_a_period():
    assert TextOptimizer()._optimize_text("it ended there") == "it ended there."


def test_optimize_content_updates_text_segments_and_metrics():
    content = make_content("My BF can't go to the party", ["My BF can't go", "to the party"])

    result = TextOptimizer().optimize_content(content)

    assert result.optimized_text == "My boyfriend cannot go to the party."
    assert result.segments == ["My boyfriend cannot go.", "to the party."]
    assert result.word_count == 7
    assert result.estimated_duration == 7 / 150 * 60


def test_optimization_stats_count_words_and_characters():
    stats = TextOptimizer().get_optimization_stats("a b c", "a b c d")

    assert stats["original_words"] == 3
    assert stats["optimized_words"] == 4
    assert stats["original_chars"] == 5
    assert stats["optimized_chars"] == 7


def test_optimization_stats_handle_empty_input():
    stats = TextOptimizer().get_optimization_stats("", "")

    assert stats == {
        "original_words": 0,
        "optimized_words": 0,
        "original_chars": 0,
        "optimized_chars": 0,
        "abbreviations_replaced": 0,
    }
