"""Fact Extractor Agent - Extracts facts from articles using Gemini with hierarchical structure."""
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
        
        # Extract facts using Gemini (hierarchical structure)
        facts_dict = self.gemini.extract_facts(
            article_data.get('content'),
            article_data.get('title')
        )
        
        # Save article to database
        db.session.add(article)
        db.session.commit()
        
        # Save facts to database (hierarchical)
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
        
        # Extract facts using Gemini (hierarchical structure)
        facts_dict = self.gemini.extract_facts(text, title)
        
        # Save article to database
        db.session.add(article)
        db.session.commit()
        
        # Save facts to database (hierarchical)
        self._save_facts_to_db(article.id, facts_dict)
        
        return article, facts_dict
    
    def extract_facts_from_existing_article(self, article):
        """
        Extract facts from an already saved article.
        
        Args:
            article (Article): Article object from database
            
        Returns:
            dict: Extracted facts in hierarchical structure
        """
        if not article.content:
            return {
                'what_facts': [],
                'claims': [],
                'error': 'No content available'
            }
        
        # Extract facts using Gemini (hierarchical structure)
        facts_dict = self.gemini.extract_facts(article.content, article.title)
        
        # Save facts to database (hierarchical)
        self._save_facts_to_db(article.id, facts_dict)
        
        return facts_dict
    
    def _save_facts_to_db(self, article_id, facts_dict):
        """
        Save extracted facts to database using hierarchical structure.
        
        Args:
            article_id (int): ID of the article
            facts_dict (dict): Dictionary with what_facts and claims
        """
        # Map importance to score
        importance_map = {
            'high': 0.9,
            'medium': 0.6,
            'low': 0.3
        }
        
        # Map confidence to score
        confidence_map = {
            'high': 0.9,
            'medium': 0.7,
            'low': 0.5
        }
        
        # Save WHAT facts
        if 'what_facts' in facts_dict:
            for what_fact in facts_dict['what_facts']:
                if isinstance(what_fact, dict) and what_fact.get('event'):
                    fact = Fact(
                        article_id=article_id,
                        fact_text=what_fact['event'],
                        category='what',
                        confidence=confidence_map.get(what_fact.get('confidence', 'medium'), 0.7),
                        importance_score=importance_map.get(what_fact.get('importance', 'medium'), 0.6)
                    )
                    
                    # Set related entities
                    fact.set_related_who(what_fact.get('related_who', []))
                    fact.set_related_where(what_fact.get('related_where', []))
                    fact.set_related_when(what_fact.get('related_when', []))
                    
                    db.session.add(fact)
        
        # Save CLAIMS
        if 'claims' in facts_dict:
            for claim_fact in facts_dict['claims']:
                if isinstance(claim_fact, dict) and claim_fact.get('claim'):
                    fact = Fact(
                        article_id=article_id,
                        fact_text=claim_fact['claim'],
                        category='claim',
                        confidence=confidence_map.get(claim_fact.get('confidence', 'medium'), 0.7),
                        importance_score=importance_map.get(claim_fact.get('importance', 'medium'), 0.6)
                    )
                    
                    # Set related entities
                    fact.set_related_who(claim_fact.get('related_who', []))
                    fact.set_related_where(claim_fact.get('related_where', []))
                    fact.set_related_when(claim_fact.get('related_when', []))
                    
                    db.session.add(fact)
        
        db.session.commit()
    
    def get_facts_for_article(self, article_id):
        """
        Retrieve facts for a specific article from database in hierarchical structure.
        
        Args:
            article_id (int): ID of the article
            
        Returns:
            dict: Facts organized hierarchically (what_facts and claims)
        """
        facts = Fact.query.filter_by(article_id=article_id).order_by(Fact.importance_score.desc()).all()
        
        facts_dict = {
            'what_facts': [],
            'claims': []
        }
        
        for fact in facts:
            fact_data = {
                'event' if fact.category == 'what' else 'claim': fact.fact_text,
                'related_who': fact.get_related_who(),
                'related_where': fact.get_related_where(),
                'related_when': fact.get_related_when(),
                'importance': 'high' if fact.importance_score >= 0.8 else 'medium' if fact.importance_score >= 0.5 else 'low',
                'confidence': 'high' if fact.confidence >= 0.8 else 'medium' if fact.confidence >= 0.6 else 'low'
            }
            
            if fact.category == 'what':
                facts_dict['what_facts'].append(fact_data)
            elif fact.category == 'claim':
                facts_dict['claims'].append(fact_data)
        
        return facts_dict
    
    def get_facts_for_display(self, article_id):
        """
        Retrieve facts formatted for display in templates (backward compatible).
        
        Args:
            article_id (int): ID of the article
            
        Returns:
            dict: Facts organized by category for display
        """
        facts = Fact.query.filter_by(article_id=article_id).order_by(Fact.importance_score.desc()).all()
        
        display_dict = {
            'who': [],
            'what': [],
            'when': [],
            'where': [],
            'claims': []
        }
        
        for fact in facts:
            # Add the main fact
            if fact.category == 'what':
                display_dict['what'].append(fact.fact_text)
                # Add related entities
                display_dict['who'].extend(fact.get_related_who())
                display_dict['where'].extend(fact.get_related_where())
                display_dict['when'].extend(fact.get_related_when())
            elif fact.category == 'claim':
                display_dict['claims'].append(fact.fact_text)
                # Add related entities
                display_dict['who'].extend(fact.get_related_who())
                display_dict['where'].extend(fact.get_related_where())
                display_dict['when'].extend(fact.get_related_when())
        
        # Remove duplicates while preserving order
        for key in display_dict:
            display_dict[key] = list(dict.fromkeys(display_dict[key]))
        
        return display_dict
