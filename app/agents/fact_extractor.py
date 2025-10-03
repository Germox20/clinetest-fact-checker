"""Fact Extractor Agent - Extracts facts from articles using Gemini."""
from app.services.gemini_service import GeminiService
from app.services.news_api_service import NewsAPIService
from app.models import Article, Fact, db


class FactExtractorAgent:
    """Agent responsible for extracting facts from articles."""
    
    def __init__(self):
        """Initialize the fact extractor with required services."""
        self.gemini = GeminiService()
        self.news_api = NewsAPIService()
    
    def process_article(self, url):
        """
        Process an article URL and extract facts.
        
        Args:
            url (str): URL of the article to process
            
        Returns:
            tuple: (article_object, facts_dict) or (None, None) on error
        """
        # Fetch article content
        article_data = self.news_api.fetch_article_content(url)
        
        if not article_data.get('success') or not article_data.get('content'):
            print(f"Failed to fetch article content from {url}")
            return None, None
        
        # Create article record
        article = Article(
            url=url,
            title=article_data.get('title'),
            content=article_data.get('content'),
            source_type='original',
            source_domain=article_data.get('domain')
        )
        
        # Extract facts using Gemini
        facts_dict = self.gemini.extract_facts(
            article_data.get('content'),
            article_data.get('title')
        )
        
        # Save article to database
        db.session.add(article)
        db.session.commit()
        
        # Save facts to database
        self._save_facts_to_db(article.id, facts_dict)
        
        return article, facts_dict
    
    def extract_facts_from_text(self, text, title=None):
        """
        Extract facts from provided text (without URL).
        
        Args:
            text (str): Article text to analyze
            title (str): Optional article title
            
        Returns:
            tuple: (article_object, facts_dict)
        """
        # Create article record
        article = Article(
            url='user_provided_text',
            title=title or 'User Provided Text',
            content=text,
            source_type='original',
            source_domain='user_input'
        )
        
        # Extract facts using Gemini
        facts_dict = self.gemini.extract_facts(text, title)
        
        # Save article to database
        db.session.add(article)
        db.session.commit()
        
        # Save facts to database
        self._save_facts_to_db(article.id, facts_dict)
        
        return article, facts_dict
    
    def extract_facts_from_existing_article(self, article):
        """
        Extract facts from an already saved article.
        
        Args:
            article (Article): Article object from database
            
        Returns:
            dict: Extracted facts
        """
        if not article.content:
            return {
                'who': [],
                'what': [],
                'when': [],
                'where': [],
                'claims': [],
                'error': 'No content available'
            }
        
        # Extract facts using Gemini
        facts_dict = self.gemini.extract_facts(article.content, article.title)
        
        # Save facts to database
        self._save_facts_to_db(article.id, facts_dict)
        
        return facts_dict
    
    def _save_facts_to_db(self, article_id, facts_dict):
        """
        Save extracted facts to the database.
        
        Args:
            article_id (int): ID of the article
            facts_dict (dict): Dictionary of facts by category
        """
        # Define category mapping
        categories = {
            'who': 'who',
            'what': 'what',
            'when': 'when',
            'where': 'where',
            'claims': 'claim'
        }
        
        for category_key, facts_list in facts_dict.items():
            if category_key in categories and isinstance(facts_list, list):
                for fact_text in facts_list:
                    if fact_text:  # Skip empty strings
                        fact = Fact(
                            article_id=article_id,
                            fact_text=fact_text,
                            category=categories[category_key],
                            confidence=0.8  # Default confidence
                        )
                        db.session.add(fact)
        
        db.session.commit()
    
    def get_facts_for_article(self, article_id):
        """
        Retrieve facts for a specific article from database.
        
        Args:
            article_id (int): ID of the article
            
        Returns:
            dict: Facts organized by category
        """
        facts = Fact.query.filter_by(article_id=article_id).all()
        
        facts_dict = {
            'who': [],
            'what': [],
            'when': [],
            'where': [],
            'claims': []
        }
        
        category_mapping = {
            'who': 'who',
            'what': 'what',
            'when': 'when',
            'where': 'where',
            'claim': 'claims'
        }
        
        for fact in facts:
            category_key = category_mapping.get(fact.category)
            if category_key:
                facts_dict[category_key].append(fact.fact_text)
        
        return facts_dict
