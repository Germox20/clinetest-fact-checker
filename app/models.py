"""Database models for the Fact Checker App."""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()


class Article(db.Model):
    """Model for storing articles to be fact-checked."""
    
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text)
    content = db.Column(db.Text)
    source_type = db.Column(db.String(50))  # 'original', 'news', 'official_doc', 'social_media'
    source_domain = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    facts = db.relationship('Fact', backref='article', lazy=True, cascade='all, delete-orphan')
    original_analyses = db.relationship('Analysis', foreign_keys='Analysis.original_article_id', 
                                       backref='original_article', lazy=True, cascade='all, delete-orphan')
    comparison_analyses = db.relationship('Analysis', foreign_keys='Analysis.comparison_article_id',
                                         backref='comparison_article', lazy=True)
    reports = db.relationship('Report', backref='article', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert article to dictionary."""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'content': self.content[:500] + '...' if self.content and len(self.content) > 500 else self.content,
            'source_type': self.source_type,
            'source_domain': self.source_domain,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Article {self.id}: {self.title[:50] if self.title else self.url[:50]}>'


class Fact(db.Model):
    """Model for storing extracted facts from articles with hierarchical structure."""
    
    __tablename__ = 'facts'
    
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    fact_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # 'what' or 'claim' (primary categories)
    confidence = db.Column(db.Float)  # Confidence in fact extraction (0-1)
    
    # Hierarchical relationships - only WHAT and CLAIM are primary
    parent_fact_id = db.Column(db.Integer, db.ForeignKey('facts.id'), nullable=True)
    
    # Related entities stored as JSON (WHO, WHERE, WHEN are now properties of WHAT/CLAIM)
    related_who = db.Column(db.Text)  # JSON array of WHO entities
    related_where = db.Column(db.Text)  # JSON array of WHERE locations  
    related_when = db.Column(db.Text)  # JSON array of WHEN timeframes
    
    # Importance score for search prioritization (0.0-1.0)
    importance_score = db.Column(db.Float, default=0.5)
    
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    child_facts = db.relationship('Fact', backref=db.backref('parent_fact', remote_side=[id]), 
                                 cascade='all, delete-orphan')
    
    def set_related_who(self, who_list):
        """Store related WHO entities as JSON."""
        self.related_who = json.dumps(who_list) if who_list else None
    
    def get_related_who(self):
        """Retrieve related WHO entities from JSON."""
        return json.loads(self.related_who) if self.related_who else []
    
    def set_related_where(self, where_list):
        """Store related WHERE locations as JSON."""
        self.related_where = json.dumps(where_list) if where_list else None
    
    def get_related_where(self):
        """Retrieve related WHERE locations from JSON."""
        return json.loads(self.related_where) if self.related_where else []
    
    def set_related_when(self, when_list):
        """Store related WHEN timeframes as JSON."""
        self.related_when = json.dumps(when_list) if when_list else None
    
    def get_related_when(self):
        """Retrieve related WHEN timeframes from JSON."""
        return json.loads(self.related_when) if self.related_when else []
    
    def to_dict(self):
        """Convert fact to dictionary."""
        return {
            'id': self.id,
            'article_id': self.article_id,
            'fact_text': self.fact_text,
            'category': self.category,
            'confidence': self.confidence,
            'importance_score': self.importance_score,
            'related_who': self.get_related_who(),
            'related_where': self.get_related_where(),
            'related_when': self.get_related_when(),
            'parent_fact_id': self.parent_fact_id,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None
        }
    
    def __repr__(self):
        return f'<Fact {self.id}: {self.category} - {self.fact_text[:50]}>'


class Analysis(db.Model):
    """Model for storing fact comparison analysis between articles."""
    
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    original_article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    comparison_article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    accuracy_score = db.Column(db.Float)  # 0-100 score
    matching_facts = db.Column(db.Text)  # JSON array of matching facts
    conflicting_facts = db.Column(db.Text)  # JSON array of conflicting facts
    analysis_details = db.Column(db.Text)  # JSON object with detailed analysis
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_matching_facts(self, facts_list):
        """Store matching facts as JSON."""
        self.matching_facts = json.dumps(facts_list)
    
    def get_matching_facts(self):
        """Retrieve matching facts from JSON."""
        return json.loads(self.matching_facts) if self.matching_facts else []
    
    def set_conflicting_facts(self, facts_list):
        """Store conflicting facts as JSON."""
        self.conflicting_facts = json.dumps(facts_list)
    
    def get_conflicting_facts(self):
        """Retrieve conflicting facts from JSON."""
        return json.loads(self.conflicting_facts) if self.conflicting_facts else []
    
    def set_analysis_details(self, details_dict):
        """Store analysis details as JSON."""
        self.analysis_details = json.dumps(details_dict)
    
    def get_analysis_details(self):
        """Retrieve analysis details from JSON."""
        return json.loads(self.analysis_details) if self.analysis_details else {}
    
    def to_dict(self):
        """Convert analysis to dictionary."""
        return {
            'id': self.id,
            'original_article_id': self.original_article_id,
            'comparison_article_id': self.comparison_article_id,
            'accuracy_score': self.accuracy_score,
            'matching_facts': self.get_matching_facts(),
            'conflicting_facts': self.get_conflicting_facts(),
            'analysis_details': self.get_analysis_details(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Analysis {self.id}: Article {self.original_article_id} vs {self.comparison_article_id}>'


class Report(db.Model):
    """Model for storing final fact-checking reports."""
    
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    original_article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    overall_score = db.Column(db.Float)  # Overall accuracy score (0-100)
    confidence_level = db.Column(db.String(20))  # 'high', 'medium', 'low'
    sources_checked = db.Column(db.Integer)  # Number of sources analyzed
    summary = db.Column(db.Text)  # Summary of findings
    recommendations = db.Column(db.Text)  # Recommendations for the user
    detailed_results = db.Column(db.Text)  # JSON with detailed results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Curator Agent merge tracking
    is_merged = db.Column(db.Boolean, default=False)  # Has this report been merged
    merge_count = db.Column(db.Integer, default=0)  # Number of times merged
    analysis_attempts = db.Column(db.Integer, default=1)  # Analysis retry attempts
    parent_report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships for merged reports
    merged_reports = db.relationship('Report', 
                                    backref=db.backref('parent_report', remote_side=[id]),
                                    foreign_keys=[parent_report_id])
    
    def set_detailed_results(self, results_dict):
        """Store detailed results as JSON."""
        self.detailed_results = json.dumps(results_dict)
    
    def get_detailed_results(self):
        """Retrieve detailed results from JSON."""
        return json.loads(self.detailed_results) if self.detailed_results else {}
    
    def to_dict(self):
        """Convert report to dictionary."""
        return {
            'id': self.id,
            'original_article_id': self.original_article_id,
            'overall_score': self.overall_score,
            'confidence_level': self.confidence_level,
            'sources_checked': self.sources_checked,
            'summary': self.summary,
            'recommendations': self.recommendations,
            'detailed_results': self.get_detailed_results(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Report {self.id}: Article {self.original_article_id} - Score: {self.overall_score}>'
