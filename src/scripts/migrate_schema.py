#!/usr/bin/env python3
import psycopg2
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

class SchemaMigrator:
    def __init__(self):
        load_dotenv()
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
        # 🎯 Migraciones de schema organizadas por versión
        self.migrations = {
            'v1.1.0': {
                'description': 'Agregar columnas de análisis de sentimientos',
                'migrations': [
                    {
                        'table': 'posts',
                        'changes': [
                            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS sentiment_score FLOAT",
                            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS category_tags TEXT[]",
                            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS word_count INTEGER DEFAULT 0"
                        ]
                    },
                    {
                        'table': 'comments',
                        'changes': [
                            "ALTER TABLE comments ADD COLUMN IF NOT EXISTS sentiment_score FLOAT"
                        ]
                    }
                ]
            },
            'v1.2.0': {
                'description': 'Agregar tabla de análisis de texto',
                'migrations': [
                    {
                        'table': 'text_analysis',
                        'changes': [
                            """
                            CREATE TABLE IF NOT EXISTS text_analysis (
                                id SERIAL PRIMARY KEY,
                                post_id TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
                                keywords TEXT[],
                                topics TEXT[],
                                readability_score FLOAT,
                                language TEXT DEFAULT 'en',
                                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                            """,
                            "CREATE INDEX IF NOT EXISTS idx_text_analysis_post_id ON text_analysis(post_id)"
                        ]
                    }
                ]
            }
        }
    
    def _get_db_connection(self, database_name):
        """Obtener conexión a una base de datos específica."""
        return psycopg2.connect(database=database_name, **self.db_config)
    
    def _get_all_story_databases(self):
        """Obtener todas las bases de datos de historias."""
        conn = psycopg2.connect(database='postgres', **self.db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT datname FROM pg_database 
            WHERE datname LIKE '%_stories'
            AND datname NOT IN ('postgres', 'template0', 'template1')
        """)
        
        databases = [row[0] for row in cursor.fetchall()]
        conn.close()
        return databases
    
    def _ensure_migration_table(self, database_name):
        """Asegurar que existe la tabla de control de migraciones."""
        conn = self._get_db_connection(database_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version TEXT UNIQUE NOT NULL,
                description TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_applied_migrations(self, database_name):
        """Obtener migraciones ya aplicadas."""
        try:
            conn = self._get_db_connection(database_name)
            cursor = conn.cursor()
            
            cursor.execute("SELECT version FROM schema_migrations ORDER BY applied_at")
            applied = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return applied
        except:
            return []
    
    def _apply_migration_to_database(self, database_name, version, migration_data):
        """Aplicar una migración específica a una base de datos."""
        print(f"  🔧 Aplicando migración {version} a {database_name}")
        
        conn = self._get_db_connection(database_name)
        cursor = conn.cursor()
        
        try:
            # Aplicar cada cambio de la migración
            for migration in migration_data['migrations']:
                table_name = migration['table']
                print(f"    📋 Modificando tabla: {table_name}")
                
                for change in migration['changes']:
                    cursor.execute(change)
                    print(f"      ✅ {change[:50]}...")
            
            # Registrar migración como aplicada
            cursor.execute("""
                INSERT INTO schema_migrations (version, description)
                VALUES (%s, %s)
                ON CONFLICT (version) DO NOTHING
            """, (version, migration_data['description']))
            
            conn.commit()
            print(f"    ✅ Migración {version} aplicada exitosamente")
            
        except Exception as e:
            conn.rollback()
            print(f"    ❌ Error aplicando migración {version}: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_all_databases(self):
        """Aplicar migraciones pendientes a todas las bases de datos."""
        print("🚀 Iniciando migración de schema en todas las bases de datos...")
        
        databases = self._get_all_story_databases()
        print(f"📊 Bases de datos encontradas: {databases}")
        
        for database_name in databases:
            print(f"\n🔍 Procesando base de datos: {database_name}")
            
            # Asegurar tabla de control
            self._ensure_migration_table(database_name)
            
            # Obtener migraciones aplicadas
            applied_migrations = self._get_applied_migrations(database_name)
            print(f"  📋 Migraciones aplicadas: {applied_migrations}")
            
            # Aplicar migraciones pendientes
            pending_count = 0
            for version, migration_data in self.migrations.items():
                if version not in applied_migrations:
                    print(f"  🆕 Migración pendiente: {version} - {migration_data['description']}")
                    self._apply_migration_to_database(database_name, version, migration_data)
                    pending_count += 1
                else:
                    print(f"  ✅ Migración ya aplicada: {version}")
            
            if pending_count == 0:
                print(f"  ✅ No hay migraciones pendientes para {database_name}")
            else:
                print(f"  🎉 {pending_count} migraciones aplicadas a {database_name}")
        
        print("\n🎉 Migración de schema completada!")
    
    def migrate_specific_database(self, database_name):
        """Aplicar migraciones a una base de datos específica."""
        print(f"🚀 Migrando schema en base de datos: {database_name}")
        
        # Verificar que la DB existe
        databases = self._get_all_story_databases()
        if database_name not in databases:
            print(f"❌ Base de datos '{database_name}' no encontrada")
            print(f"📊 Bases de datos disponibles: {databases}")
            return False
        
        # Asegurar tabla de control
        self._ensure_migration_table(database_name)
        
        # Obtener migraciones aplicadas
        applied_migrations = self._get_applied_migrations(database_name)
        print(f"📋 Migraciones aplicadas: {applied_migrations}")
        
        # Aplicar migraciones pendientes
        pending_count = 0
        for version, migration_data in self.migrations.items():
            if version not in applied_migrations:
                print(f"🆕 Aplicando migración: {version} - {migration_data['description']}")
                self._apply_migration_to_database(database_name, version, migration_data)
                pending_count += 1
            else:
                print(f"✅ Migración ya aplicada: {version}")
        
        if pending_count == 0:
            print(f"✅ No hay migraciones pendientes")
        else:
            print(f"🎉 {pending_count} migraciones aplicadas")
        
        return True
    
    def show_migration_status(self):
        """Mostrar estado de migraciones en todas las bases de datos."""
        print("📊 ESTADO DE MIGRACIONES")
        print("="*60)
        
        databases = self._get_all_story_databases()
        
        for database_name in databases:
            print(f"\n🏷️  {database_name.upper()}")
            
            self._ensure_migration_table(database_name)
            applied_migrations = self._get_applied_migrations(database_name)
            
            for version, migration_data in self.migrations.items():
                status = "✅" if version in applied_migrations else "⏳"
                print(f"  {status} {version}: {migration_data['description']}")

def main():
    migrator = SchemaMigrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--all':
            migrator.migrate_all_databases()
        elif command == '--status':
            migrator.show_migration_status()
        elif command.startswith('--db='):
            database_name = command.split('=')[1]
            migrator.migrate_specific_database(database_name)
        else:
            print("❌ Comando no reconocido")
            print("Uso:")
            print("  python scripts/migrate_schema.py --all              # Migrar todas las DB")
            print("  python scripts/migrate_schema.py --db=aita_stories  # Migrar DB específica")
            print("  python scripts/migrate_schema.py --status           # Ver estado")
    else:
        # Modo interactivo
        migrator.show_migration_status()
        
        choice = input("\n¿Aplicar migraciones pendientes a todas las DB? (s/n): ")
        if choice.lower() in ['s', 'si', 'y', 'yes']:
            migrator.migrate_all_databases()

if __name__ == '__main__':
    main()