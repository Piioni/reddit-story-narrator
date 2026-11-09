import psycopg2
import os
from datetime import datetime

def sync_all_stats():
    """Sincroniza estadísticas locales a la DB administrativa."""
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'user': os.getenv('POSTGRES_USER', 'scraper'),
        'password': os.environ['POSTGRES_PASSWORD'],
        'port': int(os.getenv('POSTGRES_PORT', '5432'))
    }
    
    # Obtener categorías
    admin_conn = psycopg2.connect(database='reddit_admin', **db_config)
    admin_cursor = admin_conn.cursor()
    
    admin_cursor.execute("SELECT category_name, database_name FROM categories WHERE is_active = TRUE")
    categories = admin_cursor.fetchall()
    
    print("🔄 Sincronizando estadísticas centralizadas...")
    
    for category_name, database_name in categories:
        try:
            # Obtener estadísticas locales
            content_conn = psycopg2.connect(database=database_name, **db_config)
            content_cursor = content_conn.cursor()
            
            content_cursor.execute("SELECT stat_name, stat_value FROM local_stats")
            local_stats = dict(content_cursor.fetchall())
            content_conn.close()
            
            # Actualizar en reddit_admin
            admin_cursor.execute("""
                UPDATE category_stats SET
                    total_posts = %s,
                    total_updates = %s,
                    total_comments = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE category_name = %s
            """, (
                local_stats.get('total_posts', 0),
                local_stats.get('total_updates', 0),
                local_stats.get('total_comments', 0),
                category_name
            ))
            
            print(f"  ✅ {category_name}: {local_stats}")
            
        except Exception as e:
            print(f"  ❌ Error en {category_name}: {e}")
    
    admin_conn.commit()
    admin_conn.close()
    print("✅ Sincronización completada")

if __name__ == '__main__':
    sync_all_stats()