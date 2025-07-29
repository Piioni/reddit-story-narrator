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
            segments = []
            
            # 1. Título con contexto de usuario
            clean_title = self._clean_text(reddit_post.title)
            if clean_title:
                title_segment = f"{clean_title}. Posted by u/{reddit_post.author}"
                segments.append(title_segment)
            
            # 2. Contenido principal del post
            clean_text = self._clean_text(reddit_post.text)
            if clean_text:
                segments.append(clean_text)
            
            # 3. Updates con contexto temporal
            if reddit_post.updates:
                update_segments = self._process_updates_with_context(reddit_post.updates)
                segments.extend(update_segments)
            
            # 4. Comentarios relevantes con introducción
            if reddit_post.comments:
                comment_segments = self._process_comments_with_context(reddit_post.comments)
                segments.extend(comment_segments)
            
            # Crear texto narrativo completo para métricas
            narrative_text = " ".join(segments)
            
            # Calculate metrics
            word_count = len(narrative_text.split())
            estimated_duration = (word_count / self.words_per_minute) * 60
            
            return ProcessedContent(
                post_id=reddit_post.post_id,
                original_title=reddit_post.title,
                category=category,
                narrative_text=narrative_text,
                optimized_text="",  # Will be filled by TextOptimizer
                estimated_duration=estimated_duration,
                word_count=word_count,
                segments=segments,  # ✅ Segmentos con contexto narrativo
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
    
    def _process_updates_with_context(self, updates: List[Dict]) -> List[str]:
        segments = []
        
        for i, update in enumerate(updates):
            update_text = update.get('text', '')
            if update_text and len(update_text.strip()) > 10:
                clean_update = self._clean_text(update_text)
                if clean_update:
                    time_context = self._get_update_time_context(update, i)
                    update_segment = f"Update {time_context}. {clean_update}"
                    segments.append(update_segment)
        
        return segments

    def _get_update_time_context(self, update: Dict, index: int) -> str:
        # Si hay timestamp específico en el update
        if 'timestamp' in update:
            # Aquí podrías calcular "2 hours later", "next day", etc.
            # Por simplicidad, usaremos índices
            pass
        
        # Contextos temporales genéricos pero naturales
        time_contexts = [
            "a few hours later",
            "the next day", 
            "later that week",
            "after some time",
            "recently"
        ]
        
        if index < len(time_contexts):
            return time_contexts[index]
        else:
            return f"update {index + 1}"

    def _process_comments_with_context(self, comments: List[Dict]) -> List[str]:
        segments = []

        if not comments:
            return segments

        # Introducción a los comentarios
        if len(comments) == 1:
            segments.append("Top comment.")
        else:
            segments.append("Top/Relevant comments.")

        # Procesar comentarios individuales
        for i, comment in enumerate(comments[:2]):  # Máximo 2 comentarios
            clean_comment = self._clean_text(comment['text'])
            if clean_comment:
                segments.append(f"{clean_comment}")

        return segments

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

