import praw
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from praw.exceptions import RedditAPIException, PRAWException
from scraper.database import DatabaseManager, DatabaseConfig
from utils.logger import StructuredLogger

class RedditScraper:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        subreddits: List[str],
        search_params: Dict,
        db_config: Dict  
    ):
        # Configurar Reddit API
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        self.subreddits = subreddits
        self.search_params = search_params or {
            'time_filter': 'week',
            'min_upvotes': 250,
            'limit': 5,
            'comment_limit': 2,
            'min_comment_upvotes': 100,
            'max_comment_length': 500
        }

        # Configurar logger
        self.logger = StructuredLogger('RedditScraper')

        self.db_config = db_config 
        
         # Configurar Database
        db_config_obj = DatabaseConfig(**db_config)
        self.db_manager = DatabaseManager(db_config_obj, self.logger)
        self.db_manager.initialize_schema()
    
    
    # Funciones para scrappear subreddits en base a parametros
    def fetch_posts(self) -> List[Dict]:
        posts_data = []
        
        # Recorrer cada subreddit y obtener posts
        for subreddit_name in self.subreddits:
            try:
                self.logger.log('INFO', 'Scrapeando subreddit', subreddit=subreddit_name)
                subreddit_posts = self._fetch_subreddit_posts(subreddit_name)
                posts_data.extend(subreddit_posts)
                
                self.logger.log('INFO', f'Completado subreddit {subreddit_name}', 
                              posts_found=len(subreddit_posts))
                
            except RedditAPIException as e:
                self._handle_reddit_error(e, subreddit_name)
            except PRAWException as e:
                self.logger.log('ERROR', 'Error de PRAW', subreddit=subreddit_name, error=str(e))
            except Exception as e:
                self.logger.log('ERROR', 'Error inesperado', subreddit=subreddit_name, error=str(e))
        
        return posts_data

    def _fetch_subreddit_posts(self, subreddit_name: str) -> List[Dict]:
        subreddit = self.reddit.subreddit(subreddit_name)
        limit = self.search_params['limit']
        
        # Obtener tipo de posts según configuración o input del usuario
        posts_generator = self._get_posts_generator(subreddit)
        
        posts_data = []
        for post in posts_generator:
            if len(posts_data) >= limit:
                break
            
            if self._should_process_post(post):
                # Si el post cumple los criterios, procesarlo junto a sus updates
                post_data = self._process_post(post, subreddit_name)
                if post_data:
                    posts_data.append(post_data)
                    self.logger.log('INFO', 'Post procesado', 
                                  post_id=post.id, subreddit=subreddit_name)
        
        return posts_data

    def _should_process_post(self, post) -> bool:
        min_upvotes = self.search_params['min_upvotes']
        
        # Verificar criterios básicos
        if (post.score < min_upvotes or 
            not post.selftext.strip()):
            return False
        
        # Verificar si ya fue procesado y registrado en la base de datos
        if self.db_manager and self.db_manager.is_processed(post.id):
            return False
        
        return True
    
    def _process_post(self, post, subreddit_name: str) -> Optional[Dict]:
        try:
            # Extraer datos básicos del post
            post_data = {
                'id': post.id,
                'author': post.author.name if post.author else '[deleted]',
                'subreddit': subreddit_name,
                'title': post.title,
                'text': post.selftext,
                'upvotes': post.score,
                'url': f'https://www.reddit.com{post.permalink}' if post.permalink else None,
                'created_utc': datetime.fromtimestamp(post.created_utc, timezone.utc),
                'is_nsfw': post.over_18,
                'processed_at': datetime.now(timezone.utc)
            }
            
            # Extraer updates del texto
            self.logger.log('INFO', 'Buscando updates', post_id=post.id, author=post_data['author'])
            updates = self._extract_updates(post)

            # Obtener comentarios relevantes
            comments = self._fetch_relevant_comments(post)
            
            # Guardar en base de datos
            success = self.db_manager.save_post_data(post_data, updates, comments)
            if not success:
                self.logger.log('ERROR', 'Error guardando post', post_id=post.id)
                return None
                        
            return post_data
            
        except Exception as e:
            self.logger.log('ERROR', 'Error procesando post', post_id=post.id, error=str(e))
            return None

    # Funciones para extraer updates de los posts mediante varias estrategias
    def _extract_updates(self, post) -> List[Dict]:
        all_updates = []
        
        try:
            # Estrategia 1: Updates en comentarios del autor en el post original
            comment_updates = self._extract_updates_from_author_comments(post)
            all_updates.extend(comment_updates)
        
            # Si el autor del post no ha sido eliminado
            if post.author:
                # Estrategia 2: Posts posteriores del autor en el mismo subreddit
                subreddit_updates = self._find_updates_in_subreddit(post)
                all_updates.extend(subreddit_updates)
                
                # Estrategia 3: Posts del usuario que mencionen el post original
                profile_updates = self._find_updates_in_user_profile(post)
                all_updates.extend(profile_updates)
        
            # Ordenar updates por fecha y eliminar duplicados
            unique_updates = self._deduplicate_updates(all_updates)
            sorted_updates = sorted(unique_updates, key=lambda x: x.get('created_utc', datetime.min.replace(tzinfo=timezone.utc)))
            
            if not sorted_updates:
                self.logger.log('INFO', 'No se encontraron updates para el post', post_id=post.id)
                return []
            else:
                self.logger.log('INFO', 'Updates encontrados para el post', 
                            post_id=post.id, 
                            total_updates=len(sorted_updates))
                
                return sorted_updates
                
        except Exception as e:
            self.logger.log('ERROR', 'Error en _extract_updates', post_id=post.id, error=str(e))
            return []

    def _extract_updates_from_author_comments(self, post) -> List[Dict]:
        updates = []
        
        try:
            if not post.author:
                return updates
                
            author_name = post.author.name
            
            # Palabras clave que indican updates/edits en comentarios
            update_keywords = [
                'update', 'actualización', 'edit', 'edited', 'correction', 
                'clarification', 'aclaración', 'corrección', 'add', 'adding',
                'forgot to mention', 'forgot to add', 'también', 'also',
                'by the way', 'btw', 'oh and', 'one more thing'
            ]
            
            # Configurar comentarios
            post.comment_sort = 'new'  # Ordenar por fecha para capturar updates cronológicos
            post.comment_limit = 100   # Límite alto para capturar todos los comentarios del autor
            
            # Evitar cargar "more comments" para mejor rendimiento
            post.comments.replace_more(limit=0)
            
            # Obtener todos los comentarios
            all_comments = post.comments.list()
            
            # Filtrar comentarios del autor
            author_comments = [
                comment for comment in all_comments 
                if (hasattr(comment, 'author') and 
                    comment.author and 
                    comment.author.name == author_name and
                    hasattr(comment, 'body') and
                    comment.body not in ['[deleted]', '[removed]'])
            ]
            
            # Analizar cada comentario del autor
            for comment in author_comments:
                comment_text = comment.body.lower()
                comment_original = comment.body
                
                # Verificar si el comentario contiene información de update/edit
                contains_update_keywords = any(keyword in comment_text for keyword in update_keywords)
                
                # Verificar si es un comentario sustancial (no solo respuestas cortas)
                is_substantial = len(comment_original.strip()) > 50
                
                # Verificar si tiene alta interacción (podría indicar información importante)
                has_interaction = comment.score > 10 if hasattr(comment, 'score') else False
                
                # Patrones específicos que indican updates en comentarios
                update_patterns = [
                    r'(?:update|actualización)[:\s]*(.{20,})',
                    r'(?:edit|edited)[:\s]*(.{20,})',
                    r'(?:forgot to mention|forgot to add|olvidé mencionar)[:\s]*(.{20,})',
                    r'(?:clarification|aclaración)[:\s]*(.{20,})',
                    r'(?:correction|corrección)[:\s]*(.{20,})',
                    r'(?:also|también|by the way|btw)[,\s]*(.{30,})'
                ]
                
                # Buscar patrones específicos de update
                contains_update_pattern = False
                for pattern in update_patterns:
                    if re.search(pattern, comment_text, re.IGNORECASE | re.DOTALL):
                        contains_update_pattern = True
                        break
                
                # Decidir si el comentario es un update relevante
                is_update = (
                    (contains_update_keywords and is_substantial) or
                    contains_update_pattern or
                    (is_substantial and has_interaction and 
                    any(word in comment_text for word in ['update', 'edit', 'actualización']))
                )
                
                if is_update:
                    updates.append({
                        'id': comment.id,
                        'type': 'author_comment',
                        'text': comment_original,
                        'source': f'author_comment_{comment.id}',
                        'created_utc': datetime.fromtimestamp(comment.created_utc, timezone.utc),
                        'upvotes': getattr(comment, 'score', 0),
                        'url': f'https://www.reddit.com{post.permalink}{comment.id}/'
                    })
                    
            self.logger.log('INFO', 'Comentarios del autor analizados', 
                        post_id=post.id, 
                        total_author_comments=len(author_comments),
                        update_comments_found=len(updates))
                    
        except Exception as e:
            self.logger.log('WARNING', 'Error buscando updates en comentarios del autor', 
                        post_id=post.id, error=str(e))
        
        return updates

    def _find_updates_in_subreddit(self, original_post) -> List[Dict]:
        """Busca posts del mismo autor en el subreddit que sean updates."""
        updates = []
        
        try:
            if not original_post.author:
                return updates
                
            author_name = original_post.author.name
            subreddit = original_post.subreddit
            original_created = datetime.fromtimestamp(original_post.created_utc, timezone.utc)
            
            # Palabras clave para identificar updates
            update_keywords = [
                'update', 'actualización', 'edit', 'follow up', 'followup', 
                'part 2', 'part two', 'continuation', 'final update'
            ]
            
            # Buscar posts del autor posteriores al original
            author_posts = list(subreddit.search(f'author:{author_name}', limit=50, sort='new'))
            
            for post in author_posts:
                if (post.id != original_post.id and 
                    post.created_utc > original_post.created_utc and
                    post.author and post.author.name == author_name):
                    
                    # Verificar si el título o contenido sugiere que es un update
                    title_lower = post.title.lower()
                    text_lower = post.selftext.lower() if post.selftext else ""
                    
                    # Buscar referencias al post original
                    original_title_words = set(original_post.title.lower().split())
                    post_title_words = set(title_lower.split())
                    title_overlap = len(original_title_words.intersection(post_title_words))
                    
                    is_update = (
                        any(keyword in title_lower for keyword in update_keywords) or
                        any(keyword in text_lower for keyword in update_keywords) or
                        original_post.id in text_lower or
                        title_overlap >= 3  # Títulos similares
                    )
                    
                    if is_update:
                        updates.append({
                            'id': post.id,
                            'type': 'subreddit_post',
                            'text': f"TÍTULO: {post.title}\n\n{post.selftext}",
                            'source': f'subreddit_post_{post.id}',
                            'created_utc': datetime.fromtimestamp(post.created_utc, timezone.utc),
                            'upvotes': post.score,
                            'url': f'https://www.reddit.com{post.permalink}'
                        })
                        
        except Exception as e:
            self.logger.log('WARNING', 'Error buscando updates en subreddit', 
                        post_id=original_post.id, error=str(e))
        
        return updates

    def _find_updates_in_user_profile(self, original_post) -> List[Dict]:
        """Busca updates en el perfil del usuario."""
        updates = []
        
        try:
            if not original_post.author:
                return updates
                
            author = original_post.author
            original_created = datetime.fromtimestamp(original_post.created_utc, timezone.utc)
            
            # Palabras clave más específicas para el perfil
            update_keywords = [
                'update', 'actualización', 'follow up', 'followup', 
                'final update', 'last update', 'conclusion'
            ]
            
            # Obtener posts recientes del usuario
            user_posts = list(author.submissions.new(limit=25))
            
            for post in user_posts:
                if (post.id != original_post.id and 
                    post.created_utc > original_post.created_utc):
                    
                    title_lower = post.title.lower()
                    text_lower = post.selftext.lower() if post.selftext else ""
                    
                    # Buscar menciones explícitas del post original o palabras clave
                    is_related_update = (
                        original_post.id in text_lower or
                        any(keyword in title_lower for keyword in update_keywords) or
                        any(keyword in text_lower for keyword in update_keywords[:3])  # Solo las más específicas
                    )
                    
                    # Verificar si menciona el subreddit original
                    mentions_original_subreddit = original_post.subreddit.display_name.lower() in text_lower
                    
                    if is_related_update and (mentions_original_subreddit or original_post.id in text_lower):
                        updates.append({
                            'id': post.id,
                            'type': 'profile_post',
                            'text': f"TÍTULO: {post.title}\n\nSUBREDDIT: {post.subreddit.display_name}\n\n{post.selftext}",
                            'source': f'profile_post_{post.id}',
                            'created_utc': datetime.fromtimestamp(post.created_utc, timezone.utc),
                            'upvotes': post.score,
                            'url': f'https://www.reddit.com{post.permalink}'
                        })
                        
        except Exception as e:
            self.logger.log('WARNING', 'Error buscando updates en perfil', 
                        post_id=original_post.id, error=str(e))
        
        return updates

    def _deduplicate_updates(self, updates: List[Dict]) -> List[Dict]:
        if not updates:
            return updates
            
        unique_updates = []
        seen_texts = set()
        
        for update in updates:
            try:
                # Asegurar que 'text' existe y es string
                text = update.get('text', '')
                if not isinstance(text, str):
                    continue
                    
                # Crear una "huella" del texto para detectar duplicados
                text_fingerprint = re.sub(r'\s+', ' ', text[:200].lower().strip())
                
                if text_fingerprint not in seen_texts and len(text_fingerprint) > 20:
                    seen_texts.add(text_fingerprint)
                    unique_updates.append(update)
                    
            except Exception as e:
                self.logger.log('DEBUG', 'Error procesando update en deduplicación', error=str(e))
                continue
        
        return unique_updates
    
    
    # Funciones para manejar que tipo de posts buscar
    def _get_posts_generator(self, subreddit):
        limit = self.search_params['limit']
        
        # Si hay configuración específica, usarla directamente
        if 'post_type' in self.search_params:
            post_type = self.search_params['post_type']
        else:
            # Usar la opción guardada o preguntar una vez
            if not hasattr(self, '_user_post_type_choice'):
                self._user_post_type_choice = self._get_user_post_type_choice()
            post_type = self._user_post_type_choice
        
        generators = {
            'hot': lambda: subreddit.hot(limit=limit * 3),
            'top': lambda: subreddit.top(
                time_filter=self.search_params['time_filter'], 
                limit=limit * 3
            ),
            'rising': lambda: subreddit.rising(limit=limit * 4),
            'controversial': lambda: subreddit.controversial(limit=limit * 3)
        }
        
        return generators.get(post_type, generators['hot'])()

    def _get_user_post_type_choice(self) -> str:
        options = {
            '1': 'hot',
            '2': 'top', 
            '3': 'rising',
            '4': 'controversial'
        }
        
        print(f"""
        Opciones de posts:
        1. Hot posts
        2. Top posts ({self.search_params['time_filter']})
        3. Rising posts
        4. Controversial posts
        """)
        
        while True:
            choice = input("Seleccione una opción (1-4): ").strip()
            if choice in options:
                return options[choice]
            self.logger.log('WARNING', 'Opción no válida seleccionada', choice=choice)
    

    # Funciones para obtener comentarios relevantes de los posts
    def _fetch_relevant_comments(self, post) -> List:
        relevant_comments = []
        
        try:
            comment_limit = self.search_params.get('comment_limit', 2)
            min_upvotes = self.search_params.get('min_comment_upvotes', 100)
            max_length = self.search_params.get('max_comment_length', 500)
            
            # Obtener el nombre del autor del post
            post_author = post.author.name if post.author else None
            
            # Configurar ordenamiento de comentarios
            post.comment_sort = 'top'
            post.comment_limit = comment_limit * 3  # Buffer para filtrado
            
            # Evitar cargar "more comments"
            post.comments.replace_more(limit=0)
            comments = post.comments.list()
            
            for comment in comments:
                # Verificar que el comentario no sea del autor del post
                comment_author = comment.author.name if comment.author else None
                is_not_post_author = comment_author != post_author
                
                if (is_not_post_author and 
                    self._is_valid_comment(comment, min_upvotes, max_length)):
                    relevant_comments.append(comment)
                    if len(relevant_comments) >= comment_limit:
                        break
            
        except Exception as e:
            self.logger.log('ERROR', 'Error obteniendo comentarios', 
                          post_id=post.id, error=str(e))
        
        return relevant_comments
    
    def _is_valid_comment(self, comment, min_upvotes: int, max_length: int) -> bool:
        try:
            # Verificaciones básicas de estructura
            if not (hasattr(comment, 'score') and hasattr(comment, 'body')):
                return False
                
            # Verificaciones de contenido
            if (comment.body in ['[deleted]', '[removed]'] or 
                not comment.body.strip()):
                return False
                
            # Verificaciones de calidad
            if (comment.score < min_upvotes or 
                len(comment.body) > max_length):
                return False
                
            # Excluir comentarios oficiales/automáticos
            if getattr(comment, 'stickied', False):
                return False
                
            # Opcional: Filtrar comentarios muy cortos
            if len(comment.body.strip()) < 10:
                return False
                
            return True
            
        except Exception as e:
            self.logger.log('DEBUG', 'Error validando comentario', error=str(e))
            return False
    
    
    # Maneja el time out y errores de Reddit API
    def _handle_reddit_error(self, error: RedditAPIException, subreddit: str):
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