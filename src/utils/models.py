from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DatabaseConfig:
    host: str
    database: str
    user: str
    password: str
    port: int = 5432

@dataclass
class RedditPost:
    post_id: str
    title: str
    text: str
    author: str
    subreddit: str
    upvotes: int
    url: str
    created_utc: str
    is_nsfw: bool
    status: str
    updates: List[Dict]
    comments: List[Dict]

@dataclass
class ProcessedContent:
    post_id: str
    original_title: str
    category: str
    narrative_text: str
    optimized_text: str
    estimated_duration: float
    word_count: int
    segments: List[str]
    metadata: Dict
