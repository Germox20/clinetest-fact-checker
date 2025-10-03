"""Flask application initialization."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config
import os


def create_app(config_name='default'):
    """
    Create and configure the Flask application.
    
    Args:
        config_name (str): Configuration name (default, development, production)
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    config_obj = config.get(config_name, config['default'])
    app.config.from_object(config_obj)
    
    # Validate API keys
    is_valid, missing_keys = config_obj.validate_config()
    if not is_valid:
        print(f"Warning: Missing API keys: {', '.join(missing_keys)}")
        print("Please configure your .env file with the required API keys.")
    
    # Initialize database
    from app.models import db
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Register blueprints/routes
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app
