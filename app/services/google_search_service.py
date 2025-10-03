"""Google Custom Search API service for web search."""
from googleapiclient.discovery import build
from config import Config
from urllib.parse import urlparse


class GoogleSearchService:
    """Service for interacting with Google Custom Search API."""
    
    def __init__(self):
        """Initialize the Google Search service with API key."""
        if not Config.GOOGLE_SEARCH_API_KEY or not Config.GOOGLE_SEARCH_ENGINE_ID:
            raise ValueError("Google Search API credentials not found in configuration")
        
        self.api_key = Config.GOOGLE_SEARCH_API_KEY
        self.engine_id = Config.GOOGLE_SEARCH_ENGINE_ID
        self.service = build("customsearch", "v1", developerKey=self.api_key)
    
    def search(self, query, max_results=10):
        """
        Search for web pages using Google Custom Search.
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of search result dictionaries
        """
        try:
            results = []
            
            # Google Custom Search returns 10 results per request
            # We'll limit to first page for free tier
            response = self.service.cse().list(
                q=query,
                cx=self.engine_id,
                num=min(max_results, 10)
            ).execute()
            
            if 'items' in response:
                for item in response['items']:
                    results.append({
                        'url': item.get('link'),
                        'title': item.get('title'),
                        'snippet': item.get('snippet'),
                        'domain': urlparse(item.get('link')).netloc if item.get('link') else None
                    })
            
            return results
        except Exception as e:
            print(f"Error searching with Google Custom Search: {e}")
            return []
    
    def search_for_facts(self, facts, max_results_per_query=5):
        """
        Search for information about specific facts.
        
        Args:
            facts (dict): Dictionary of facts by category
            max_results_per_query (int): Max results per search query
            
        Returns:
            list: Combined list of search results
        """
        all_results = []
        
        # Create search queries from key facts
        queries = self._build_search_queries(facts)
        
        for query in queries[:3]:  # Limit to 3 queries to stay within API limits
            results = self.search(query, max_results=max_results_per_query)
            all_results.extend(results)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                unique_results.append(result)
        
        return unique_results
    
    def search_official_sources(self, facts):
        """
        Search specifically for official/authoritative sources.
        
        Args:
            facts (dict): Dictionary of facts by category
            
        Returns:
            list: Search results filtered for official sources
        """
        queries = self._build_search_queries(facts)
        official_results = []
        
        for query in queries[:2]:  # Limit queries
            # Add site filters for official sources
            official_query = f"{query} site:.gov OR site:.edu OR site:.org"
            results = self.search(official_query, max_results=5)
            official_results.extend(results)
        
        return official_results
    
    def classify_result_type(self, url):
        """
        Classify the type of search result based on URL.
        
        Args:
            url (str): URL to classify
            
        Returns:
            str: Result type classification
        """
        domain = urlparse(url).netloc.lower()
        
        # Check for official domains
        for official_domain in Config.OFFICIAL_DOMAINS:
            if domain.endswith(official_domain):
                return 'official'
        
        # Check for major news
        for news_domain in Config.MAJOR_NEWS_DOMAINS:
            if news_domain in domain:
                return 'news_major'
        
        # Check for social media
        social_domains = ['twitter.com', 'facebook.com', 'instagram.com', 'reddit.com']
        for social_domain in social_domains:
            if social_domain in domain:
                return 'social'
        
        # Check for blog indicators
        blog_indicators = ['blog', 'wordpress', 'medium.com', 'substack.com']
        for indicator in blog_indicators:
            if indicator in domain:
                return 'blog'
        
        # Check for wiki
        if 'wikipedia.org' in domain:
            return 'wiki'
        
        # Default to general
        return 'news_general'
    
    def _build_search_queries(self, facts):
        """
        Build search queries from facts.
        
        Args:
            facts (dict): Dictionary of facts by category
            
        Returns:
            list: List of search query strings
        """
        queries = []
        
        # Query 1: Main entities and events
        query_parts = []
        if facts.get('who'):
            # Take top 2 entities
            for entity in facts['who'][:2]:
                entity_name = entity.split(':')[0].strip()
                query_parts.append(entity_name)
        
        if facts.get('what'):
            # Take main event
            event = facts['what'][0] if facts['what'] else ''
            event_words = ' '.join(event.split()[:10])
            query_parts.append(event_words)
        
        if query_parts:
            queries.append(' '.join(query_parts))
        
        # Query 2: Specific claims
        if facts.get('claims'):
            for claim in facts['claims'][:2]:
                # Extract key words from claim
                claim_words = ' '.join(claim.split()[:15])
                queries.append(claim_words)
        
        # Query 3: Location-specific if available
        if facts.get('where') and facts.get('what'):
            location = facts['where'][0]
            event = ' '.join(facts['what'][0].split()[:8])
            queries.append(f"{event} {location}")
        
        return queries
