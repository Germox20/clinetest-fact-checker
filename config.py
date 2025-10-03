"""Configuration settings for the Fact Checker App."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///fact_checker.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    NEWS_API_KEY = os.getenv('NEWS_API_KEY')
    GOOGLE_SEARCH_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
    GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
    
    # Application settings
    MAX_SOURCES_TO_CHECK = int(os.getenv('MAX_SOURCES_TO_CHECK', 10))
    ARTICLE_FETCH_TIMEOUT = int(os.getenv('ARTICLE_FETCH_TIMEOUT', 30))
    
    # Source reliability weights for scoring
    SOURCE_WEIGHTS = {
        'official': 1.0,      # .gov, .edu, official documents
        'news_major': 0.8,    # Established news organizations
        'news_general': 0.6,  # General news sites
        'blog': 0.4,          # Blogs and opinion sites
        'social': 0.3         # Social media posts
    }
    
    # Confidence level thresholds
    CONFIDENCE_THRESHOLDS = {
        'high': {'min_sources': 5, 'min_agreement': 0.8},
        'medium': {'min_sources': 3, 'min_agreement': 0.6},
        'low': {'min_sources': 0, 'min_agreement': 0.0}
    }
    
    # Trusted domains for source classification
    OFFICIAL_DOMAINS = ['.gov', '.edu', '.org']
    MAJOR_NEWS_DOMAINS = [
        'reuters.com', 'apnews.com', 'bbc.com', 'cnn.com',
        'nytimes.com', 'theguardian.com', 'washingtonpost.com',
        'wsj.com', 'bloomberg.com', 'npr.org'
    ]
    
    @staticmethod
    def validate_config():
        """Validate that required configuration values are set."""
        required_keys = [
            'GEMINI_API_KEY',
            'NEWS_API_KEY',
            'GOOGLE_SEARCH_API_KEY',
            'GOOGLE_SEARCH_ENGINE_ID'
        ]
        
        missing_keys = []
        for key in required_keys:
            if not os.getenv(key):
                missing_keys.append(key)
        
        if missing_keys:
            return False, missing_keys
        return True, []


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
