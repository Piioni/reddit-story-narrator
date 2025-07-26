import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from scraper import RedditScraper
from utils import StructuredLogger
import psycopg2

class RedditScrapperApp:
    def __init__(self):
        load_dotenv()
        self.logger = StructuredLogger('RedditScrapperApp')
        
        # 🎯 Configuración base de DB centralizada
        self.base_db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
        # ✅ Cargar categorías (falla si no puede conectar)
        self.categories = self._load_categories_from_db()
        
    def _load_categories_from_db(self):
        """Carga categorías desde la DB administrativa. FALLA si no puede conectar."""
        try:
            print("🔍 Conectando a base de datos administrativa...")
            conn = psycopg2.connect(database='reddit_admin', **self.base_db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT category_name, database_name, subreddits, description
                FROM categories 
                ORDER BY category_name
            """)
            
            categories = {}
            for row in cursor.fetchall():
                categories[row[0]] = {
                    'database': row[1],
                    'subreddits': list(row[2]),  # PostgreSQL array to Python list
                    'description': row[3]
                }
            
            conn.close()
            
            if not categories:
                print("❌ No se encontraron categorías en la base de datos")
                print("💡 Ejecuta: python scripts/migrate_db.py --init")
                sys.exit(1)
            
            print(f"✅ Categorías cargadas: {', '.join(categories.keys())}")
            self.logger.info(f"Categorías cargadas desde DB", count=len(categories))
            return categories
            
        except psycopg2.OperationalError as e:
            print("❌ Error de conexión a PostgreSQL:")
            print(f"   {str(e)}")
            print("\n💡 Posibles soluciones:")
            print("   1. Verifica que Docker esté ejecutándose: docker-compose ps")
            print("   2. Inicia PostgreSQL: docker-compose up -d")
            print("   3. Inicializa la DB: python scripts/migrate_db.py --init")
            sys.exit(1)
            
        except psycopg2.Error as e:
            print("❌ Error en la base de datos:")
            print(f"   {str(e)}")
            print("\n💡 Solución:")
            print("   Inicializa la base de datos: python scripts/migrate_db.py --init")
            sys.exit(1)
            
        except Exception as e:
            print("❌ Error inesperado cargando categorías:")
            print(f"   {str(e)}")
            sys.exit(1)
    
    def show_menu(self):
        """Muestra menú interactivo de categorías."""
        print("\n" + "="*70)
        print("🎯 REDDIT SCRAPER - SELECCIONAR CATEGORÍA")
        print("="*70)
        
        # Mostrar categorías disponibles
        category_list = list(self.categories.keys())
        
        for i, (category, config) in enumerate(self.categories.items(), 1):
            subreddits_str = ', '.join(config['subreddits'])
            print(f"{i}. {category.upper()}")
            print(f"   📝 {config['description']}")
            print(f"   🏷️  Subreddits: {subreddits_str}")
            print(f"   📁 Base de datos: {config['database']}")
            print()
        
        print(f"{len(self.categories) + 1}. Ver estadísticas")
        print("0. Salir")
        
        while True:
            try:
                choice = input(f"\nSelecciona una categoría (0-{len(self.categories) + 1}): ").strip()
                choice_num = int(choice)
                
                if choice_num == 0:
                    return None
                elif choice_num == len(self.categories) + 1:
                    self._show_statistics()
                    continue
                elif 1 <= choice_num <= len(self.categories):
                    return category_list[choice_num - 1]
                else:
                    print("❌ Opción inválida")
            except ValueError:
                print("❌ Por favor ingresa un número válido")
    
    def _show_statistics(self):
        """Muestra estadísticas actuales de todas las categorías."""
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS ACTUALES")
        print("="*60)
        
        for category_name, config in self.categories.items():
            print(f"\n🏷️  {category_name.upper()}")
            stats = self._get_category_stats(config['database'])
            
            if stats:
                print(f"   📝 Posts: {stats.get('total_posts', 0)}")
                print(f"   🔄 Updates: {stats.get('total_updates', 0)}")
                print(f"   💬 Comments: {stats.get('total_comments', 0)}")
                
                last_updated = stats.get('last_updated', 'Nunca')
                if last_updated != 'Nunca':
                    print(f"   🕒 Última actualización: {last_updated}")
            else:
                print("   ❌ No hay datos disponibles")
        
        input("\nPresiona Enter para continuar...")
    
    def _get_category_stats(self, database_name):
        """Obtiene estadísticas de una categoría específica."""
        try:
            conn = self._get_db_connection(database_name)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stat_name, stat_value, last_updated 
                FROM local_stats 
                ORDER BY stat_name
            """)
            
            stats = {}
            for row in cursor.fetchall():
                if row[0] == 'total_posts':
                    stats['total_posts'] = row[1]
                elif row[0] == 'total_updates':
                    stats['total_updates'] = row[1]
                elif row[0] == 'total_comments':
                    stats['total_comments'] = row[1]
                
                stats['last_updated'] = row[2]
            
            conn.close()
            return stats
            
        except Exception as e:
            self.logger.warning(f"Error obteniendo estadísticas", database=database_name, error=str(e))
            return None
    
    def run_scraper(self, category_name):
        """Ejecuta el scraper para una categoría específica."""
        if category_name not in self.categories:
            print(f"❌ Categoría '{category_name}' no encontrada")
            return False
            
        config = self.categories[category_name]
        
        print(f"\n🚀 Iniciando scraper para: {category_name.upper()}")
        print(f"� Base de datos: {config['database']}")
        print(f"🏷️  Subreddits: {', '.join(config['subreddits'])}")
        print(f"📝 Descripción: {config['description']}")
        
        try:
            # Registrar inicio en logs
            log_id = self._log_scraping_start(category_name, config['database'])
            
            # Configurar scraper con DB específica
            scraper_config = self._build_scraper_config(
                subreddits=config['subreddits'],
                database=config['database']
            )
            
            # Ejecutar scraper
            scraper = RedditScraper(**scraper_config)
            posts = scraper.fetch_posts()
            
            # Registrar finalización
            self._log_scraping_end(log_id, len(posts), success=True)
            
            print(f"✅ Scraper completado para {category_name}")
            print(f"📝 Posts obtenidos: {len(posts)}")
            
            # ✅ Las estadísticas se actualizan automáticamente via triggers
            
            scraper.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Error ejecutando scraper para {category_name}", error=str(e))
            print(f"❌ Error: {e}")
            
            # Registrar error
            log_id = locals().get('log_id')
            if log_id is not None:
                self._log_scraping_end(log_id, 0, success=False)
            
            return False
    
    def _build_scraper_config(self, subreddits, database):
        """Construye configuración para el scraper usando la config base."""
        return {
            'client_id': os.getenv('REDDIT_CLIENT_ID'),
            'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
            'user_agent': os.getenv('REDDIT_USER_AGENT'),
            'subreddits': subreddits,
            'search_params': {
                'time_filter': os.getenv('TIME_FILTER', 'week'),
                'min_upvotes': int(os.getenv('MIN_UPVOTES', '1000')),
                'limit': int(os.getenv('LIMIT', '10')),
                'post_type': os.getenv('POST_TYPE', 'hot'),
                'comment_limit': int(os.getenv('COMMENT_LIMIT', '2')),
                'min_comment_upvotes': int(os.getenv('MIN_COMMENT_UPVOTES', '69')),
                'max_comment_length': int(os.getenv('MAX_COMMENT_LENGTH', '500'))
            },
            'db_config': {
                **self.base_db_config,  # 🎯 Usar configuración base
                'database': database   # Solo cambiar la DB específica
            }
        }
    
    def _get_db_connection(self, database_name=None):
        """Helper para obtener conexión a DB específica."""
        db_name = database_name or 'reddit_admin'
        return psycopg2.connect(database=db_name, **self.base_db_config)
    
    def _log_scraping_start(self, category_name, database_name):
        """Registra inicio del scraping en la DB administrativa."""
        try:
            conn = self._get_db_connection('reddit_admin')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scraping_logs (category, database_name, status)
                VALUES (%s, %s, 'running')
                RETURNING id
            """, (category_name, database_name))
            
            log_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            return log_id
            
        except Exception as e:
            self.logger.warning("Error registrando inicio de scraping", error=str(e))
            return None
    
    def _log_scraping_end(self, log_id, posts_count, success=True):
        """Registra finalización del scraping."""
        if not log_id:
            return
            
        try:
            conn = self._get_db_connection('reddit_admin')
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE scraping_logs SET
                    ended_at = CURRENT_TIMESTAMP,
                    posts_scraped = %s,
                    status = %s
                WHERE id = %s
            """, (posts_count, 'completed' if success else 'failed', log_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.warning("Error registrando fin de scraping", error=str(e))

def main():
    print("🎯 Inicializando Reddit Scraper...")
    
    try:
        # ✅ Fallar inmediatamente si no puede conectar a DB
        app = RedditScrapperApp()
        
    except SystemExit:
        # ✅ Ya se mostró el error apropiado
        return
    except Exception as e:
        print(f"❌ Error crítico durante la inicialización: {e}")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        # Modo comando directo
        category = sys.argv[1].lower()
        if category in app.categories:
            print(f"🚀 Ejecutando scraper para categoría: {category}")
            success = app.run_scraper(category)
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Categoría '{category}' no encontrada")
            print(f"Categorías disponibles: {', '.join(app.categories.keys())}")
            sys.exit(1)
    else:
        # Modo interactivo
        try:
            while True:
                selection = app.show_menu()
                
                if selection is None:
                    print("👋 ¡Hasta luego!")
                    break
                
                # Confirmar antes de ejecutar
                config = app.categories[selection]
                subreddits_str = ', '.join(config['subreddits'])
                
                print(f"\n📋 Vas a scrapear:")
                print(f"   🏷️  Categoría: {selection.upper()}")
                print(f"   📝 {config['description']}")
                print(f"   🔗 Subreddits: {subreddits_str}")
                print(f"   📁 Base de datos: {config['database']}")
                
                confirm = input(f"\n¿Continuar con el scraping? (s/n): ").lower()
                if confirm in ['s', 'si', 'y', 'yes']:
                    success = app.run_scraper(selection)
                    
                    if success:
                        print(f"\n🎉 ¡Scraping completado exitosamente!")
                    else:
                        print(f"\n❌ El scraping falló")
                else:
                    print("❌ Scraping cancelado")
                
                # Preguntar si quiere hacer otro scraping
                another = input(f"\n¿Realizar otro scraping? (s/n): ").lower()
                if another not in ['s', 'si', 'y', 'yes']:
                    print("👋 ¡Hasta luego!")
                    break
                    
        except KeyboardInterrupt:
            print("\n⏸️  Programa interrumpido por el usuario")
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()