import os
import sys
from dotenv import load_dotenv
from scraper import RedditScraper

def load_config():
    load_dotenv()
    
    config = {
        'client_id': os.getenv('REDDIT_CLIENT_ID'),
        'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        'user_agent': os.getenv('REDDIT_USER_AGENT'),
        'subreddits': os.getenv('SUBREDDITS', 'AmItheAsshole,AITAH').split(','),
        'search_params': {
            'time_filter': os.getenv('TIME_FILTER'),
            'min_upvotes': int(os.getenv('MIN_UPVOTES', '200')),
            'limit': int(os.getenv('LIMIT', '10')),
            'post_type': os.getenv('POST_TYPE', 'hot'),
            'comment_limit': int(os.getenv('COMMENT_LIMIT', '2')),
            'min_comment_upvotes': int(os.getenv('MIN_COMMENT_UPVOTES', '100')),
            'max_comment_length': int(os.getenv('MAX_COMMENT_LENGTH', '500'))
        },
        'db_config' : {
            'host': os.getenv('POSTGRES_HOST', 'postgres'),
            'database': os.getenv('POSTGRES_DB', 'reddit_scraper'),
            'user': os.getenv('POSTGRES_USER', 'scraper'),
            'password': os.getenv('POSTGRES_PASSWORD', 'scraper_pass'),
            'port': int(os.getenv('POSTGRES_PORT', '5432'))
        }
    }
    return config


def main():
    scraper = None
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
        if scraper:
            try:
                scraper.close()
                print("🔄 Scraper cerrado correctamente")
            except:
                pass


if __name__ == '__main__':
    main()