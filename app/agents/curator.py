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
    
    def review_and_reconcile_analyses(self, analyses):
        """
        Review analyses to ensure consistency in fact classifications.
        Resolves contradictions where facts are marked as both matching AND conflicting.
        Applies numerical and ambiguous expression rules.
        
        Args:
            analyses (list): List of analysis dictionaries
            
        Returns:
            list: Reconciled analyses with consistent classifications
        """
        print("\n" + "="*60)
        print("CURATOR REVIEW: Reconciling fact classifications")
        print("="*60)
        
        reconciled_analyses = []
        
        for idx, analysis in enumerate(analyses, 1):
            print(f"\n→ Reviewing analysis {idx}/{len(analyses)}...")
            
            matching_facts = analysis.get('matching_facts', [])
            conflicting_facts = analysis.get('conflicting_facts', [])
            
            # Check for dual classifications
            dual_classified = self._find_dual_classifications(matching_facts, conflicting_facts)
            
            if dual_classified:
                print(f"  ⚠ Found {len(dual_classified)} dual-classified facts")
                
                # Resolve each dual classification
                for original_fact, comparison_fact in dual_classified:
                    decision = self._resolve_fact_classification(original_fact, comparison_fact)
                    
                    if decision == 'match':
                        # Keep in matching, remove from conflicting
                        conflicting_facts = [c for c in conflicting_facts 
                                           if not self._facts_match(c, original_fact, comparison_fact)]
                        print(f"  ✓ Reclassified as MATCH: {original_fact[:50]}...")
                    else:
                        # Keep in conflicting, remove from matching
                        matching_facts = [m for m in matching_facts 
                                        if not self._facts_match(m, original_fact, comparison_fact)]
                        print(f"  ✓ Reclassified as CONFLICT: {original_fact[:50]}...")
            else:
                print("  ✓ No dual classifications found")
            
            # Update analysis with reconciled facts
            analysis['matching_facts'] = matching_facts
            analysis['conflicting_facts'] = conflicting_facts
            reconciled_analyses.append(analysis)
        
        print(f"\n✓ Review complete: {len(reconciled_analyses)} analyses reconciled")
        return reconciled_analyses
    
    def _find_dual_classifications(self, matching_facts, conflicting_facts):
        """Find facts that appear in both matching and conflicting lists."""
        dual_classified = []
        
        for match in matching_facts:
            match_text = self._extract_fact_text(match)
            
            for conflict in conflicting_facts:
                conflict_original = conflict.get('original', '') if isinstance(conflict, dict) else str(conflict)
                conflict_comparison = conflict.get('comparison', '') if isinstance(conflict, dict) else ''
                
                # Check if they're about the same fact
                if self._is_same_fact(match_text, conflict_original) or \
                   self._is_same_fact(match_text, conflict_comparison):
                    dual_classified.append((match_text, conflict_comparison or conflict_original))
                    break
        
        return dual_classified
    
    def _extract_fact_text(self, fact):
        """Extract text from fact (handles both string and dict)."""
        if isinstance(fact, dict):
            return fact.get('original_fact') or fact.get('fact', '')
        return str(fact)
    
    def _is_same_fact(self, fact1, fact2):
        """Check if two facts are about the same thing (simple similarity)."""
        import re
        # Remove numbers and special chars for comparison
        clean1 = re.sub(r'[\d\W]+', ' ', fact1.lower()).strip()
        clean2 = re.sub(r'[\d\W]+', ' ', fact2.lower()).strip()
        
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 or not words2:
            return False
        
        # Calculate word overlap
        overlap = len(words1 & words2) / max(len(words1), len(words2))
        return overlap > 0.5  # 50% word overlap
    
    def _resolve_fact_classification(self, fact1, fact2):
        """
        Resolve whether facts should be classified as matching or conflicting.
        Applies number comparison and ambiguous expression rules.
        
        Returns: 'match' or 'conflict'
        """
        import re
        
        # Extract numbers from both facts
        numbers1 = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', fact1)
        numbers2 = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', fact2)
        
        # Convert to floats
        nums1 = [float(n.replace(',', '')) for n in numbers1]
        nums2 = [float(n.replace(',', '')) for n in numbers2]
        
        # If both have numbers, apply 30% rule
        if nums1 and nums2:
            # Compare corresponding numbers
            for n1, n2 in zip(nums1, nums2):
                if self._numbers_within_tolerance(n1, n2):
                    print(f"    → Numbers {n1} vs {n2}: within 30% tolerance")
                    return 'match'
                else:
                    print(f"    → Numbers {n1} vs {n2}: exceed 30% tolerance")
                    return 'conflict'
        
        # Check for ambiguous expressions
        ambiguous_match = self._check_ambiguous_expressions(fact1, fact2)
        if ambiguous_match is not None:
            return 'match' if ambiguous_match else 'conflict'
        
        # Default: keep as conflict if we can't determine
        return 'conflict'
    
    def _numbers_within_tolerance(self, num1, num2):
        """Check if two numbers are within 30% of the larger number."""
        if num1 == 0 and num2 == 0:
            return True
        
        larger = max(abs(num1), abs(num2))
        difference = abs(num1 - num2)
        percentage_diff = (difference / larger) * 100
        
        return percentage_diff < 30
    
    def _check_ambiguous_expressions(self, fact1, fact2):
        """
        Check if ambiguous expressions match with numbers.
        Returns: True (match), False (no match), None (not applicable)
        """
        import re
        
        # Ambiguous expression mappings
        EXPRESSIONS = {
            'few': (0, 20),
            'some': (5, 50),
            'any': (0, 20),
            'various': (20, 50),
            'many': (20, 200),
            'several': (50, 200),
            'lot': (50, 200),
            'lots': (50, 200),
            'huge': (200, float('inf')),
            'massive': (200, float('inf')),
            'big': (200, float('inf'))
        }
        
        # Find expression in one fact and number in another
        fact1_lower = fact1.lower()
        fact2_lower = fact2.lower()
        
        # Extract numbers
        numbers1 = re.findall(r'\d+(?:,\d{3})*', fact1)
        numbers2 = re.findall(r'\d+(?:,\d{3})*', fact2)
        
        # Check if one has expression and other has number
        for expr, (min_val, max_val) in EXPRESSIONS.items():
            if expr in fact1_lower and numbers2:
                num = float(numbers2[0].replace(',', ''))
                match = min_val <= num <= max_val
                print(f"    → Expression '{expr}' vs number {num}: {'match' if match else 'no match'}")
                return match
            elif expr in fact2_lower and numbers1:
                num = float(numbers1[0].replace(',', ''))
                match = min_val <= num <= max_val
                print(f"    → Expression '{expr}' vs number {num}: {'match' if match else 'no match'}")
                return match
        
        return None  # No ambiguous expressions found
    
    def _facts_match(self, fact_item, original_text, comparison_text):
        """Check if a fact item matches the given texts."""
        if isinstance(fact_item, dict):
            item_orig = fact_item.get('original', '') or fact_item.get('original_fact', '')
            item_comp = fact_item.get('comparison', '') or fact_item.get('comparison_fact', '')
            
            return (original_text in item_orig or item_orig in original_text) and \
                   (comparison_text in item_comp or item_comp in comparison_text)
        
        item_text = str(fact_item)
        return original_text in item_text or comparison_text in item_text
    
    def rescore_analysis(self, matching_facts, conflicting_facts):
        """
        Recalculate accuracy score for an analysis after fact reclassification.
        
        Args:
            matching_facts (list): List of matching facts
            conflicting_facts (list): List of conflicting facts
            
        Returns:
            float: New accuracy score
        """
        print(f"\n→ Curator: Rescoring analysis...")
        
        # Count facts by strength/severity
        strong_matches = 0
        moderate_matches = 0
        
        for fact in matching_facts:
            if isinstance(fact, dict):
                strength = fact.get('match_strength', 'moderate')
                if strength == 'strong':
                    strong_matches += 1
                else:
                    moderate_matches += 1
            else:
                moderate_matches += 1
        
        high_conflicts = 0
        medium_conflicts = 0
        low_conflicts = 0
        
        for fact in conflicting_facts:
            if isinstance(fact, dict):
                severity = fact.get('conflict_severity', 'medium')
                if severity == 'high':
                    high_conflicts += 1
                elif severity == 'medium':
                    medium_conflicts += 1
                else:
                    low_conflicts += 1
            else:
                medium_conflicts += 1
        
        # Calculate weighted score
        positive_points = (strong_matches * 10) + (moderate_matches * 7)
        negative_points = (high_conflicts * 15) + (medium_conflicts * 10) + (low_conflicts * 5)
        
        total_facts = len(matching_facts) + len(conflicting_facts)
        if total_facts == 0:
            return 50.0
        
        # Score formula: percentage of positive points out of maximum possible
        max_possible = total_facts * 10
        raw_score = max(0, positive_points - negative_points)
        score = min(100.0, (raw_score / max_possible) * 100)
        
        print(f"  ✓ New score: {score:.1f}")
        print(f"    - Matching facts: {len(matching_facts)} (strong: {strong_matches}, moderate: {moderate_matches})")
        print(f"    - Conflicting facts: {len(conflicting_facts)} (high: {high_conflicts}, medium: {medium_conflicts}, low: {low_conflicts})")
        
        return score
