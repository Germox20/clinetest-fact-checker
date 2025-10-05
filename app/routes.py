"""Application routes and API endpoints."""
from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import Article, Report, Analysis, db
from app.agents.fact_extractor import FactExtractorAgent
from app.agents.search_agent import SearchAgent
from app.agents.scorer import ScorerAgent
from config import Config

bp = Blueprint('main', __name__)

# Initialize agents (will be created per request to avoid state issues)
def get_fact_extractor():
    return FactExtractorAgent()

def get_search_agent():
    return SearchAgent()

def get_scorer():
    return ScorerAgent()

def get_curator():
    from app.agents.curator import CuratorAgent
    return CuratorAgent()


@bp.route('/')
def index():
    """Home page."""
    return render_template('index.html')


@bp.route('/analyze', methods=['GET'])
def analyze_page():
    """Analysis page."""
    return render_template('analyze.html')


@bp.route('/history', methods=['GET'])
def history_page():
    """History page showing past analyses."""
    return render_template('history.html')


@bp.route('/report/<int:report_id>', methods=['GET'])
def report_detail_page(report_id):
    """Detailed report page."""
    try:
        report = Report.query.get(report_id)
        
        if not report:
            return render_template('error.html', 
                                 error_message='Report not found',
                                 error_code=404), 404
        
        # Get article
        article = Article.query.get(report.original_article_id)
        
        # Get all facts from original article (for display)
        from app.agents.fact_extractor import FactExtractorAgent
        fact_extractor = FactExtractorAgent()
        original_facts = fact_extractor.get_facts_for_display(report.original_article_id)
        
        # Get analyses with comparison articles and their facts
        analyses = Analysis.query.filter_by(original_article_id=report.original_article_id).all()
        
        analyses_data = []
        for analysis in analyses:
            comparison_article = Article.query.get(analysis.comparison_article_id)
            comparison_facts = fact_extractor.get_facts_for_display(analysis.comparison_article_id)
            
            analyses_data.append({
                'analysis': analysis,
                'comparison_article': comparison_article,
                'comparison_facts': comparison_facts,
                'matching_facts': analysis.get_matching_facts(),
                'conflicting_facts': analysis.get_conflicting_facts(),
                'analysis_details': analysis.get_analysis_details()
            })
        
        return render_template('report_detail.html',
                             report=report,
                             article=article,
                             original_facts=original_facts,
                             analyses=analyses_data,
                             detailed_results=report.get_detailed_results())
    
    except Exception as e:
        current_app.logger.error(f"Error loading report detail page: {e}")
        return render_template('error.html',
                             error_message=str(e),
                             error_code=500), 500


