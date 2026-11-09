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
        
        self.base_db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.environ['POSTGRES_PASSWORD'],
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
        
        self.categories = self._load_categories_from_db()
        
    def _load_categories_from_db(self):
        try:
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
                    'subreddits': list(row[2]),
                    'description': row[3]
                }
            
            conn.close()
            
            if not categories:
                print(" No se encontraron categorías en la base de datos")
                sys.exit(1)
            
            self.logger.info(f"Categorías cargadas desde DB", count=len(categories))
            return categories
            
        except psycopg2.OperationalError as e:
            self.logger.error("Error cargando categorías desde la base de datos", error=str(e)) 
            sys.exit(1)
            
        except psycopg2.Error as e:
            self.logger.error("Error cargando categorías desde la base de datos", error=str(e))
            sys.exit(1)
            
        except Exception as e:
            self.logger.error("Error cargando categorías desde la base de datos", error=str(e))
            print(f"   {str(e)}")
            sys.exit(1)
    
    def show_menu(self):
        print("\n" + "="*70)
        print("REDDIT SCRAPER - SELECCIONAR CATEGORÍA")
        print("="*70)
        
        # Mostrar categorías disponibles
        category_list = list(self.categories.keys())
        
        for i, (category, config) in enumerate(self.categories.items(), 1):
            subreddits_str = ', '.join(config['subreddits'])
            print(f"{i}. {category.upper()}")
            print(f"📝 {config['description']}")
            print(f"🏷️  Subreddits: {subreddits_str}")
            print(f"📁 Base de datos: {config['database']}")
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
                    print("Opción inválida")
            except ValueError:
                print("Por favor ingresa un número válido")

    def _show_statistics(self):
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
                print("No hay datos disponibles")
        
        input("\nPresiona Enter para continuar...")
    
    def _get_category_stats(self, database_name):
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
        if category_name not in self.categories:
            print(f"Categoría '{category_name}' no encontrada")
            return False
            
        config = self.categories[category_name]
        
        self.logger.info(f"Ejecutando scraper para {category_name}", config=config)
        
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
            
            self.logger.info(f"Scraping completado para {category_name}", posts_count=len(posts))
            scraper.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Error ejecutando scraper para {category_name}", error=str(e))
            
            # Registrar error
            log_id = locals().get('log_id')
            if log_id is not None:
                self._log_scraping_end(log_id, 0, success=False)
            
            return False
    
    def _build_scraper_config(self, subreddits, database):
        return {
            'client_id': os.getenv('REDDIT_CLIENT_ID'),
            'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
            'user_agent': os.getenv('REDDIT_USER_AGENT'),
            'subreddits': subreddits,
            'search_params': {
                'time_filter': os.getenv('TIME_FILTER'),
                'min_upvotes': int(os.getenv('MIN_UPVOTES', 100)),
                'limit': int(os.getenv('LIMIT', 5)),
                'post_type': os.getenv('POST_TYPE'),
                'comment_limit': int(os.getenv('COMMENT_LIMIT', 2)),
                'min_comment_upvotes': int(os.getenv('MIN_COMMENT_UPVOTES', 250)),
                'max_comment_length': int(os.getenv('MAX_COMMENT_LENGTH', 500)),
            },
            'db_config': {
                **self.base_db_config, 
                'database': database   
            }
        }
    
    def _get_db_connection(self, database_name=None):
        db_name = database_name or 'reddit_admin'
        return psycopg2.connect(database=db_name, **self.base_db_config)
    
    def _log_scraping_start(self, category_name, database_name):
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
        app = RedditScrapperApp()
        
    except SystemExit:
        return
    except Exception as e:
        print(f"Error crítico durante la inicialización: {e}")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        # Modo comando directo
        category = sys.argv[1].lower()
        if category in app.categories:
            print(f"🚀 Ejecutando scraper para categoría: {category}")
            success = app.run_scraper(category)
            sys.exit(0 if success else 1)
        else:
            print(f"Categoría '{category}' no encontrada")
            print(f"Categorías disponibles: {', '.join(app.categories.keys())}")
            sys.exit(1)
    else:
        # Modo interactivo
        try:
            while True:
                selection = app.show_menu()
                
                if selection is None:
                    print("¡Hasta luego!")
                    break
                
                # Confirmar antes de ejecutar
                config = app.categories[selection]
                subreddits_str = ', '.join(config['subreddits'])
                
                print(f"\n📋 Vas a scrapear:")
                print(f"🔗 Subreddits: {subreddits_str}")
                
                confirm = input(f"\n¿Continuar con el scraping? (s/n): ").lower()
                if confirm in ['s', 'si', 'y', 'yes']:
                    success = app.run_scraper(selection)
                    
                    if success:
                        print(f"\n¡Scraping completado exitosamente!")
                    else:
                        print(f"\nEl scraping falló")
                else:
                    print("Scraping cancelado")

                # Preguntar si quiere hacer otro scraping
                another = input(f"\n¿Realizar otro scraping? (y/n): ").lower()
                if another not in ['y', 'yes']:
                    print("👋 ¡Hasta luego!")
                    break
                    
        except KeyboardInterrupt:
            print("\nPrograma interrumpido por el usuario")
        except Exception as e:
            print(f"\nError inesperado: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()