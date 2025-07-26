from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from datetime import datetime

@dataclass
class RedditPost:
    """Unified Reddit post data from database."""
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
    """Content after narrative building and optimization."""
    post_id: str
    original_title: str
    category: str
    narrative_text: str
    optimized_text: str
    estimated_duration: float
    word_count: int
    segments: List[str]
    metadata: Dict
    is_suitable: bool
    processing_notes: List[str]

@dataclass
class VideoSegment:
    """Individual video segment with timing and audio."""
    text: str
    start_time: float
    end_time: float
    audio_file: Optional[str] = None
    subtitle_file: Optional[str] = None

@dataclass
class VideoContent:
    """Complete video ready for production."""
    post_id: str
    title: str
    category: str
    segments: List[VideoSegment]
    total_duration: float
    background_video: Optional[str] = None
    final_video_path: Optional[str] = None
    status: str = 'pending'