#!/usr/bin/env python3
import psycopg2
from psycopg2.extensions import cursor as Cursor
from typing import List, Dict, Optional, Any
from datetime import datetime
from utils.models import DatabaseConfig

class DatabaseManager:
    def __init__(self, config: DatabaseConfig, logger):
        self.config = config
        self.logger = logger
        self.connection: Optional[psycopg2.extensions.connection] = None
        self._connect()
    
    def _connect(self):
        try:
            self.connection = psycopg2.connect(
                host=self.config.host,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
            self.connection.autocommit = False  
            
            self.logger.info("Conexión a base de datos establecida", 
                           database=self.config.database)
            
        except Exception as e:
            self.logger.error("Error conectando a base de datos", 
                            database=self.config.database, error=str(e))
            raise

    def get_cursor(self) -> Cursor:
        if self.connection is None:
            raise Exception("No hay conexión a la base de datos")
        return self.connection.cursor()
    
    def initialize_schema(self):
        try:
            cursor = self.get_cursor()
            
            # Verificar que las tablas principales existan
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('posts', 'updates', 'comments', 'local_stats')
            """)
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            required_tables = ['posts', 'updates', 'comments', 'local_stats']
            
            missing_tables = set(required_tables) - set(existing_tables)
            
            if missing_tables:
                self.logger.error("Tablas faltantes en base de datos", 
                                missing_tables=list(missing_tables),
                                database=self.config.database)
                raise Exception(f"Tablas faltantes: {missing_tables}")
            
            self.logger.info("Schema de base de datos verificado", 
                           database=self.config.database)
            
        except Exception as e:
            self.logger.error("Error verificando schema", error=str(e))
            raise
    
    def is_processed(self, post_id: str) -> bool:
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT 1 FROM posts WHERE post_id = %s LIMIT 1", (post_id,))
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            self.logger.warning("Error verificando si post fue procesado", 
                              post_id=post_id, error=str(e))
            return False
    
    def save_post_data(self, post_data: Dict, updates: List[Dict], comments: List) -> bool:
        try:
            cursor = self.get_cursor()
            
            # Verificar si el post ya existe
            if self.is_processed(post_data['id']):
                self.logger.info("Post ya existe, saltando", post_id=post_data['id'])
                return True
            
            # Iniciar transacción
            if self.connection:
                self.connection.rollback() 
            
            # 1. Insertar post principal
            post_id = self._insert_post(cursor, post_data)
            if not post_id:
                if self.connection:
                    self.connection.rollback()
                return False
            
            # 2. Insertar updates si existen
            if updates:
                self._insert_updates(cursor, updates, post_data['id'])

            
            # 3. Insertar comentarios si existen
            if comments:
                self._insert_comments(cursor, comments, post_data['id'])

            
            # Confirmar transacción
            if self.connection:
                self.connection.commit()
            
            return True
            
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            self.logger.error("Error guardando post", 
                            post_id=post_data.get('id', 'unknown'), 
                            error=str(e))
            return False
    
    def _insert_post(self, cursor: Cursor, post_data: Dict) -> Optional[str]:
        try:
            insert_sql = """
                INSERT INTO posts (
                    post_id, author, subreddit, title, text, upvotes, 
                    url, created_utc, is_nsfw
                ) VALUES (
                    %(id)s, %(author)s, %(subreddit)s, %(title)s, %(text)s, 
                    %(upvotes)s, %(url)s, %(created_utc)s, %(is_nsfw)s
                )
                RETURNING post_id
            """
            
            cursor.execute(insert_sql, post_data)
            result = cursor.fetchone()
            
            if result:
                return result[0]
            return None
            
        except Exception as e:
            self.logger.error("Error insertando post", 
                            post_id=post_data.get('id', 'unknown'), 
                            error=str(e))
            return None
    
    def _insert_updates(self, cursor: Cursor, updates: List[Dict], post_id: str) -> int:
        inserted_count = 0
        
        for i, update in enumerate(updates):
            try:
                # Preparar datos del update
                update_data = {
                    'update_id': update.get('update_id', f'update_{i}'),
                    'post_id': post_id,
                    'type': update.get('type', 'unknown'),
                    'update_text': update.get('update_text', ''),
                    'update_order': i + 1,
                    'created_utc': update.get('created_utc', datetime.utcnow()),
                    'upvotes': update.get('upvotes', 0),
                    'url': update.get('url', None)
                }
                
                insert_sql = """
                    INSERT INTO updates (
                        update_id, post_id, type, update_text, update_order,
                        created_utc, upvotes, url
                    ) VALUES (
                        %(update_id)s, %(post_id)s, %(type)s, %(update_text)s, 
                        %(update_order)s, %(created_utc)s, %(upvotes)s, %(url)s
                    )
                    ON CONFLICT (update_id) DO NOTHING
                """
                
                cursor.execute(insert_sql, update_data)
                
                # Verificar si se insertó (no era duplicado)
                if cursor.rowcount > 0:
                    inserted_count += 1
                
            except Exception as e:
                self.logger.warning("Error insertando update", 
                                  post_id=post_id, 
                                  update_id=update.get('id', f'update_{i}'),
                                  error=str(e))
                continue
        
        return inserted_count
    
    def _insert_comments(self, cursor: Cursor, comments: List, post_id: str) -> int:
        inserted_count = 0
        
        for comment in comments:
            try:
                # Preparar datos del comentario
                comment_data = {
                    'comment_id': comment.id,
                    'post_id': post_id,
                    'author': comment.author.name if comment.author else '[deleted]',
                    'text': comment.body,
                    'upvotes': getattr(comment, 'score', 0),
                    'created_utc': datetime.fromtimestamp(comment.created_utc, 
                                                        tz=datetime.now().astimezone().tzinfo)
                }
                
                insert_sql = """
                    INSERT INTO comments (
                        comment_id, post_id, author, text, upvotes, created_utc
                    ) VALUES (
                        %(comment_id)s, %(post_id)s, %(author)s, %(text)s, 
                        %(upvotes)s, %(created_utc)s
                    )
                    ON CONFLICT (comment_id) DO NOTHING
                """
                
                cursor.execute(insert_sql, comment_data)
                
                # Verificar si se insertó (no era duplicado)
                if cursor.rowcount > 0:
                    inserted_count += 1
                
            except Exception as e:
                self.logger.warning("Error insertando comentario", 
                                  post_id=post_id,
                                  comment_id=getattr(comment, 'id', 'unknown'),
                                  error=str(e))
                continue
        
        return inserted_count
    
    def get_stats(self) -> Dict[str, Any]:
        try:
            cursor = self.get_cursor()
            
            cursor.execute("""
                SELECT stat_name, stat_value, last_updated 
                FROM local_stats 
                ORDER BY stat_name
            """)
            
            stats = {}
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'value': row[1],
                    'last_updated': row[2]
                }
            
            return stats
            
        except Exception as e:
            self.logger.error("Error obteniendo estadísticas", error=str(e))
            return {}
    
    def close(self):
        if self.connection:
            self.connection.close()
            self.logger.info("Conexión a base de datos cerrada")