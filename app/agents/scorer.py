"""Scorer Agent - Compares facts and calculates accuracy scores."""
from app.services.gemini_service import GeminiService
from app.models import Analysis, Report, db
from config import Config


class ScorerAgent:
    """Agent responsible for comparing facts and calculating accuracy scores."""
    
    def __init__(self):
        """Initialize the scorer with required services."""
        self.gemini = GeminiService()
    
    def compare_and_score(self, original_facts, comparison_article, comparison_facts):
        """
        Compare facts from original and comparison articles and create analysis.
        Uses context-aware matching and relevance filtering.
        
        Args:
            original_facts (dict): Facts from original article (hierarchical)
            comparison_article: Article object from comparison source
            comparison_facts (dict): Facts from comparison article (hierarchical)
            
        Returns:
            dict or None: Analysis dict with comparison results, or None if not relevant
        """
        # Use Gemini to compare facts (context-aware)
        comparison_result = self.gemini.compare_facts(original_facts, comparison_facts)
        
        # Get relevance score from comparison
        relevance_score = comparison_result.get('relevance_score', 0.5)
        
        # Filter out low-relevance sources (different topics)
        if relevance_score < 0.4:
            print(f"Skipping low-relevance source (relevance: {relevance_score}): {comparison_article.url}")
            return None
        
        # Calculate accuracy score for this comparison
        score = self._calculate_comparison_score(
            comparison_result,
            comparison_article.source_type,
            relevance_score
        )
        
        # Create analysis record (will be saved later)
        analysis = {
            'comparison_article_id': comparison_article.id,
            'accuracy_score': score,
            'matching_facts': comparison_result.get('matching', []),
            'conflicting_facts': comparison_result.get('conflicting', []),
            'analysis_details': {
                'unique_to_original': comparison_result.get('unique_to_original', []),
                'unique_to_comparison': comparison_result.get('unique_to_comparison', []),
                'analysis_notes': comparison_result.get('analysis_notes', ''),
                'relevance_score': relevance_score,
                'source_type': comparison_article.source_type,
                'source_domain': comparison_article.source_domain
            }
        }
        
        return analysis
    
    def generate_final_report(self, original_article_id, analyses):
        """
        Generate final fact-checking report based on all analyses.
        
        Args:
            original_article_id (int): ID of original article
            analyses (list): List of analysis dictionaries
            
        Returns:
            Report: Final report with overall score and recommendations
        """
        if not analyses:
            return self._create_no_sources_report(original_article_id)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(analyses)
        
        # Determine confidence level
        confidence_level = self._determine_confidence_level(analyses)
        
        # Generate summary
        summary = self._generate_summary(analyses, overall_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(overall_score, confidence_level, analyses)
        
        # Create detailed results
        detailed_results = {
            'individual_analyses': analyses,
            'score_breakdown': self._get_score_breakdown(analyses),
            'source_distribution': self._get_source_distribution(analyses),
            'fact_verification_details': self._get_fact_verification_details(analyses)
        }
        
        # Create report
        report = Report(
            original_article_id=original_article_id,
            overall_score=overall_score,
            confidence_level=confidence_level,
            sources_checked=len(analyses),
            summary=summary,
            recommendations=recommendations
        )
        report.set_detailed_results(detailed_results)
        
        db.session.add(report)
        db.session.commit()
        
        return report
    
    def _calculate_comparison_score(self, comparison_result, source_type, relevance_score=0.5):
        """
        Calculate score for a single comparison.
        
        Args:
            comparison_result (dict): Result from Gemini comparison
            source_type (str): Type of source being compared
            relevance_score (float): Relevance score from comparison (0.0-1.0)
            
        Returns:
            float: Score from 0-100
        """
        matching_facts = comparison_result.get('matching', [])
        conflicting_facts = comparison_result.get('conflicting', [])
        
        # Count facts
        num_matching = len(matching_facts)
        num_conflicting = len(conflicting_facts)
        total_facts = num_matching + num_conflicting
        
        if total_facts == 0:
            return 50.0  # Neutral score if no overlap
        
        # Calculate base agreement percentage
        agreement_percentage = (num_matching / total_facts) * 100
        
        # Apply confidence weighting for matching facts
        confidence_weight = 0
        for fact in matching_facts:
            if isinstance(fact, dict):
                conf = fact.get('confidence', 'medium')
                if conf == 'high':
                    confidence_weight += 1.0
                elif conf == 'medium':
                    confidence_weight += 0.7
                else:
                    confidence_weight += 0.5
        
        if num_matching > 0:
            avg_confidence = confidence_weight / num_matching
            agreement_percentage *= avg_confidence
        
        return min(100.0, agreement_percentage)
    
    def _calculate_overall_score(self, analyses):
        """
        Calculate overall accuracy score from all analyses.
        
        Args:
            analyses (list): List of analysis dictionaries
            
        Returns:
            float: Overall score from 0-100
        """
        if not analyses:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for analysis in analyses:
            score = analysis.get('accuracy_score', 0)
            source_type = analysis.get('analysis_details', {}).get('source_type', 'news_general')
            
            # Get weight for source type
            weight = Config.SOURCE_WEIGHTS.get(source_type, 0.5)
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        overall_score = weighted_sum / total_weight
        return round(overall_score, 2)
    
    def _determine_confidence_level(self, analyses):
        """
        Determine confidence level based on sources and agreement.
        
        Args:
            analyses (list): List of analysis dictionaries
            
        Returns:
            str: 'high', 'medium', or 'low'
        """
        num_sources = len(analyses)
        
        # Calculate average agreement
        if analyses:
            avg_score = sum(a.get('accuracy_score', 0) for a in analyses) / len(analyses)
            agreement_ratio = avg_score / 100.0
        else:
            agreement_ratio = 0.0
        
        # Check thresholds
        for level in ['high', 'medium', 'low']:
            thresholds = Config.CONFIDENCE_THRESHOLDS[level]
            if (num_sources >= thresholds['min_sources'] and 
                agreement_ratio >= thresholds['min_agreement']):
                return level
        
        return 'low'
    
    def _generate_summary(self, analyses, overall_score):
        """Generate summary text for the report."""
        num_sources = len(analyses)
        
        if overall_score >= 80:
            verdict = "highly accurate"
        elif overall_score >= 60:
            verdict = "moderately accurate"
        elif overall_score >= 40:
            verdict = "questionable accuracy"
        else:
            verdict = "low accuracy"
        
        summary = f"Based on analysis of {num_sources} source(s), "
        summary += f"the article appears to be {verdict} "
        summary += f"with an overall score of {overall_score:.1f}/100. "
        
        # Add details about matching/conflicting facts
        total_matching = sum(len(a.get('matching_facts', [])) for a in analyses)
        total_conflicting = sum(len(a.get('conflicting_facts', [])) for a in analyses)
        
        summary += f"Found {total_matching} corroborating fact(s) and {total_conflicting} conflicting claim(s) across sources."
        
        return summary
    
    def _generate_recommendations(self, score, confidence, analyses):
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if score >= 80 and confidence == 'high':
            recommendations.append("The information appears reliable and well-supported by multiple sources.")
        elif score >= 60:
            recommendations.append("The information has moderate support. Consider seeking additional sources for verification.")
        else:
            recommendations.append("Exercise caution: The information has limited support or conflicting reports.")
        
        # Check for official sources
        has_official = any(
            a.get('analysis_details', {}).get('source_type') == 'official' 
            for a in analyses
        )
        
        if not has_official:
            recommendations.append("No official sources were found. Consider checking government or institutional sources.")
        
        # Check source diversity
        source_types = set(
            a.get('analysis_details', {}).get('source_type') 
            for a in analyses
        )
        
        if len(source_types) < 2:
            recommendations.append("Limited source diversity. Cross-reference with different types of sources.")
        
        return ' '.join(recommendations)
    
    def _get_score_breakdown(self, analyses):
        """Get breakdown of scores by source type."""
        breakdown = {}
        
        for analysis in analyses:
            source_type = analysis.get('analysis_details', {}).get('source_type', 'unknown')
            score = analysis.get('accuracy_score', 0)
            
            if source_type not in breakdown:
                breakdown[source_type] = []
            breakdown[source_type].append(score)
        
        # Calculate averages
        for source_type in breakdown:
            scores = breakdown[source_type]
            breakdown[source_type] = {
                'count': len(scores),
                'average_score': sum(scores) / len(scores) if scores else 0,
                'scores': scores
            }
        
        return breakdown
    
    def _get_source_distribution(self, analyses):
        """Get distribution of source types."""
        distribution = {}
        
        for analysis in analyses:
            source_type = analysis.get('analysis_details', {}).get('source_type', 'unknown')
            distribution[source_type] = distribution.get(source_type, 0) + 1
        
        return distribution
    
    def _get_fact_verification_details(self, analyses):
        """Get detailed fact verification statistics."""
        total_matching = sum(len(a.get('matching_facts', [])) for a in analyses)
        total_conflicting = sum(len(a.get('conflicting_facts', [])) for a in analyses)
        
        return {
            'total_matching_facts': total_matching,
            'total_conflicting_facts': total_conflicting,
            'verification_ratio': total_matching / (total_matching + total_conflicting) 
                                  if (total_matching + total_conflicting) > 0 else 0
        }
    
    def _create_no_sources_report(self, original_article_id):
        """Create report when no sources were found."""
        report = Report(
            original_article_id=original_article_id,
            overall_score=0.0,
            confidence_level='low',
            sources_checked=0,
            summary="Unable to verify: No corroborating sources were found.",
            recommendations="The article could not be fact-checked due to lack of available sources. Exercise extreme caution with this information."
        )
        report.set_detailed_results({
            'individual_analyses': [],
            'score_breakdown': {},
            'source_distribution': {},
            'fact_verification_details': {
                'total_matching_facts': 0,
                'total_conflicting_facts': 0,
                'verification_ratio': 0
            }
        })
        
        db.session.add(report)
        db.session.commit()
        
        return report