@bp.route('/api/analyze', methods=['POST'])
def analyze_article():
    """
    Analyze an article for fact-checking with Curator Agent orchestration.
    Features:
    - Query optimization for better source discovery
    - Duplicate detection and filtering
    - Report merging for re-analyzed articles
    - Iterative analysis with up to 3 attempts
    
    Expects JSON with either 'url' or 'text' field.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        url = data.get('url')
        text = data.get('text')
        title = data.get('title')
        
        if not url and not text:
            return jsonify({'error': 'Either url or text must be provided'}), 400
        
        # Initialize agents
        curator = get_curator()
        fact_extractor = get_fact_extractor()
        search_agent = get_search_agent()
        scorer = get_scorer()
        
        # Curator: Check for existing analysis
        existing_report = curator.check_existing_analysis(url, text)
        
        # Step 1: Extract facts from original article
        current_app.logger.info("="*60)
        current_app.logger.info("STEP 1: Extracting facts from original article")
        current_app.logger.info("="*60)
        
        if url:
            current_app.logger.info(f"Processing URL: {url}")
            original_article, original_facts = fact_extractor.process_article(url)
        else:
            current_app.logger.info(f"Processing text (length: {len(text)} chars)")
            original_article, original_facts = fact_extractor.extract_facts_from_text(text, title)
        
        if not original_article:
            current_app.logger.error("Failed to process article")
            return jsonify({'error': 'Failed to process article'}), 500
        
        current_app.logger.info(f"✓ Article processed: {original_article.title}")
        current_app.logger.info(f"✓ Extracted {len(original_facts.get('what_facts', []))} WHAT facts")
        current_app.logger.info(f"✓ Extracted {len(original_facts.get('claims', []))} CLAIMS")
        
        # Get already-analyzed article IDs for filtering
        analyzed_ids = curator.get_analyzed_article_ids(original_article.id) if existing_report else [original_article.id]
        
        # Iterative analysis loop (max 3 attempts)
        report = existing_report
        new_sources_added = 0
        
        for attempt in range(1, 4):
            current_app.logger.info(f"\n{'='*60}")
            current_app.logger.info(f"ANALYSIS ATTEMPT {attempt}/3")
            current_app.logger.info(f"{'='*60}")
            
            # Curator: Optimize search queries
            query_data = curator.optimize_search_queries(original_facts, attempt)
            
            # Step 2: Search for corroborating sources with optimized queries
            try:
                sources = search_agent.find_corroborating_sources(
                    query_data=query_data,
                    max_sources=Config.MAX_SOURCES_TO_CHECK
                )
            except Exception as e:
                current_app.logger.error(f"Error in find_corroborating_sources: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Curator: Filter duplicates and already-analyzed sources
            sources = curator.filter_duplicate_sources(sources, original_article.url, analyzed_ids)
            
            if not sources:
                current_app.logger.info("✗ No new sources to analyze")
                if report:
                    break  # Exit if we have a report and no new sources
                else:
                    continue  # Try next attempt if no report yet
            
            # Step 3: Analyze each source
            current_app.logger.info("\n" + "="*60)
            current_app.logger.info("STEP 3: Analyzing sources")
            current_app.logger.info("="*60)
            
            analyses = []
            for idx, source in enumerate(sources[:Config.MAX_SOURCES_TO_CHECK], 1):
                current_app.logger.info(f"\n→ Analyzing source {idx}/{len(sources[:Config.MAX_SOURCES_TO_CHECK])}")
                current_app.logger.info(f"  URL: {source['url']}")
                current_app.logger.info(f"  Title: {source.get('title', 'N/A')}")
                
                # Fetch and store source
                current_app.logger.info("  → Fetching article content...")
                source_article = search_agent.fetch_and_store_source(
                    source['url'],
                    source.get('source_type')
                )
                
                if not source_article or not source_article.content:
                    current_app.logger.warning("  ✗ Failed to fetch or no content")
                    continue
                
                current_app.logger.info(f"  ✓ Content fetched ({len(source_article.content)} chars)")
                
                # Extract facts from source (hierarchical)
                current_app.logger.info("  → Extracting facts...")
                source_facts = fact_extractor.extract_facts_from_existing_article(source_article)
                current_app.logger.info(f"  ✓ Extracted {len(source_facts.get('what_facts', []))} WHAT facts, {len(source_facts.get('claims', []))} claims")
                
                # Compare and score (returns None if not relevant)
                current_app.logger.info("  → Comparing facts...")
                analysis = scorer.compare_and_score(
                    original_facts,
                    source_article,
                    source_facts
                )
                
                # Skip if source is not relevant
                if analysis is None:
                    current_app.logger.warning("  ✗ Source filtered as not relevant (relevance < 0.4)")
                    continue
                
                current_app.logger.info(f"  ✓ Analysis complete - Score: {analysis['accuracy_score']:.1f}")
                
                # Save analysis to database
                analysis_record = Analysis(
                    original_article_id=original_article.id,
                    comparison_article_id=analysis['comparison_article_id'],
                    accuracy_score=analysis['accuracy_score']
                )
                analysis_record.set_matching_facts(analysis['matching_facts'])
                analysis_record.set_conflicting_facts(analysis['conflicting_facts'])
                analysis_record.set_analysis_details(analysis['analysis_details'])
                
                db.session.add(analysis_record)
                db.session.commit()
                
                analyses.append(analysis)
                analyzed_ids.append(source_article.id)
            
            current_app.logger.info(f"\n✓ Sources analyzed this attempt: {len(analyses)}")
            
            # Step 4: Generate or merge report
            if existing_report and analyses:
                # Curator: Merge new analyses into existing report
                report, sources_added = curator.merge_reports(existing_report, analyses)
                new_sources_added += sources_added
            elif analyses:
                # Generate new report
                report = scorer.generate_final_report(original_article.id, analyses)
                report.analysis_attempts = attempt
                db.session.commit()
                new_sources_added = len(analyses)
            
            # Check if we should retry
            if report and not curator.should_retry_analysis(report, attempt):
                break
        
        # Prepare response
        was_merged = existing_report is not None
        
        return jsonify({
            'success': True,
            'article_id': original_article.id,
            'report_id': report.id if report else None,
            'report': report.to_dict() if report else None,
            'was_merged': was_merged,
            'new_sources_added': new_sources_added,
            'total_attempts': report.analysis_attempts if report else 1
        })
    
    except Exception as e:
        current_app.logger.error(f"Error analyzing article: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/analysis/<int:report_id>', methods=['GET'])
def get_analysis(report_id):
    """Get analysis results by report ID."""
    try:
        report = Report.query.get(report_id)
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # Get article details
        article = Article.query.get(report.original_article_id)
        
        # Get all analyses for this article
        analyses = Analysis.query.filter_by(original_article_id=report.original_article_id).all()
        
        return jsonify({
            'success': True,
            'report': report.to_dict(),
            'article': article.to_dict() if article else None,
            'analyses': [a.to_dict() for a in analyses]
        })
    
    except Exception as e:
        current_app.logger.error(f"Error retrieving analysis: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/history', methods=['GET'])
def get_history():
    """Get list of previous analyses."""
    try:
        # Get recent reports with their articles
        reports = Report.query.order_by(Report.created_at.desc()).limit(50).all()
        
        history = []
        for report in reports:
            article = Article.query.get(report.original_article_id)
            history.append({
                'report_id': report.id,
                'article_title': article.title if article else 'Unknown',
                'article_url': article.url if article else '',
                'overall_score': report.overall_score,
                'confidence_level': report.confidence_level,
                'sources_checked': report.sources_checked,
                'created_at': report.created_at.isoformat() if report.created_at else None
            })
        
        return jsonify({
            'success': True,
            'history': history
        })
    
    except Exception as e:
        current_app.logger.error(f"Error retrieving history: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/report/<int:report_id>', methods=['GET'])
def get_report(report_id):
    """Get detailed report."""
    try:
        report = Report.query.get(report_id)
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # Get article
        article = Article.query.get(report.original_article_id)
        
        # Get analyses with comparison articles
        analyses = Analysis.query.filter_by(original_article_id=report.original_article_id).all()
        
        analyses_data = []
        for analysis in analyses:
            comparison_article = Article.query.get(analysis.comparison_article_id)
            analyses_data.append({
                'analysis': analysis.to_dict(),
                'comparison_article': comparison_article.to_dict() if comparison_article else None
            })
        
        return jsonify({
            'success': True,
            'report': report.to_dict(),
            'article': article.to_dict() if article else None,
            'analyses': analyses_data
        })
    
    except Exception as e:
        current_app.logger.error(f"Error retrieving report: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/report/<int:report_id>/delete', methods=['DELETE'])
def delete_report(report_id):
    """Delete a report and its associated analyses."""
    try:
        report = Report.query.get(report_id)
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # Get the article ID before deleting
        article_id = report.original_article_id
        
        # Delete all analyses for this report
        Analysis.query.filter_by(original_article_id=article_id).delete()
        
        # Delete the report
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Report deleted successfully'
        })
    
    except Exception as e:
        current_app.logger.error(f"Error deleting report: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'database': 'connected'
    })
