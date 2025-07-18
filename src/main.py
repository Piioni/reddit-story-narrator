from Scrapper import RedditScraper  
import os
from dotenv import load_dotenv

def main():
    # Configuración
    config = {
        'client_id': os.getenv("REDDIT_CLIENT_ID"),
        'client_secret': os.getenv("REDDIT_CLIENT_SECRET"),
        'password' : os.getenv("REDDIT_PASSWORD"),
        'user_agent': os.getenv("REDDIT_USER_AGENT"),
        'username' : os.getenv("REDDIT_USERNAME"),
        'subreddits': ['AmItheAsshole', 'AITAH'],
        'search_params': {
            'time_filter': 'week',
            'min_upvotes': 1000,
            'limit': 10
        }
    }

    scraper = RedditScraper(**config)
    try:
        posts = scraper.fetch_posts()
        print(posts)
            
    finally:
        scraper.close()

if __name__ == '__main__':
    print(os.getenv("REDDIT_CLIENT_ID"))
    print(os.getenv("REDDIT_CLIENT_SECRET"))
    print(os.getenv("REDDIT_USER_AGENT"))
    main()