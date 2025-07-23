import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from utils.logger import StructuredLogger

@dataclass
class DatabaseConfig:
    host: str
    database: str
    user: str
    password: str
    port: int = 5432

class DatabaseManager:
    def __init__(self, config: DatabaseConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self.conn = None
        self._connect()
    
    def _connect(self, max_retries: int = 3, retry_delay: int = 5):
        """Establece conexión con la base de datos con reintentos."""
        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=self.config.host,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                    port=self.config.port
                )
                self.conn.autocommit = False
                self.logger.log('INFO', 'Conexión a PostgreSQL establecida')
                return
                
            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:
                    self.logger.log('ERROR', 'No se pudo conectar a PostgreSQL', error=str(e))
                    raise
                self.logger.log('WARNING', f'Intentando conectar a PostgreSQL (intento {attempt + 1})', error=str(e))
                time.sleep(retry_delay)
    
    def initialize_schema(self, schema_path: str = '/app/config/schema.sql'):
        """Inicializa las tablas de la base de datos."""
        try:
            with open(schema_path, 'r') as f:
                schema = f.read()
            
            with self.conn.cursor() as cursor:
                cursor.execute(schema)
            self.conn.commit()
            self.logger.log('INFO', 'Schema de base de datos inicializado')
            
        except Exception as e:
            self.conn.rollback()
            self.logger.log('ERROR', 'Error inicializando schema', error=str(e))
            raise
    
    def is_processed(self, post_id: str) -> bool:
        """Verifica si un post ya fue procesado."""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('SELECT id FROM posts WHERE id = %s', (post_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.log('ERROR', 'Error verificando post procesado', post_id=post_id, error=str(e))
            return False
    
    def save_post_data(self, post_data: Dict, updates: List[Dict], comments: List) -> bool:
        """Guarda un post completo con sus updates y comentarios."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with self.conn.cursor() as cursor:
                    # Insertar post principal
                    cursor.execute("""
                        INSERT INTO posts (
                            id, subreddit, title, text, upvotes, url, 
                            created_utc, media_type, media_url, is_nsfw, full_narrative
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (
                        post_data['id'],
                        post_data['subreddit'],
                        post_data['title'],
                        post_data['text'],
                        post_data['upvotes'],
                        post_data['url'],
                        post_data['created_utc'],
                        post_data.get('media', {}).get('type', 'text'),
                        post_data.get('media', {}).get('url'),
                        post_data['is_nsfw'],
                        post_data['full_narrative']
                    ))
                    
                    # Insertar updates si existen
                    if updates:
                        update_records = [
                            (
                                f"update_{post_data['id']}_{i}",
                                post_data['id'],
                                update['text'],
                                i,
                                post_data['created_utc']
                            )
                            for i, update in enumerate(updates)
                        ]
                        execute_batch(cursor, """
                            INSERT INTO updates (id, post_id, update_text, update_order, created_utc)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                        """, update_records)
                    
                    # Insertar comentarios si existen
                    if comments:
                        comment_records = [
                            (
                                comment.id,
                                post_data['id'],
                                str(comment.author) if comment.author else '[deleted]',
                                comment.body,
                                comment.score,
                                comment.is_submitter,
                                getattr(comment, 'is_premium', False),
                                datetime.utcfromtimestamp(comment.created_utc)
                            )
                            for comment in comments
                        ]
                        execute_batch(cursor, """
                            INSERT INTO comments (
                                id, post_id, author, text, upvotes, is_submitter, is_premium, created_utc
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                        """, comment_records)
                
                self.conn.commit()
                return True
                
            except psycopg2.IntegrityError as e:
                self.conn.rollback()
                if "duplicate key" in str(e).lower():
                    self.logger.log('WARNING', 'Post ya existe', post_id=post_data['id'])
                    return True
                raise
                
            except Exception as e:
                self.conn.rollback()
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log('ERROR', 'Error al guardar en DB tras reintentos', 
                                  post_id=post_data['id'], error=str(e))
                    return False
                
                # Backoff exponencial
                time.sleep(2 ** retry_count)
        
        return False
    
    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            self.logger.log('INFO', 'Conexión a base de datos cerrada')