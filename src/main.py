import os
import sys
from dotenv import load_dotenv
from scraper import RedditScraper

def load_config():
    load_dotenv()
    
    # Validar variables requeridas
    required_vars = [
        'REDDIT_CLIENT_ID',
        'REDDIT_CLIENT_SECRET', 
        'REDDIT_USER_AGENT'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Variables de entorno faltantes: {', '.join(missing_vars)}")
    
    config = {
        'client_id': os.getenv('REDDIT_CLIENT_ID'),
        'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        'user_agent': os.getenv('REDDIT_USER_AGENT'),
        'subreddits': os.getenv('SUBREDDITS', 'AmItheAsshole,AITAH').split(','),
        'search_params': {
            'time_filter': os.getenv('TIME_FILTER', 'week'),
            'min_upvotes': int(os.getenv('MIN_UPVOTES', '1000')),
            'limit': int(os.getenv('LIMIT', '10')),
            'comment_limit': int(os.getenv('COMMENT_LIMIT', '20')),
            'min_comment_upvotes': int(os.getenv('MIN_COMMENT_UPVOTES', '5')),
            'max_comment_length': int(os.getenv('MAX_COMMENT_LENGTH', '1000'))
        }
    }
    
    # Configuración de DB (opcional)
    if os.getenv('POSTGRES_HOST'):
        config['db_config'] = {
            'host': os.getenv('POSTGRES_HOST'),
            'database': os.getenv('POSTGRES_DB', 'reddit_scraper'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
    
    return config

def main():
    try:
        config = load_config()
        
        print("🚀 Iniciando Reddit Scraper...")
        print(f"📂 Subreddits: {', '.join(config['subreddits'])}")
        print(f"⚙️  Filtro: {config['search_params']['time_filter']}")
        print(f"📊 Límite de posts: {config['search_params']['limit']}")
        
        scraper = RedditScraper(**config)
        
        # Ejecutar scraping
        posts = scraper.fetch_posts()
        
        print(f"\n✅ Scraping completado!")
        print(f"📝 Posts obtenidos: {len(posts)}")
        
        # Mostrar resumen
        if posts:
            print("\n📋 Resumen de posts:")
            for post in posts[:5]:  # Mostrar los primeros 5
                print(f"  • {post['title'][:60]}{'...' if len(post['title']) > 60 else ''}")
                print(f"    👍 {post['upvotes']} upvotes | 💬 {post.get('comments_count', 0)} comments")
            
            if len(posts) > 5:
                print(f"  ... y {len(posts) - 5} posts más")
        
    except KeyboardInterrupt:
        print("\n⏸️  Scraping interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error durante el scraping: {str(e)}")
        sys.exit(1)
    finally:
        try:
            scraper.close()
        except:
            pass

if __name__ == '__main__':
    main()