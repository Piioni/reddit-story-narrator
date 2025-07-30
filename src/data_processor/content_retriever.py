import psycopg2
import psycopg2.extras
from typing import List, Dict
from utils.models import RedditPost
from utils.logger import StructuredLogger

class ContentRetriever:   
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.logger = StructuredLogger('ContentRetriever')
    
    
    def get_unprocessed_posts(self, category: str, limit: int = 1) -> List[RedditPost]:
        database_name = f"{category}_stories"
        
        try:
            conn = psycopg2.connect(database=database_name, **self.db_config)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Query unificada que obtiene posts con updates y comentarios
            query = """
                SELECT 
                    p.post_id, p.author, p.subreddit, p.title, p.text, 
                    p.upvotes, p.url, p.created_utc, p.is_nsfw, p.status,
                    
                    -- Obtener updates ordenados
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'update_id', u.update_id,
                                'text', u.update_text,
                                'created_utc', u.created_utc,
                                'type', u.type,
                                'upvotes', u.upvotes,
                                'update_order', u.update_order
                            ) ORDER BY u.update_order
                        ) FILTER (WHERE u.update_id IS NOT NULL), 
                        '[]'::json
                    ) as updates,
                    
                    -- Obtener comentarios top
                    COALESCE(
                        (SELECT json_agg(
                            json_build_object(
                                'comment_id', c.comment_id,
                                'author', c.author,
                                'text', c.text,
                                'upvotes', c.upvotes
                            ) ORDER BY c.upvotes DESC
                        ) FROM comments c WHERE c.post_id = p.post_id LIMIT 2),  
                        '[]'::json
                    ) as comments
                    
                FROM posts p
                LEFT JOIN updates u ON p.post_id = u.post_id
                WHERE 
                    p.status = 'unprocessed'  
                GROUP BY p.post_id, p.author, p.subreddit, p.title, p.text, 
                         p.upvotes, p.url, p.created_utc, p.is_nsfw, p.status
                ORDER BY p.upvotes DESC, p.created_utc DESC
                LIMIT %s
            """

            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to RedditPost objects
            posts = []
            for row in rows:
                post = RedditPost(
                    post_id=row['post_id'],
                    title=row['title'],
                    text=row['text'],
                    author=row['author'],
                    subreddit=row['subreddit'],
                    upvotes=row['upvotes'],
                    url=row['url'],
                    created_utc=row['created_utc'],
                    is_nsfw=row['is_nsfw'],
                    status=row['status'],
                    updates=row['updates'] or [],
                    comments=row['comments'] or []
                )
                posts.append(post)
            
            self.logger.info("Posts no procesados obtenidos", 
                           category=category, count=len(posts))
            
            return posts
            
        except Exception as e:
            self.logger.error("Error obteniendo posts no procesados", 
                            category=category, error=str(e))
            return []
    
    def mark_as_processing(self, post_id: str, category: str) -> bool:
        database_name = f"{category}_stories"
        
        try:
            conn = psycopg2.connect(database=database_name, **self.db_config)
            cursor = conn.cursor()
            
            # Insert or update processing status
            cursor.execute("""
                UPDATE posts SET status = 'processing' WHERE post_id = %s
            """, (post_id,))
            
            conn.commit()
            conn.close()
            
            self.logger.info("Post marcado como en proceso", post_id=post_id)
            return True
            
        except Exception as e:
            self.logger.error("Error marcando post como en proceso", 
                            post_id=post_id, error=str(e))
            return False
    
    def mark_as_completed(self, post_id: str, category: str, video_path: str) -> bool:
        database_name = f"{category}_stories"
        
        try:
            conn = psycopg2.connect(database=database_name, **self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE posts SET
                    status = 'completed'
                WHERE post_id = %s
            """, (post_id,))
            
            conn.commit()
            conn.close()
            
            self.logger.info("Post marcado como completado", 
                           post_id=post_id, video_path=video_path)
            return True
            
        except Exception as e:
            self.logger.error("Error marcando post como completado", 
                            post_id=post_id, error=str(e))
            return False