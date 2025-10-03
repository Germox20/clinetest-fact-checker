"""News API service for searching news articles."""
from newsapi import NewsApiClient
from config import Config
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class NewsAPIService:
    """Service for interacting with News API."""
    
    def __init__(self):
        """Initialize the News API service with API key."""
        if not Config.NEWS_API_KEY:
            raise ValueError("NEWS_API_KEY not found in configuration")
        
        self.client = NewsApiClient(api_key=Config.NEWS_API_KEY)
        self.timeout = Config.ARTICLE_FETCH_TIMEOUT
    
    def search_articles(self, query, max_results=10):
        """
        Search for news articles related to a query.
        
        Args:
            query (str): Search query (keywords from facts)
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of article dictionaries with url, title, source, etc.
        """
        try:
            # Search for articles
            response = self.client.get_everything(
                q=query,
                language='en',
                sort_by='relevancy',
                page_size=min(max_results, 100)
            )
            
            articles = []
            if response['status'] == 'ok':
                for article in response['articles'][:max_results]:
                    articles.append({
                        'url': article.get('url'),
                        'title': article.get('title'),
                        'source': article.get('source', {}).get('name'),
                        'published_at': article.get('publishedAt'),
                        'description': article.get('description'),
                        'content': article.get('content')
                    })
            
            return articles
        except Exception as e:
            print(f"Error searching News API: {e}")
            return []
    
    def fetch_article_content(self, url):
        """
        Fetch full article content from URL.
        
        Args:
            url (str): URL of the article
            
        Returns:
            dict: Dictionary with title, content, and metadata
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else soup.title.string if soup.title else 'No title'
            
            # Extract main content (try common article tags)
            content_text = ''
            
            # Try article tag first
            article = soup.find('article')
            if article:
                paragraphs = article.find_all('p')
                content_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # If no article tag, try finding main content div
            if not content_text:
                main_content = soup.find('main') or soup.find('div', class_=['article-content', 'post-content', 'entry-content'])
                if main_content:
                    paragraphs = main_content.find_all('p')
                    content_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # Last resort: get all paragraphs
            if not content_text:
                paragraphs = soup.find_all('p')
                content_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:20]])  # Limit to first 20 paragraphs
            
            # Extract domain
            domain = urlparse(url).netloc
            
            return {
                'url': url,
                'title': title_text,
                'content': content_text,
                'domain': domain,
                'success': True
            }
        except requests.RequestException as e:
            print(f"Error fetching article from {url}: {e}")
            return {
                'url': url,
                'title': None,
                'content': None,
                'domain': None,
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            print(f"Error parsing article from {url}: {e}")
            return {
                'url': url,
                'title': None,
                'content': None,
                'domain': None,
                'success': False,
                'error': str(e)
            }
    
    def classify_source_type(self, url, source_name=None):
        """
        Classify the type of news source.
        
        Args:
            url (str): URL of the article
            source_name (str): Name of the source
            
        Returns:
            str: Source type ('news_major', 'news_general', 'blog', etc.)
        """
        domain = urlparse(url).netloc.lower()
        
        # Check if it's a major news organization
        for major_domain in Config.MAJOR_NEWS_DOMAINS:
            if major_domain in domain:
                return 'news_major'
        
        # Check for official domains
        for official_domain in Config.OFFICIAL_DOMAINS:
            if domain.endswith(official_domain):
                return 'official'
        
        # Check for social media
        social_domains = ['twitter.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'reddit.com']
        for social_domain in social_domains:
            if social_domain in domain:
                return 'social'
        
        # Check for blog indicators
        blog_indicators = ['blog', 'wordpress', 'medium.com', 'substack.com']
        for indicator in blog_indicators:
            if indicator in domain:
                return 'blog'
        
        # Default to general news
        return 'news_general'
    
    def build_search_query(self, facts):
        """
        Build search query from extracted facts.
        
        Args:
            facts (dict): Dictionary of facts by category
            
        Returns:
            str: Search query string
        """
        query_parts = []
        
        # Add key entities (who)
        if facts.get('who'):
            # Take first 2 most important entities
            entities = facts['who'][:2]
            for entity in entities:
                # Extract just the entity name (before colon if present)
                entity_name = entity.split(':')[0].strip()
                query_parts.append(entity_name)
        
        # Add main events (what)
        if facts.get('what'):
            # Take first main event
            events = facts['what'][:1]
            for event in events:
                # Extract key words (first few words)
                event_words = ' '.join(event.split()[:8])
                query_parts.append(event_words)
        
        # Add location if specific
        if facts.get('where'):
            locations = facts['where'][:1]
            query_parts.extend(locations)
        
        # Combine into query
        query = ' '.join(query_parts)
        
        # Limit query length
        if len(query) > 200:
            query = query[:200]
        
        return query
