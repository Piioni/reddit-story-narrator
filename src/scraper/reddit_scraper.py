import praw
import re
import time
from datetime import datetime
from typing import List, Dict, Optional
from praw.exceptions import RedditAPIException, PRAWException

from .database import DatabaseManager, DatabaseConfig
from ..utils.logger import StructuredLogger

class RedditScraper:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        subreddits: List[str],
        search_params: Optional[Dict] = None,
        db_config: Optional[Dict] = None
    ):
        # Configurar Reddit API
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        self.subreddits = subreddits
        self.search_params = search_params or self._default_search_params()
        
        # Configurar logger
        self.logger = StructuredLogger('RedditScraper')
        
        # Configurar base de datos si se proporciona
        self.db_manager = None
        if db_config:
            db_config_obj = DatabaseConfig(**db_config)
            self.db_manager = DatabaseManager(db_config_obj, self.logger)
            self.db_manager.initialize_schema()
    
    def _default_search_params(self) -> Dict:
        """Parámetros de búsqueda por defecto."""
        return {
            'time_filter': 'week',
            'min_upvotes': 250,
            'limit': 5,
            'comment_limit': 2,
            'min_comment_upvotes': 100,
            'max_comment_length': 500
        }
    
    def fetch_posts(self) -> List[Dict]:
        """Obtiene posts de los subreddits configurados."""
        posts_data = []
        limit = self.search_params['limit']
        
        for subreddit_name in self.subreddits:
            try:
                self.logger.log('INFO', 'Scrapeando subreddit', subreddit=subreddit_name)
                
                subreddit = self.reddit.subreddit(subreddit_name)
                posts = self._get_posts_by_filter(subreddit)
                
                subreddit_posts = 0
                for post in posts:
                    if subreddit_posts >= limit:
                        break
                    
                    if self._should_process_post(post):
                        post_data = self._process_post(post, subreddit_name)
                        if post_data:
                            posts_data.append(post_data)
                            subreddit_posts += 1
                            self.logger.log('INFO', 'Post procesado', 
                                          post_id=post.id, subreddit=subreddit_name)
                
                self.logger.log('INFO', f'Completado subreddit {subreddit_name}', 
                              posts_found=subreddit_posts)
                
            except RedditAPIException as e:
                self._handle_reddit_error(e, subreddit_name)
            except PRAWException as e:
                self.logger.log('ERROR', 'Error de PRAW', subreddit=subreddit_name, error=str(e))
            except Exception as e:
                self.logger.log('ERROR', 'Error inesperado', subreddit=subreddit_name, error=str(e))
        
        return posts_data
    
    def _get_posts_by_filter(self, subreddit):
        """Obtiene posts según el filtro de tiempo configurado."""
        time_filter = self.search_params['time_filter']
        limit = self.search_params['limit'] * 3  # Buffer para filtrado
        
        if time_filter == 'week':
            return subreddit.top('week', limit=limit)
        elif time_filter == 'day':
            return subreddit.top('day', limit=limit)
        elif time_filter == 'month':
            return subreddit.top('month', limit=limit)
        else:
            return subreddit.hot(limit=limit)
    
    def _should_process_post(self, post) -> bool:
        """Determina si un post debe ser procesado."""
        min_upvotes = self.search_params['min_upvotes']
        
        # Verificar criterios básicos
        if (post.score < min_upvotes or 
            post.over_18 or 
            not post.selftext.strip()):
            return False
        
        # Verificar si ya fue procesado (solo si hay DB)
        if self.db_manager and self.db_manager.is_processed(post.id):
            return False
        
        return True
    
    def _process_post(self, post, subreddit_name: str) -> Optional[Dict]:
        """Procesa un post individual."""
        try:
            # Extraer datos básicos del post
            post_data = {
                'id': post.id,
                'subreddit': subreddit_name,
                'title': post.title,
                'text': post.selftext,
                'upvotes': post.score,
                'url': f'https://reddit.com{post.permalink}',
                'created_utc': datetime.utcfromtimestamp(post.created_utc),
                'is_nsfw': post.over_18,
                'media': {'type': 'text', 'url': None}
            }
            
            # Extraer updates del texto
            updates = self._extract_updates(post.selftext)
            
            # Construir narrativa completa
            post_data['full_narrative'] = self._build_full_narrative(
                post.title, post.selftext, updates
            )
            
            # Obtener comentarios relevantes
            comments = self._fetch_relevant_comments(post)
            
            # Guardar en base de datos si está configurada
            if self.db_manager:
                success = self.db_manager.save_post_data(post_data, updates, comments)
                if not success:
                    self.logger.log('ERROR', 'Error guardando post', post_id=post.id)
                    return None
            
            # Añadir datos extra para el retorno
            post_data['updates'] = updates
            post_data['comments_count'] = len(comments)
            
            return post_data
            
        except Exception as e:
            self.logger.log('ERROR', 'Error procesando post', post_id=post.id, error=str(e))
            return None
    
    def _extract_updates(self, text: str) -> List[Dict]:
        """Extrae secciones de updates/edits del texto."""
        updates = []
        
        # Patrón mejorado para capturar updates
        patterns = [
            r'(?:EDIT|UPDATE|ACTUALIZACIÓN)[:\s]*([^]*?)(?=(?:EDIT|UPDATE|ACTUALIZACIÓN|\n\n---|\Z))',
            r'(?:Edit|Update)[:\s]*([^]*?)(?=(?:Edit|Update|\n\n---|\Z))'
        ]
        
        for pattern in patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for match in regex.finditer(text):
                update_text = match.group(1).strip()
                if update_text and len(update_text) > 10:  # Filtrar updates muy cortos
                    updates.append({'text': update_text})
        
        return updates
    
    def _build_full_narrative(self, title: str, text: str, updates: List[Dict]) -> str:
        """Construye la narrativa completa del post."""
        narrative_parts = [
            f"TÍTULO: {title}",
            f"POST ORIGINAL: {text}"
        ]
        
        for i, update in enumerate(updates, 1):
            narrative_parts.append(f"ACTUALIZACIÓN {i}: {update['text']}")
        
        return "\n\n" + "="*50 + "\n\n".join(narrative_parts)
    
    def _fetch_relevant_comments(self, post) -> List:
        """Obtiene comentarios relevantes del post."""
        relevant_comments = []
        
        try:
            comment_limit = self.search_params.get('comment_limit', 2)
            min_upvotes = self.search_params.get('min_comment_upvotes', 100)
            max_length = self.search_params.get('max_comment_length', 500)
            
            # Configurar ordenamiento de comentarios
            post.comment_sort = 'top'
            post.comment_limit = min(20, comment_limit * 3)  # Buffer para filtrado
            
            # Evitar cargar "more comments"
            post.comments.replace_more(limit=0)
            comments = post.comments.list()
            
            for comment in comments:
                if self._is_valid_comment(comment, min_upvotes, max_length):
                    relevant_comments.append(comment)
                    if len(relevant_comments) >= comment_limit:
                        break
            
        except Exception as e:
            self.logger.log('ERROR', 'Error obteniendo comentarios', 
                          post_id=post.id, error=str(e))
        
        return relevant_comments
    
    def _is_valid_comment(self, comment, min_upvotes: int, max_length: int) -> bool:
        """Valida si un comentario cumple los criterios."""
        try:
            return (
                hasattr(comment, 'score') and
                hasattr(comment, 'body') and
                comment.score >= min_upvotes and
                len(comment.body) <= max_length and
                comment.body not in ['[deleted]', '[removed]'] and
                not getattr(comment, 'stickied', False) and
                comment.body.strip() != ''
            )
        except:
            return False
    
    def _handle_reddit_error(self, error: RedditAPIException, subreddit: str):
        """Maneja errores específicos de la API de Reddit."""
        error_str = str(error).upper()
        
        if "RATELIMIT" in error_str:
            # Extraer tiempo de espera
            wait_time_match = re.search(r'(\d+)\s*MINUTE', error_str)
            if wait_time_match:
                wait_time = int(wait_time_match.group(1)) * 60
            else:
                wait_time_match = re.search(r'(\d+)\s*SECOND', error_str)
                wait_time = int(wait_time_match.group(1)) if wait_time_match else 60
            
            self.logger.log('WARNING', 'Rate limit alcanzado', 
                          subreddit=subreddit, wait_time=wait_time)
            time.sleep(wait_time + 2)
            
        elif "FORBIDDEN" in error_str:
            self.logger.log('ERROR', 'Acceso prohibido al subreddit', subreddit=subreddit)
        elif "NOT_FOUND" in error_str:
            self.logger.log('ERROR', 'Subreddit no encontrado', subreddit=subreddit)
        else:
            self.logger.log('ERROR', 'Error de Reddit API', 
                          subreddit=subreddit, error=str(error))
    
    def close(self):
        """Libera recursos y cierra conexiones."""
        if self.db_manager:
            self.db_manager.close()
        self.logger.log('INFO', 'Scraper cerrado correctamente')