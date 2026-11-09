import pytest

from scraper.reddit_scraper import RedditScraper
from utils import StructuredLogger


@pytest.fixture
def scraper():
    # Skip __init__: it opens a Reddit client and a database connection.
    instance = RedditScraper.__new__(RedditScraper)
    instance.logger = StructuredLogger("test")
    return instance


TEXT = "The landlord finally agreed to fix the broken heating after three weeks."


def test_hash_ignores_case_and_punctuation(scraper):
    shouted = TEXT.upper().replace(".", "!!!")

    assert scraper._create_content_hash(TEXT) == scraper._create_content_hash(shouted)


def test_hash_ignores_a_leading_update_marker(scraper):
    assert scraper._create_content_hash(TEXT) == scraper._create_content_hash("Update: " + TEXT)


def test_hash_differs_for_different_content(scraper):
    other = "My sister borrowed the car and returned it with an empty tank."

    assert scraper._create_content_hash(TEXT) != scraper._create_content_hash(other)


def test_hash_of_short_text_is_none(scraper):
    assert scraper._create_content_hash("too short") is None


def test_hash_of_text_made_of_stopwords_is_none(scraper):
    assert scraper._create_content_hash("the and of to in on at by is a an") is None


def test_duplicate_updates_are_removed_and_order_is_kept(scraper):
    first = {"update_id": "1", "update_text": TEXT}
    repeated = {"update_id": "2", "update_text": TEXT.lower()}
    second = {"update_id": "3", "update_text": "My sister borrowed the car and returned it empty."}

    assert scraper._deduplicate_updates([first, repeated, second]) == [first, second]


def test_updates_without_enough_text_are_dropped(scraper):
    updates = [{"update_id": "1", "update_text": "short"}, {"update_id": "2", "update_text": TEXT}]

    assert scraper._deduplicate_updates(updates) == [updates[1]]


def test_text_key_is_used_when_update_text_is_missing(scraper):
    update = {"update_id": "1", "text": TEXT}

    assert scraper._deduplicate_updates([update]) == [update]


def test_empty_list_is_returned_as_is(scraper):
    assert scraper._deduplicate_updates([]) == []
