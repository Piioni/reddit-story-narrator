import psycopg2
import os
import time
import sys
from dotenv import load_dotenv

class DatabaseMigrator:
    def __init__(self):
        load_dotenv()
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.environ['POSTGRES_PASSWORD'],
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
        # 🎯 ÚNICA FUENTE DE VERDAD para categorías
        self.target_categories = {
            'aita_stories': ['AmItheAsshole', 'AITAH'],
            'relationship_stories': ['relationship_advice', 'relationships'],
            'legal_stories': ['legaladvice', 'bestoflegaladvice'],
            'work_stories': ['antiwork', 'MaliciousCompliance', 'pettyrevenge'],
            'tech_stories': ['programming', 'webdev', 'learnprogramming'],
            'creepypastas': ['creepy', 'creepypasta'],
        }
    
    def wait_for_postgres(self, max_retries=10, delay=3):
        print("🔍 Esperando a que PostgreSQL esté listo...")

        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(database='postgres', **self.db_config)
                conn.close()
                print("✅ PostgreSQL está listo!")
                return True
            except psycopg2.OperationalError:
                if attempt < max_retries - 1:
                    print(f"⏳ Intento {attempt + 1}/{max_retries} - Esperando {delay}s...")
                    time.sleep(delay)
                else:
                    print("❌ No se pudo conectar a PostgreSQL")
                    return False
        return False
    
    def initialize_complete_system(self):
        print("🚀 Inicializando sistema completo de Reddit Scraper...")
        
        # Esperar a PostgreSQL
        if not self.wait_for_postgres():
            sys.exit(1)
        
        # Crear DB administrativa
        self._ensure_admin_database()
        
        # Crear todas las categorías
        self.check_and_create_missing_categories()
        
        print("🎉 Sistema inicializado completamente!")
        

    # Metodos para incializar la base de datos administrativa junto con su esquema
    def _ensure_admin_database(self):
        print("📊 Verificando base de datos administrativa...")
        
        # Verificar si reddit_admin existe
        existing_dbs = self._get_existing_databases()
        
        if 'reddit_admin' not in existing_dbs:
            print("🆕 Creando base de datos administrativa: reddit_admin")
            self._create_admin_database()
            self._create_admin_schema()
        else:
            print("✅ Base de datos administrativa ya existe")
    
    def _create_admin_database(self):
        conn = psycopg2.connect(database='postgres', **self.db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE reddit_admin")
        cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE reddit_admin TO {self.db_config['user']}")
        
        conn.close()
        print("  ✅ Base de datos reddit_admin creada")
    
    def _create_admin_schema(self):
        conn = psycopg2.connect(database='reddit_admin', **self.db_config)
        cursor = conn.cursor()
        
        admin_schema_sql = """
        -- Configuración de categorías
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            category_name TEXT UNIQUE NOT NULL,
            database_name TEXT UNIQUE NOT NULL,
            subreddits TEXT[] NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Estadísticas por categoría
        CREATE TABLE IF NOT EXISTS category_stats (
            id SERIAL PRIMARY KEY,
            category_name TEXT UNIQUE NOT NULL,
            last_scrape TIMESTAMP,
            total_posts INTEGER DEFAULT 0,
            total_updates INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Logs de scraping
        CREATE TABLE IF NOT EXISTS scraping_logs (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            database_name TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            posts_scraped INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0
        );
        """
        
        cursor.execute(admin_schema_sql)
        conn.commit()
        conn.close()
        print("  ✅ Schema administrativo creado")
    
    def check_and_create_missing_categories(self):
        print("🔍 Verificando categorías existentes...")
        
        existing_dbs = self._get_existing_databases()
        existing_categories = self._get_existing_categories()
        
        print(f"📊 Bases de datos existentes: {existing_dbs}")
        print(f"📋 Categorías registradas: {list(existing_categories.keys())}")
        
        for db_name, subreddits in self.target_categories.items():
            category_name = db_name.replace('_stories', '')
            
            # Verificar si la DB existe
            if db_name not in existing_dbs:
                print(f"🆕 Creando nueva base de datos: {db_name}")
                self._create_database(db_name)
                self._apply_schema_to_database(db_name)
            else:
                print(f"✅ Base de datos {db_name} ya existe")
            
            # Verificar si la categoría está registrada
            if category_name not in existing_categories:
                print(f"📝 Registrando nueva categoría: {category_name}")
                self._register_category(category_name, db_name, subreddits)
            else:
                print(f"✅ Categoría {category_name} ya registrada")
    
    def _get_existing_databases(self):
        conn = psycopg2.connect(database='postgres', **self.db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT datname FROM pg_database 
            WHERE datname NOT IN ('postgres', 'template0', 'template1')
            AND datname NOT LIKE 'pg_%'
        """)
        
        databases = [row[0] for row in cursor.fetchall()]
        conn.close()
        return databases
    
    def _get_existing_categories(self):
        try:
            conn = psycopg2.connect(database='reddit_admin', **self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("SELECT category_name, database_name FROM categories")
            categories = dict(cursor.fetchall())
            
            conn.close()
            return categories
        except:
            return {}
    
    def _create_database(self, db_name):
        conn = psycopg2.connect(database='postgres', **self.db_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"CREATE DATABASE {db_name}")
        cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {self.db_config['user']}")
        
        conn.close()
        print(f"  ✅ Base de datos {db_name} creada")
    
    def _apply_schema_to_database(self, db_name):
        conn = psycopg2.connect(database=db_name, **self.db_config)
        cursor = conn.cursor()
        
        # Schema completo con triggers
        schema_sql = """
        -- Tabla principal de posts
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            post_id TEXT UNIQUE NOT NULL,
            author TEXT NOT NULL,
            subreddit TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            upvotes INTEGER NOT NULL,
            url TEXT,
            created_utc TIMESTAMP NOT NULL,
            is_nsfw BOOLEAN DEFAULT FALSE,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'unprocessed'
        );

        -- Tabla de updates/edits de posts
        CREATE TABLE IF NOT EXISTS updates (
            id SERIAL PRIMARY KEY,
            update_id TEXT UNIQUE NOT NULL,
            post_id TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            update_text TEXT NOT NULL,
            update_order INTEGER NOT NULL,
            created_utc TIMESTAMP NOT NULL,
            upvotes INTEGER DEFAULT 0,
            url TEXT
        );

        -- Tabla de comentarios relevantes
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            comment_id TEXT UNIQUE NOT NULL,
            post_id TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
            author TEXT,
            text TEXT NOT NULL,
            upvotes INTEGER NOT NULL,
            created_utc TIMESTAMP NOT NULL
        );

        -- Tabla local de estadísticas
        CREATE TABLE IF NOT EXISTS local_stats (
            stat_name TEXT PRIMARY KEY,
            stat_value INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Inicializar estadísticas
        INSERT INTO local_stats (stat_name, stat_value) VALUES 
            ('total_posts', 0),
            ('total_updates', 0),
            ('total_comments', 0)
        ON CONFLICT (stat_name) DO NOTHING;

        -- FUNCIÓN para actualizar estadísticas automáticamente
        CREATE OR REPLACE FUNCTION update_local_stats()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE local_stats SET 
            stat_value = (SELECT COUNT(*) FROM posts),
            last_updated = CURRENT_TIMESTAMP
            WHERE stat_name = 'total_posts';
            
            UPDATE local_stats SET 
            stat_value = (SELECT COUNT(*) FROM updates),
            last_updated = CURRENT_TIMESTAMP
            WHERE stat_name = 'total_updates';
            
            UPDATE local_stats SET 
            stat_value = (SELECT COUNT(*) FROM comments),
            last_updated = CURRENT_TIMESTAMP
            WHERE stat_name = 'total_comments';
            
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;

        -- TRIGGERS automáticos
        DROP TRIGGER IF EXISTS trigger_posts_stats ON posts;
        CREATE TRIGGER trigger_posts_stats
            AFTER INSERT OR DELETE ON posts
            FOR EACH STATEMENT
            EXECUTE FUNCTION update_local_stats();

        DROP TRIGGER IF EXISTS trigger_updates_stats ON updates;
        CREATE TRIGGER trigger_updates_stats
            AFTER INSERT OR DELETE ON updates
            FOR EACH STATEMENT
            EXECUTE FUNCTION update_local_stats();

        DROP TRIGGER IF EXISTS trigger_comments_stats ON comments;
        CREATE TRIGGER trigger_comments_stats
            AFTER INSERT OR DELETE ON comments
            FOR EACH STATEMENT
            EXECUTE FUNCTION update_local_stats();

        -- Índices
        CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
        CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_posts_upvotes ON posts(upvotes DESC);
        CREATE INDEX IF NOT EXISTS idx_updates_post_id ON updates(post_id);
        CREATE INDEX IF NOT EXISTS idx_updates_order ON updates(post_id, update_order);
        CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
        CREATE INDEX IF NOT EXISTS idx_comments_upvotes ON comments(upvotes DESC);
        """
        
        cursor.execute(schema_sql)
        conn.commit()
        conn.close()
        print(f"  ✅ Schema aplicado a {db_name}")
    
    def _register_category(self, category_name, database_name, subreddits):
        conn = psycopg2.connect(database='reddit_admin', **self.db_config)
        cursor = conn.cursor()
        
        description = f"Database for {', '.join(subreddits)} stories"
        
        cursor.execute("""
            INSERT INTO categories (category_name, database_name, subreddits, description) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (category_name) DO UPDATE SET 
                subreddits = EXCLUDED.subreddits,
                description = EXCLUDED.description
        """, (category_name, database_name, subreddits, description))
        
        cursor.execute("""
            INSERT INTO category_stats (category_name) 
            VALUES (%s)
            ON CONFLICT (category_name) DO NOTHING
        """, (category_name,))
        
        conn.commit()
        conn.close()
        print(f"  ✅ Categoría {category_name} registrada")

def main():
    migrator = DatabaseMigrator()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--init':
        # Modo inicialización completa
        migrator.initialize_complete_system()
    else:
        # Modo migración (por defecto)
        migrator.check_and_create_missing_categories()
        print("🎉 Migración completada!")

if __name__ == '__main__':
    main()