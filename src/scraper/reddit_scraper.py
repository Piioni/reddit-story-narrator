import praw
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from praw.exceptions import RedditAPIException, PRAWException
from scraper.database import DatabaseManager, DatabaseConfig
from utils.logger import StructuredLogger
import hashlib

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
                self.logger.info('Scrapeando subreddit', subreddit=subreddit_name)
                subreddit_posts = self._fetch_subreddit_posts(subreddit_name)
                posts_data.extend(subreddit_posts)

                self.logger.info(f'Completado subreddit {subreddit_name}', 
                              posts_found=len(subreddit_posts))
                
            except RedditAPIException as e:
                self._handle_reddit_error(e, subreddit_name)
            except PRAWException as e:
                self.logger.error('Error de PRAW', subreddit=subreddit_name, error=str(e))
            except Exception as e:
                self.logger.error('Error inesperado', subreddit=subreddit_name, error=str(e))

        return posts_data

    def _fetch_subreddit_posts(self, subreddit_name: str) -> List[Dict]:
        subreddit = self.reddit.subreddit(subreddit_name)
        limit = self.search_params['limit']
        
        # Obtener tipo de posts según configuración
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
                    self.logger.info('Post procesado', 
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
            }
            
            # Extraer updates del texto
            updates = self._extract_updates(post)

            # Obtener comentarios relevantes
            comments = self._fetch_relevant_comments(post)
            
            # Guardar en base de datos
            success = self.db_manager.save_post_data(post_data, updates, comments)
            if not success:
                self.logger.error('Error guardando post', post_id=post.id)
                return None
                        
            return post_data
            
        except Exception as e:
            self.logger.error('Error procesando post', post_id=post.id, error=str(e))
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
            
            if sorted_updates:
                self.logger.info('Updates encontrados para el post', 
                            post_id=post.id, 
                            total_updates=len(sorted_updates))
                
            return sorted_updates
                
        except Exception as e:
            self.logger.error('Error en _extract_updates', post_id=post.id, error=str(e))
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
            post.comment_limit = 25   # Límite alto para capturar todos los comentarios del autor
            
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
                has_interaction = comment.score > 25 if hasattr(comment, 'score') else False
                
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
                        'update_id': comment.id,
                        'post_id': post.id,
                        'type': 'author_comment',
                        'update_text': comment_original,
                        'created_utc': datetime.fromtimestamp(comment.created_utc, timezone.utc),
                        'upvotes': getattr(comment, 'score', 0),
                        'url': f'https://www.reddit.com{post.permalink}{comment.id}/'
                    })

        except Exception as e:
            self.logger.warning('Error buscando updates en comentarios del autor', 
                        post_id=post.id, error=str(e))
        
        return updates

    def _find_updates_in_subreddit(self, original_post) -> List[Dict]:
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
            author_posts = list(subreddit.search(f'author:{author_name}', limit=25, sort='new'))
            
            for post in author_posts:
                update_submitted_time = datetime.fromtimestamp(post.created_utc, timezone.utc)
                
                if (post.id != original_post.id and 
                    update_submitted_time > original_created and
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
                            'update_id': post.id,
                            'post_id': original_post.id,
                            'type': 'subreddit_post',
                            'update_text': f"TÍTULO: {post.title}\n\n{post.selftext}",
                            'created_utc': update_submitted_time,
                            'upvotes': post.score,
                            'url': f'https://www.reddit.com{post.permalink}'
                        })
                        
        except Exception as e:
            self.logger.warning('Error buscando updates en subreddit', 
                        post_id=original_post.id, error=str(e))
        
        return updates

    def _find_updates_in_user_profile(self, original_post) -> List[Dict]:
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
                update_submitted_time = datetime.fromtimestamp(post.created_utc, timezone.utc)
                
                if (post.id != original_post.id and 
                    update_submitted_time > original_created):
                    
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
                            'update_id': post.id,
                            'post_id': original_post.id,
                            'type': 'profile_post',
                            'update_text': f"TÍTULO: {post.title}\n\nSUBREDDIT: {post.subreddit.display_name}\n\n{post.selftext}",
                            'created_utc': update_submitted_time,
                            'upvotes': post.score,
                            'url': f'https://www.reddit.com{post.permalink}'
                        })
                        
        except Exception as e:
            self.logger.warning('Error buscando updates en perfil', 
                        post_id=original_post.id, error=str(e))
        
        return updates

    def _deduplicate_updates(self, updates: List[Dict]) -> List[Dict]:
        if not updates:
            return updates

        unique_updates = []
        seen_hashes = set()
        
        for update in updates:
            try:
                # Obtener texto del update
                text = update.get('update_text', update.get('text', ''))
                update_id = update.get('update_id', 'unknown')
                
                if not isinstance(text, str) or len(text.strip()) < 20:
                    continue
                
                # Crear hash único del contenido normalizado
                content_hash = self._create_content_hash(text)
                
                if not content_hash or content_hash in seen_hashes:
                    continue
                
                seen_hashes.add(content_hash)
                unique_updates.append(update)
                    
            except Exception as e:
                self.logger.warning('Error procesando update en deduplicación', 
                              update_id=update.get('update_id', 'unknown'), error=str(e))
                continue

        if len(updates) != len(unique_updates):
            self.logger.info('Updates deduplicados', 
                          original_count=len(updates),
                          unique_count=len(unique_updates))
        
        return unique_updates

    def _create_content_hash(self, text: str) -> Optional[str]:
        try:
            # Normalizar texto: minúsculas, remover puntuación y espacios extra
            normalized = re.sub(r'[^\w\s]', '', text.lower())
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            
            if len(normalized) < 20:
                return None
            
            # Remover palabras muy comunes que pueden aparecer en cualquier update
            stopwords = {'update', 'edit', 'edited', 'actualización', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an', 'is', 'was', 'are', 'were', 'i', 'me', 'my', 'you', 'your', 'he', 'she', 'it', 'we', 'they', 'this', 'that'}
            
            words = normalized.split()
            filtered_words = [w for w in words if len(w) > 2 and w not in stopwords]
            
            # Usar las primeras 20 palabras significativas para el hash
            content_for_hash = ' '.join(filtered_words[:20])
            
            if len(content_for_hash) < 15:
                return None
            
            # Crear hash MD5 del contenido normalizado
            return hashlib.md5(content_for_hash.encode('utf-8')).hexdigest()
            
        except Exception as e:
            self.logger.warning('Error generando hash de contenido', error=str(e))
            return None

    # TODO: Implementar una verificacion que determine si el comentario fue respondido por el autor del post e incluirlo dentro del mismo comentario
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
            self.logger.error('Error obteniendo comentarios', 
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
            self.logger.warning('Error validando comentario', error=str(e))
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

            self.logger.warning('Rate limit alcanzado',
                                subreddit=subreddit, wait_time=wait_time)
            time.sleep(wait_time + 2)
            
        elif "FORBIDDEN" in error_str:
            self.logger.error('Acceso prohibido al subreddit', subreddit=subreddit)
        elif "NOT_FOUND" in error_str:
            self.logger.error('Subreddit no encontrado', subreddit=subreddit)
        else:
            self.logger.error('Error de Reddit API',
                          subreddit=subreddit, error=str(error))

    # Funciones para manejar que tipo de posts buscar
    def _get_posts_generator(self, subreddit):
        limit = self.search_params['limit']
        
        # Usar configuración directa (sin input del usuario)
        post_type = self.search_params.get('post_type', 'hot')
        
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
    

    def close(self):
        if self.db_manager:
            self.db_manager.close()
        self.logger.info('Scraper cerrado correctamente')