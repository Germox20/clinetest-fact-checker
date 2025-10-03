# Fact Checker App

A web application that assists users in fact-checking information from news articles and social media posts using AI-powered analysis.

## Overview

The Fact Checker App uses Google Gemini AI to extract facts from articles, searches for corroborating sources using News API and Google Custom Search, and assigns accuracy scores based on the consistency and reliability of the information found.

## Features

- **Automated Fact Extraction**: Uses Google Gemini to identify key facts, claims, and entities from articles
- **Multi-Source Verification**: Searches News API and Google Custom Search for corroborating sources
- **Source Reliability Scoring**: Weighs sources based on credibility (official documents, established news, social media)
- **Accuracy Scoring**: Assigns scores (0-100) based on fact consistency across sources
- **Confidence Levels**: Provides confidence indicators based on the number of sources and agreement percentage
- **Analysis History**: Tracks previous analyses for easy reference
- **Detailed Reports**: Shows fact-by-fact comparisons and source breakdown

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Python**: 3.8+ (Tested and optimized for Python 3.13 on Windows 10/11)
- **AI/LLM**: Google Gemini API (using google-genai SDK)
- **External APIs**: News API, Google Custom Search API
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript with Bootstrap

## Quick Start

See [SETUP.md](SETUP.md) for detailed installation and configuration instructions.

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure API keys in `.env` file
4. Initialize database: `python run.py init-db`
5. Run the application: `python run.py`
6. Open browser to `http://localhost:5000`

## Project Structure

```
fact-checker-app/
├── app/
│   ├── __init__.py              # Flask app initialization
│   ├── models.py                # Database models
│   ├── routes.py                # API endpoints
│   ├── agents/                  # AI agent modules
│   │   ├── __init__.py
│   │   ├── fact_extractor.py   # Extract facts from articles
│   │   ├── search_agent.py     # Search for similar content
│   │   └── scorer.py           # Score articles
│   ├── services/                # External service integrations
│   │   ├── __init__.py
│   │   ├── gemini_service.py   # Google Gemini integration
│   │   ├── news_api_service.py # News API integration
│   │   └── google_search_service.py # Google Search integration
│   ├── static/                  # CSS, JS files
│   └── templates/               # HTML templates
├── config.py                    # Configuration management
├── requirements.txt             # Python dependencies
├── .env                         # API keys (not in git)
├── .env.example                 # Environment template
├── .gitignore
├── README.md
├── SETUP.md
└── run.py                       # Application entry point
```

## How It Works

1. **User Input**: User provides a URL or text of an article to fact-check
2. **Fact Extraction**: Gemini AI extracts key facts, claims, entities, dates, and locations
3. **Source Search**: The app searches for related articles and official sources
4. **Fact Comparison**: Extracted facts are compared against information from found sources
5. **Scoring**: An accuracy score is calculated based on:
   - Source reliability weights (official docs > news > social media)
   - Consensus strength (how many sources agree)
   - Fact verification percentage
6. **Report Generation**: A detailed report shows the overall score, confidence level, and fact-by-fact analysis

## Scoring Algorithm

- **Official sources** (.gov, .edu): 100% weight
- **Established news organizations**: 80% weight
- **General news sites**: 60% weight
- **Blogs/Opinion sites**: 40% weight
- **Social media**: 30% weight

**Confidence Levels**:
- **High**: 5+ sources checked, 80%+ agreement
- **Medium**: 3-4 sources checked, 60-79% agreement
- **Low**: <3 sources or <60% agreement

## API Endpoints

- `POST /api/analyze` - Submit article URL for analysis
- `GET /api/analysis/<id>` - Get analysis results
- `GET /api/history` - List previous analyses
- `GET /api/report/<id>` - Get detailed report

## Development

This is a local development version. For production deployment, additional considerations include:
- Using PostgreSQL instead of SQLite
- Implementing request rate limiting
- Adding user authentication
- Caching frequently analyzed URLs
- Using task queues (Celery) for async processing
- Implementing comprehensive error handling and logging

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please open an issue on the repository.
