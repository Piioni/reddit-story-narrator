import praw
import sqlite3
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import List, Dict, Optional

class RedditScraper:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        password: str,
        user_agent: str,
        username: str,
        subreddits: List[str],
        search_params: Dict = None,
        cache_db: str = 'reddit_cache.db'
    ):
    
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.subreddits = subreddits
        self.search_params = search_params or {
            'time_filter': 'week',
            'min_upvotes': 250,
            'limit': 5
        }
        self.cache_db = cache_db
        self._init_db()
        self._setup_logging()


    def fetch_posts(self) -> List[Dict]:
        posts_data = []
        min_upvotes = self.search_params['min_upvotes']
        limit = self.search_params['limit']
        
        for subreddit in self.subreddits:
            try:
                self.logger.info(f"Scrapeando subreddit: r/{subreddit}")
                
                posts = self.reddit.subreddit(subreddit).top(
                    time_filter=self.search_params['time_filter'],
                    limit=limit * 3  # Buscar más para compensar filtros
                )
                
                for post in posts:
                    if len(posts_data) >= limit:
                        break
                        
                    if (post.score >= min_upvotes and 
                        not self._is_processed(post.id) and 
                        not post.over_18):  # Ignorar NSFW
                        
                        posts_data.append({
                            'id': post.id,
                            'subreddit': str(post.subreddit),
                            'title': post.title,
                            'text': post.selftext,
                            'upvotes': post.score,
                            'url': f'https://reddit.com{post.permalink}',
                            'created_utc': post.created_utc,
                            'media': self._extract_media(post)
                        })
                        self._mark_as_processed(post)
                        self.logger.info(f"Nuevo post: {post.title[:60]}... (↑{post.score})")
                        
            except praw.exceptions.APIException as e:
                if "RATELIMIT" in str(e):
                    wait_time = int(re.search(r'wait (\d+)', str(e)).group(1))
                    self._handle_rate_limit(wait_time)
                else:
                    self.logger.error(f"Error en r/{subreddit}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error inesperado en r/{subreddit}: {str(e)}")
                
        return posts_data

    def _extract_media(self, post) -> Dict:
        media = {
            'type': None,
            'url': None,
            'is_gallery': False,
            'gallery_items': []
        }
        
        # Imagen
        if hasattr(post, 'post_hint') and 'image' in post.post_hint:
            media.update({
                'type': 'image',
                'url': post.url
            })
            
        return media

    def _is_processed(self, post_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM scraped_posts WHERE id = ?', (post_id,))
        return cursor.fetchone() is not None

    def _mark_as_processed(self, post) -> None:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO scraped_posts 
            (id, subreddit, title, created_utc, processed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            post.id,
            str(post.subreddit),
            post.title,
            post.created_utc,
            datetime.now().timestamp()
        ))
        self.conn.commit()

    def _handle_rate_limit(self, retry_after: int):
        self.logger.warning(f"Rate limit alcanzado. Esperando {retry_after} segundos...")
        time.sleep(retry_after + 2)

    def _setup_logging(self):
        self.logger = logging.getLogger('RedditTikTokScraper')
        self.logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Handler para archivo
        file_handler = logging.FileHandler('reddit_scraper.log')
        file_handler.setFormatter(formatter)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _init_db(self):
        self.conn = sqlite3.connect(self.cache_db)
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_posts (
                id TEXT PRIMARY KEY,
                subreddit TEXT,
                title TEXT,
                created_utc REAL,
                processed_at REAL
            )
        ''')
        self.conn.commit()


    def close(self):
        """Cierra conexiones y libera recursos."""
        self.conn.close()
        self.logger.info("Recursos liberados y conexiones cerradas")