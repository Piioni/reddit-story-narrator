import re
from typing import Dict, List, Optional
from data_models.video_models import RedditPost, ProcessedContent
from utils.logger import StructuredLogger

class NarrativeBuilder:    
    def __init__(self, max_duration: int = 3600, words_per_minute: int = 150):
        self.max_duration = max_duration
        self.words_per_minute = words_per_minute
        self.logger = StructuredLogger('NarrativeBuilder')
    
    def build_narrative(self, reddit_post: RedditPost, category: str) -> Optional[ProcessedContent]:
        try:
            narrative_parts = []
            
            # 1. Original title
            clean_title = self._clean_text(reddit_post.title)
            if clean_title:
                narrative_parts.append(clean_title)
            
            # 2. Main post content
            clean_text = self._clean_text(reddit_post.text)
            if clean_text:
                narrative_parts.append(clean_text)
            
            # 3. Updates (chronological order)
            if reddit_post.updates:
                update_texts = self._process_updates(reddit_post.updates)
                narrative_parts.extend(update_texts)
            
            # 4. Comments
            if reddit_post.comments:
                comment_texts = self._process_comments(reddit_post.comments)
                narrative_parts.extend(comment_texts)
            
            # Join all parts
            narrative_text = " ".join(narrative_parts)
            
            # Calculate metrics
            word_count = len(narrative_text.split())
            estimated_duration = (word_count / self.words_per_minute) * 60
            
            # Split into segments for TTS processing
            segments = self._create_segments(narrative_text)
            
            return ProcessedContent(
                post_id=reddit_post.post_id,
                original_title=reddit_post.title,
                category=category,
                narrative_text=narrative_text,
                optimized_text="",  # Will be filled by TextOptimizer
                estimated_duration=estimated_duration,
                word_count=word_count,
                segments=segments,
                metadata={
                    'author': reddit_post.author,
                    'subreddit': reddit_post.subreddit,
                    'upvotes': reddit_post.upvotes,
                    'updates_count': len(reddit_post.updates),
                    'comments_count': len(reddit_post.comments)
                }
            )
            
        except Exception as e:
            self.logger.error("Error building narrative", 
                            post_id=reddit_post.post_id, error=str(e))
            return None
    
    def _process_updates(self, updates: List[Dict]) -> List[str]:
        update_texts = []
        
        for update in updates:
            update_text = update.get('text', '')
            if update_text and len(update_text.strip()) > 10:
                clean_update = self._clean_text(update_text)
                if clean_update:
                    update_texts.append(clean_update)
        
        return update_texts
    
    def _process_comments(self, comments: List[Dict]) -> List[str]:
        comment_texts = []
        
        # Take top 3 comments by upvotes
        valid_comments = [c for c in comments if c.get('text') and 
                         len(c['text'].strip()) > 20 and
                         c['text'].lower() not in ['[deleted]', '[removed]']]
        
        for comment in valid_comments[:3]:
            clean_comment = self._clean_text(comment['text'])
            if clean_comment:
                comment_texts.append(clean_comment)
        
        return comment_texts
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        # Remove Reddit formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'~~(.*?)~~', r'\1', text)      # Strikethrough
        text = re.sub(r'\^(.*?)\^', r'\1', text)      # Superscript
        
        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'http[s]?://[^\s]+', '', text)
        
        # Remove special characters that cause TTS issues
        text = re.sub(r'[^\w\s\.,!?\-\']', ' ', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _create_segments(self, text: str, max_words_per_segment: int = 100) -> List[str]:
        if not text:
            return []
        
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if adding this sentence exceeds word limit
            test_segment = f"{current_segment} {sentence}".strip()
            
            if len(test_segment.split()) <= max_words_per_segment:
                current_segment = test_segment
            else:
                # Save current segment if it has content
                if current_segment:
                    segments.append(current_segment)
                
                # Start new segment with current sentence
                if len(sentence.split()) <= max_words_per_segment:
                    current_segment = sentence
                else:
                    # If sentence is too long, split it by words
                    words = sentence.split()
                    for i in range(0, len(words), max_words_per_segment):
                        chunk = ' '.join(words[i:i + max_words_per_segment])
                        segments.append(chunk)
                    current_segment = ""
        
        # Add final segment
        if current_segment:
            segments.append(current_segment)
        
        return segments
    