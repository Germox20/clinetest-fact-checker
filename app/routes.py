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
        
        # Get all facts from original article
        from app.agents.fact_extractor import FactExtractorAgent
        fact_extractor = FactExtractorAgent()
        original_facts = fact_extractor.get_facts_for_article(report.original_article_id)
        
        # Get analyses with comparison articles and their facts
        analyses = Analysis.query.filter_by(original_article_id=report.original_article_id).all()
        
        analyses_data = []
        for analysis in analyses:
            comparison_article = Article.query.get(analysis.comparison_article_id)
            comparison_facts = fact_extractor.get_facts_for_article(analysis.comparison_article_id)
            
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
    Analyze an article for fact-checking.
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
        fact_extractor = get_fact_extractor()
        search_agent = get_search_agent()
        scorer = get_scorer()
        
        # Step 1: Extract facts from original article
        if url:
            original_article, original_facts = fact_extractor.process_article(url)
        else:
            original_article, original_facts = fact_extractor.extract_facts_from_text(text, title)
        
        if not original_article:
            return jsonify({'error': 'Failed to process article'}), 500
        
        # Step 2: Search for corroborating sources
        sources = search_agent.find_corroborating_sources(
            original_facts, 
            max_sources=Config.MAX_SOURCES_TO_CHECK
        )
        
        # Step 3: Analyze each source
        analyses = []
        for source in sources[:Config.MAX_SOURCES_TO_CHECK]:
            # Fetch and store source
            source_article = search_agent.fetch_and_store_source(
                source['url'],
                source.get('source_type')
            )
            
            if not source_article or not source_article.content:
                continue
            
            # Extract facts from source
            source_facts = fact_extractor.extract_facts_from_existing_article(source_article)
            
            # Compare and score
            analysis = scorer.compare_and_score(
                original_facts,
                source_article,
                source_facts
            )
            
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
        
        # Step 4: Generate final report
        report = scorer.generate_final_report(original_article.id, analyses)
        
        return jsonify({
            'success': True,
            'article_id': original_article.id,
            'report_id': report.id,
            'report': report.to_dict()
        })
    
    except Exception as e:
        current_app.logger.error(f"Error analyzing article: {e}")
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


@bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'database': 'connected'
    })
