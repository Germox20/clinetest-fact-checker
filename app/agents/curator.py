"""Curator Agent - Orchestrates analysis workflow and optimizes search queries."""
from app.services.gemini_service import GeminiService
from app.models import Article, Report, Analysis, db
from datetime import datetime
import hashlib


class CuratorAgent:
    """
    Curator Agent coordinates the fact-checking workflow:
    - Optimizes search queries for better results
    - Prevents duplicate analyses
    - Merges reports when re-analyzing same article
    - Manages iterative analysis attempts
    """
    
    def __init__(self):
        """Initialize the curator with required services."""
        self.gemini = GeminiService()
        self.max_attempts = 3
        self.min_sources_threshold = 3
    
    def optimize_search_queries(self, facts, attempt=1):
        """
        Generate optimized search queries from hierarchical facts.
        
        Args:
            facts (dict): Hierarchical facts with what_facts and claims
            attempt (int): Current attempt number (for progressive refinement)
            
        Returns:
            dict: {
                'primary_query': str,
                'alternative_queries': list,
                'keywords': list
            }
        """
        print(f"\n→ Curator: Optimizing search queries (attempt {attempt})...")
        
        # Use Gemini to create effective queries
        query_data = self.gemini.optimize_search_query(facts, attempt)
        
        print(f"  ✓ Primary query: '{query_data.get('primary_query', 'N/A')}'")
        print(f"  ✓ Alternative queries: {len(query_data.get('alternative_queries', []))}")
        
        return query_data
    
    def check_existing_analysis(self, article_url=None, article_text=None):
        """
        Check if this article has been analyzed before.
        
        Args:
            article_url (str): URL of article
            article_text (str): Text content (for user-provided text)
            
        Returns:
            Report or None: Existing report if found
        """
        print("\n→ Curator: Checking for existing analysis...")
        
        if article_url and article_url != 'user_provided_text':
            # Search by URL
            article = Article.query.filter_by(url=article_url, source_type='original').first()
        elif article_text:
            # Search by content hash for user-provided text
            content_hash = self._hash_content(article_text)
            # Try to find by similar content (simplified - just check if hash matches)
            articles = Article.query.filter_by(source_type='original').all()
            article = None
            for art in articles:
                if art.content and self._hash_content(art.content) == content_hash:
                    article = art
                    break
        else:
            return None
        
        if article:
            # Get most recent report for this article
            report = Report.query.filter_by(original_article_id=article.id)\
                                 .order_by(Report.last_updated.desc()).first()
            if report:
                print(f"  ✓ Found existing report (ID: {report.id})")
                print(f"    - Current sources: {report.sources_checked}")
                print(f"    - Merge count: {report.merge_count}")
                print(f"    - Analysis attempts: {report.analysis_attempts}")
                return report
        
        print("  ℹ No existing analysis found")
        return None
    
    def filter_duplicate_sources(self, sources, original_article_url, analyzed_article_ids):
        """
        Remove duplicate and already-analyzed sources.
        
        Args:
            sources (list): List of source dictionaries
            original_article_url (str): URL of original article
            analyzed_article_ids (list): IDs of already-analyzed articles
            
        Returns:
            list: Filtered sources
        """
        print("\n→ Curator: Filtering duplicate sources...")
        initial_count = len(sources)
        
        filtered = []
        seen_urls = set()
        
        for source in sources:
            url = source.get('url')
            
            # Skip if no URL
            if not url:
                continue
            
            # Skip if duplicate in current batch
            if url in seen_urls:
                continue
            
            # Skip if it's the original article
            if url == original_article_url:
                print(f"  ✗ Skipped original article: {url}")
                continue
            
            # Skip if already analyzed
            existing_article = Article.query.filter_by(url=url).first()
            if existing_article and existing_article.id in analyzed_article_ids:
                print(f"  ✗ Skipped already analyzed: {url}")
                continue
            
            seen_urls.add(url)
            filtered.append(source)
        
        print(f"  ✓ Filtered: {initial_count} → {len(filtered)} sources")
        return filtered
    
    def merge_reports(self, existing_report, new_analyses):
        """
        Merge new analyses into existing report.
        
        Args:
            existing_report (Report): Existing report to update
            new_analyses (list): New analysis results to merge
            
        Returns:
            tuple: (updated_report, new_sources_count)
        """
        if not new_analyses:
            print("\n→ Curator: No new analyses to merge")
            return existing_report, 0
        
        print(f"\n→ Curator: Merging {len(new_analyses)} new analyses...")
        
        # Get existing analyses
        existing_analyses_objs = Analysis.query.filter_by(
            original_article_id=existing_report.original_article_id
        ).all()
        
        # Convert to list of dicts
        existing_analyses = [
            {
                'comparison_article_id': a.comparison_article_id,
                'accuracy_score': a.accuracy_score,
                'matching_facts': a.get_matching_facts(),
                'conflicting_facts': a.get_conflicting_facts(),
                'analysis_details': a.get_analysis_details()
            }
            for a in existing_analyses_objs
        ]
        
        # Combine all analyses
        all_analyses = existing_analyses + new_analyses
        
        # Recalculate report using all analyses
        from app.agents.scorer import ScorerAgent
        scorer = ScorerAgent()
        
        # Update report
        overall_score = scorer._calculate_overall_score(all_analyses)
        confidence_level = scorer._determine_confidence_level(all_analyses)
        summary = scorer._generate_summary(all_analyses, overall_score)
        recommendations = scorer._generate_recommendations(overall_score, confidence_level, all_analyses)
        
        # Update detailed results
        detailed_results = {
            'individual_analyses': all_analyses,
            'score_breakdown': scorer._get_score_breakdown(all_analyses),
            'source_distribution': scorer._get_source_distribution(all_analyses),
            'fact_verification_details': scorer._get_fact_verification_details(all_analyses)
        }
        
        # Update report fields
        existing_report.overall_score = overall_score
        existing_report.confidence_level = confidence_level
        existing_report.sources_checked = len(all_analyses)
        existing_report.summary = summary
        existing_report.recommendations = recommendations
        existing_report.set_detailed_results(detailed_results)
        existing_report.is_merged = True
        existing_report.merge_count += 1
        existing_report.last_updated = datetime.utcnow()
        
        db.session.commit()
        
        new_sources_count = len(new_analyses)
        print(f"  ✓ Report updated with {new_sources_count} new sources")
        print(f"  ✓ Total sources: {existing_report.sources_checked}")
        print(f"  ✓ New score: {overall_score:.1f}")
        
        return existing_report, new_sources_count
    
    def should_retry_analysis(self, report, attempt):
        """
        Determine if analysis should be retried.
        
        Args:
            report (Report): Current report
            attempt (int): Current attempt number
            
        Returns:
            bool: True if should retry
        """
        # Don't retry if max attempts reached
        if attempt >= self.max_attempts:
            print(f"\n→ Curator: Max attempts ({self.max_attempts}) reached")
            return False
        
        # Retry if not enough sources
        if report.sources_checked < self.min_sources_threshold:
            print(f"\n→ Curator: Only {report.sources_checked} sources found (need {self.min_sources_threshold})")
            print(f"  → Will retry with refined query (attempt {attempt + 1})")
            return True
        
        print(f"\n→ Curator: Sufficient sources found ({report.sources_checked})")
        return False
    
    def get_analyzed_article_ids(self, original_article_id):
        """
        Get IDs of articles that have already been analyzed for comparison.
        
        Args:
            original_article_id (int): ID of original article
            
        Returns:
            list: List of article IDs
        """
        analyses = Analysis.query.filter_by(original_article_id=original_article_id).all()
        analyzed_ids = [a.comparison_article_id for a in analyses]
        analyzed_ids.append(original_article_id)  # Include original
        return analyzed_ids
    
    def _hash_content(self, content):
        """
        Create a hash of content for comparison.
        
        Args:
            content (str): Content to hash
            
        Returns:
            str: Hash string
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()
