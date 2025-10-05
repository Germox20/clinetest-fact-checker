"""Search Agent - Searches for corroborating sources using News API and Google Search."""
from app.services.news_api_service import NewsAPIService
from app.services.google_search_service import GoogleSearchService
from app.models import Article, db
from config import Config


class SearchAgent:
    """Agent responsible for searching for related articles and sources."""
    
    def __init__(self):
        """Initialize the search agent with required services."""
        self.news_api = NewsAPIService()
        self.google_search = GoogleSearchService()
    
    def find_corroborating_sources(self, facts=None, query_data=None, max_sources=10):
        """
        Find sources that can corroborate or refute the facts.
        
        Args:
            facts (dict): Dictionary of facts by category (deprecated - use query_data)
            query_data (dict): Optimized queries from Curator Agent
            max_sources (int): Maximum number of sources to find
            
        Returns:
            list: List of source dictionaries with article data
        """
        print("\n" + "="*60)
        print("STEP 2: Searching for corroborating sources")
        print("="*60)
        
        sources = []
        
        # Use optimized queries if provided, otherwise fall back to facts
        if query_data:
            print("\n→ Using Curator-optimized queries...")
            news_sources = self._search_news_with_queries(query_data, max_results=max_sources // 2)
            google_sources = self._search_google_with_queries(query_data, max_results=max_sources // 2)
        else:
            print("\n→ Using legacy fact-based queries...")
            news_sources = self._search_news_sources(facts, max_results=max_sources // 2)
            google_sources = self._search_google_sources(facts, max_results=max_sources // 2)
        
        print(f"✓ Found {len(news_sources)} sources from News API")
        sources.extend(news_sources)
        
        print(f"✓ Found {len(google_sources)} sources from Google Search")
        sources.extend(google_sources)
        
        # Remove duplicates based on URL
        unique_sources = self._deduplicate_sources(sources)
        print(f"\n✓ Total unique sources found: {len(unique_sources)}")
        
        # Limit to max_sources
        final_sources = unique_sources[:max_sources]
        print(f"✓ Will analyze top {len(final_sources)} sources")
        
        return final_sources
    
    def fetch_and_store_source(self, url, source_type=None):
        """
        Fetch content from a source URL and store in database.
        
        Args:
            url (str): URL of the source
            source_type (str): Type of source (optional, will be classified if not provided)
            
        Returns:
            Article: Article object or None on error
        """
        # Fetch article content
        article_data = self.news_api.fetch_article_content(url)
        
        if not article_data.get('success'):
            print(f"Failed to fetch source from {url}")
            return None
        
        # Classify source type if not provided
        if not source_type:
            source_type = self.news_api.classify_source_type(url)
        
        # Check if article already exists
        existing_article = Article.query.filter_by(url=url).first()
        if existing_article:
            return existing_article
        
        # Create article record
        article = Article(
            url=url,
            title=article_data.get('title'),
            content=article_data.get('content'),
            source_type=source_type,
            source_domain=article_data.get('domain')
        )
        
        db.session.add(article)
        db.session.commit()
        
        return article
    
    def search_official_sources(self, facts):
        """
        Search specifically for official/authoritative sources.
        
        Args:
            facts (dict): Dictionary of facts by category
            
        Returns:
            list: List of official source dictionaries
        """
        official_sources = []
        
        # Use Google Search for official sources
        results = self.google_search.search_official_sources(facts)
        
        for result in results:
            official_sources.append({
                'url': result['url'],
                'title': result['title'],
                'snippet': result.get('snippet', ''),
                'source_type': 'official',
                'domain': result['domain']
            })
        
        return official_sources
    
    def _search_news_sources(self, facts, max_results=5):
        """
        Search for news sources using News API.
        
        Args:
            facts (dict): Dictionary of facts by category
            max_results (int): Maximum number of results
            
        Returns:
            list: List of source dictionaries
        """
        sources = []
        
        # Build search query from facts
        query = self.news_api.build_search_query(facts)
        print(f"  News API Query: '{query}'")
        
        if not query:
            print("  ✗ No query generated")
            return sources
        
        # Search for articles
        print(f"  → Calling News API with query...")
        articles = self.news_api.search_articles(query, max_results=max_results)
        print(f"  ✓ News API returned {len(articles)} articles")
        
        for article in articles:
            if article.get('url'):
                source_type = self.news_api.classify_source_type(article['url'], article.get('source'))
                sources.append({
                    'url': article['url'],
                    'title': article.get('title'),
                    'snippet': article.get('description', ''),
                    'source_type': source_type,
                    'source_name': article.get('source'),
                    'published_at': article.get('published_at')
                })
        
        return sources
    
    def _search_google_sources(self, facts, max_results=5):
        """
        Search for sources using Google Custom Search.
        
        Args:
            facts (dict): Dictionary of facts by category
            max_results (int): Maximum number of results
            
        Returns:
            list: List of source dictionaries
        """
        sources = []
        
        # Search for related content
        print(f"  → Calling Google Custom Search...")
        results = self.google_search.search_for_facts(facts, max_results_per_query=max_results)
        print(f"  ✓ Google Search returned {len(results)} results")
        
        for result in results[:max_results]:
            if result.get('url'):
                source_type = self.google_search.classify_result_type(result['url'])
                sources.append({
                    'url': result['url'],
                    'title': result.get('title'),
                    'snippet': result.get('snippet', ''),
                    'source_type': source_type,
                    'domain': result.get('domain')
                })
        
        return sources
    
    def _search_news_with_queries(self, query_data, max_results=5):
        """
        Search News API using Curator-optimized queries.
        
        Args:
            query_data (dict): Optimized queries from Curator
            max_results (int): Maximum number of results
            
        Returns:
            list: List of source dictionaries
        """
        sources = []
        
        # Get queries
        primary_query = query_data.get('primary_query', '')
        alt_queries = query_data.get('alternative_queries', [])
        
        print("\n→ Searching News API...")
        print(f"  Primary query: '{primary_query}'")
        
        # Search with primary query
        if primary_query:
            print(f"  → Calling News API with primary query...")
            articles = self.news_api.search_articles(primary_query, max_results=max_results)
            print(f"  ✓ News API returned {len(articles)} articles")
            
            for article in articles:
                if article.get('url'):
                    source_type = self.news_api.classify_source_type(article['url'], article.get('source'))
                    sources.append({
                        'url': article['url'],
                        'title': article.get('title'),
                        'snippet': article.get('description', ''),
                        'source_type': source_type,
                        'source_name': article.get('source'),
                        'published_at': article.get('published_at')
                    })
        
        # Try alternative queries if not enough results
        if len(sources) < max_results and alt_queries:
            remaining = max_results - len(sources)
            print(f"  → Trying alternative queries for {remaining} more sources...")
            
            for alt_query in alt_queries[:2]:  # Try up to 2 alternatives
                if len(sources) >= max_results:
                    break
                
                print(f"  Alt query: '{alt_query}'")
                articles = self.news_api.search_articles(alt_query, max_results=remaining)
                print(f"  ✓ Got {len(articles)} more articles")
                
                for article in articles:
                    if article.get('url'):
                        source_type = self.news_api.classify_source_type(article['url'], article.get('source'))
                        sources.append({
                            'url': article['url'],
                            'title': article.get('title'),
                            'snippet': article.get('description', ''),
                            'source_type': source_type,
                            'source_name': article.get('source'),
                            'published_at': article.get('published_at')
                        })
        
        return sources
    
    def _search_google_with_queries(self, query_data, max_results=5):
        """
        Search Google Custom Search using Curator-optimized queries.
        
        Args:
            query_data (dict): Optimized queries from Curator
            max_results (int): Maximum number of results
            
        Returns:
            list: List of source dictionaries
        """
        sources = []
        
        # Get queries
        primary_query = query_data.get('primary_query', '')
        keywords = query_data.get('keywords', [])
        
        print("\n→ Searching Google Custom Search...")
        print(f"  Primary query: '{primary_query}'")
        
        # Search with primary query
        if primary_query:
            print(f"  → Calling Google Custom Search...")
            results = self.google_search.search(primary_query, max_results=max_results)
            print(f"  ✓ Google Search returned {len(results)} results")
            
            for result in results:
                if result.get('url'):
                    source_type = self.google_search.classify_result_type(result['url'])
                    sources.append({
                        'url': result['url'],
                        'title': result.get('title'),
                        'snippet': result.get('snippet', ''),
                        'source_type': source_type,
                        'domain': result.get('domain')
                    })
        
        # Try keyword-based search if not enough results
        if len(sources) < max_results and keywords:
            remaining = max_results - len(sources)
            keyword_query = ' '.join(keywords[:5])
            print(f"  → Trying keyword query: '{keyword_query}'")
            
            results = self.google_search.search(keyword_query, max_results=remaining)
            print(f"  ✓ Got {len(results)} more results")
            
            for result in results:
                if result.get('url'):
                    source_type = self.google_search.classify_result_type(result['url'])
                    sources.append({
                        'url': result['url'],
                        'title': result.get('title'),
                        'snippet': result.get('snippet', ''),
                        'source_type': source_type,
                        'domain': result.get('domain')
                    })
        
        return sources
    
    def _deduplicate_sources(self, sources):
        """
        Remove duplicate sources based on URL.
        
        Args:
            sources (list): List of source dictionaries
            
        Returns:
            list: Deduplicated list of sources
        """
        seen_urls = set()
        unique_sources = []
        
        for source in sources:
            url = source.get('url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(source)
        
        return unique_sources
    
    def prioritize_sources(self, sources):
        """
        Prioritize sources based on reliability.
        
        Args:
            sources (list): List of source dictionaries
            
        Returns:
            list: Sorted list of sources (highest priority first)
        """
        # Define priority order
        priority_order = {
            'official': 1,
            'news_major': 2,
            'news_general': 3,
            'blog': 4,
            'social': 5
        }
        
        # Sort by priority
        sorted_sources = sorted(
            sources,
            key=lambda s: priority_order.get(s.get('source_type', 'news_general'), 6)
        )
        
        return sorted_sources
