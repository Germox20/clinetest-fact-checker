# Fact Checker App

A web application that assists users in fact-checking information from news articles and social media posts using AI-powered analysis with hierarchical fact structures.

## Overview

The Fact Checker App uses Google Gemini AI to extract facts from articles using a **hierarchical structure** where WHAT events and CLAIMS are primary facts that contain related WHO/WHERE/WHEN entities. It searches for corroborating sources using News API and Google Custom Search, and assigns accuracy scores based on context-aware matching and source reliability.

## Key Features

### 🔍 **Hierarchical Fact Extraction**
- WHAT facts (events) and CLAIMS are primary structures
- WHO, WHERE, WHEN are related entities within facts
- Importance scoring (high/medium/low) prioritizes core events
- Context-aware fact matching prevents false positives

### 🎯 **Smart Source Discovery**
- Event-focused search queries using high-importance facts
- Automatic relevance filtering (filters out < 0.4 relevance)
- Multi-source verification (News API + Google Custom Search)
- Source prioritization (official > news > blogs > social)

### 📊 **Accurate Scoring**
- Context-aware fact comparison (event + entities must match)
- Weighted scoring by source reliability
- Confidence levels based on source count and agreement
- Relevance scoring to filter unrelated articles

### 📝 **Comprehensive Reports**
- Detailed fact-by-fact analysis
- Source-by-source breakdown
- Matching and conflicting facts highlighted
- Actionable recommendations

### 💾 **Analysis History**
- Tracks all previous analyses
- Easy access to past reports
- Searchable history

## What's New in v2.0

### Hierarchical Fact Structure
- **OLD**: Facts were flat lists (WHO, WHAT, WHEN, WHERE, CLAIMS)
- **NEW**: WHAT and CLAIMS contain related entities for full context

### Context-Aware Matching
- **OLD**: Articles matched if they shared names/places
- **NEW**: Articles must discuss same events in similar context

### Relevance Filtering
- Automatically filters sources with relevance < 0.4
- Prevents analysis of unrelated articles
- Improves accuracy and speed

### Event-Focused Searches
- Search queries prioritize actual events over entities
- Uses quoted phrases for exact matching
- Better source discovery

## Technology Stack

- **Backend**: Flask (Python web framework)
- **Python**: 3.8+ (Tested and optimized for Python 3.13 on Windows 10/11)
- **AI/LLM**: Google Gemini 2.0 Flash Exp (using google-genai SDK)
- **External APIs**: News API, Google Custom Search API
- **Database**: SQLite with hierarchical fact schema
- **Frontend**: HTML, CSS, JavaScript with Bootstrap

## Quick Start

See [SETUP.md](SETUP.md) for detailed installation and configuration instructions.

### Initial Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure API keys in `.env` file
4. **Migrate database**: `python migrate_db.py`
5. Run the application: `python run.py`
6. Open browser to `http://localhost:5000`

### Database Migration

If upgrading from v1.x:
```bash
# Run migration script (will delete old database)
python migrate_db.py

# Or manually:
# 1. Delete old database: rm instance/fact_checker.db
# 2. Create new schema: python run.py init-db
```

## Project Structure

```
fact-checker-app/
├── app/
│   ├── __init__.py              # Flask app initialization
│   ├── models.py                # Database models (hierarchical Fact model)
│   ├── routes.py                # API endpoints with logging
│   ├── agents/                  # AI agent modules
│   │   ├── __init__.py
│   │   ├── fact_extractor.py   # Extract hierarchical facts
│   │   ├── search_agent.py     # Search with event-focused queries
│   │   └── scorer.py           # Context-aware comparison & scoring
│   ├── services/                # External service integrations
│   │   ├── __init__.py
│   │   ├── gemini_service.py   # Gemini with structured prompts
│   │   ├── news_api_service.py # News API with priority queries
│   │   └── google_search_service.py # Google Search integration
│   ├── static/                  # CSS, JS files
│   └── templates/               # HTML templates
├── config.py                    # Configuration management
├── requirements.txt             # Python dependencies
├── migrate_db.py                # Database migration script
├── .env                         # API keys (not in git)
├── .env.example                 # Environment template
├── .gitignore
├── README.md
├── SETUP.md
├── CHANGES.md                   # Detailed explanation of v2.0 changes
└── run.py                       # Application entry point
```

## How It Works

### 1. Hierarchical Fact Extraction
```json
{
  "what_facts": [{
    "event": "Company launches new product",
    "related_who": ["Company Name", "CEO Name"],
    "related_where": ["City", "Country"],
    "related_when": ["2024", "January"],
    "importance": "high",
    "confidence": "high"
  }],
  "claims": [{
    "claim": "Product will revolutionize industry",
    "related_who": ["CEO Name"],
    "importance": "medium"
  }]
}
```

### 2. Event-Focused Search
- **Priority 1**: High-importance WHAT facts with quoted phrases
- **Priority 2**: High-importance CLAIMS
- **Priority 3**: Medium-importance WHAT facts

Example query: `"Company launches new product" "Company Name"`

### 3. Context-Aware Matching
Facts match ONLY when:
- Same event/claim described
- Similar context (who/where/when align)

**Match**: Both say "Company X launches Product Y in 2024"
**No Match**: "Company X" + "Product Y" in different contexts

### 4. Relevance Filtering
- Each source gets relevance score (0.0-1.0)
- Sources with relevance < 0.4 are automatically filtered
- Only relevant sources are analyzed

### 5. Weighted Scoring
Accuracy score considers:
- **Source reliability** (official > news > blog > social)
- **Fact agreement** (matching vs. conflicting facts)
- **Confidence levels** (high > medium > low)
- **Relevance** (how well source covers same events)

## Scoring System

### Source Weights
- **Official sources** (.gov, .edu): 100% weight
- **Major news organizations**: 80% weight
- **General news sites**: 60% weight
- **Blogs/Opinion sites**: 40% weight
- **Social media**: 30% weight

### Confidence Levels
- **High**: 5+ relevant sources, 80%+ agreement
- **Medium**: 3-4 relevant sources, 60-79% agreement
- **Low**: <3 sources or <60% agreement

### Relevance Thresholds
- **0.8-1.0**: Highly relevant (same core events)
- **0.5-0.7**: Moderately relevant (some overlap)
- **0.4-0.5**: Low relevance (analyzed with caution)
- **0.0-0.4**: Irrelevant (automatically filtered out)

## API Endpoints

- `POST /api/analyze` - Submit article for analysis (URL or text)
- `GET /api/report/<id>` - Get detailed report
- `GET /api/history` - List previous analyses
- `GET /api/health` - Health check

## Console Logging

The system provides detailed console output:

```
============================================================
STEP 1: Extracting facts from original article
============================================================
Processing URL: https://example.com/article
✓ Article processed: Article Title
✓ Extracted 3 WHAT facts
✓ Extracted 2 CLAIMS

============================================================
STEP 2: Searching for corroborating sources
============================================================
→ Searching News API...
  News API Query: '"main event" "entity"'
  ✓ News API returned 5 articles
✓ Found 5 sources from News API

============================================================
STEP 3: Analyzing sources
============================================================
→ Analyzing source 1/5
  → Fetching article content...
  ✓ Content fetched (2500 chars)
  → Extracting facts...
  ✓ Extracted 4 WHAT facts, 1 claims
  → Comparing facts...
  ✓ Analysis complete - Score: 75.3

✓ Total sources analyzed: 3 (2 filtered as irrelevant)
```

## Configuration

Key settings in `config.py`:
- `MAX_SOURCES_TO_CHECK`: Max sources to analyze (default: 10)
- `ARTICLE_FETCH_TIMEOUT`: Timeout for fetching articles (default: 10s)
- `SOURCE_WEIGHTS`: Reliability weights by source type
- `CONFIDENCE_THRESHOLDS`: Min sources/agreement for confidence levels

Relevance threshold (in scorer.py):
- Default: 0.4 (can be adjusted based on needs)

## Development

### Running Tests
```bash
# Test with a sample article
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### Debugging
- Enable Flask debug mode in `run.py`
- Check console for detailed step-by-step logs
- Review database: `sqlite3 instance/fact_checker.db`

### Future Enhancements
- Semantic search using embeddings
- Entity resolution across sources
- Temporal fact tracking
- Source clustering by sub-topics
- User authentication
- API rate limiting
- Async processing with Celery

## Documentation

- **README.md** (this file) - Overview and usage
- **SETUP.md** - Detailed setup instructions
- **CHANGES.md** - Technical explanation of v2.0 improvements
- **Code comments** - Inline documentation

## Troubleshooting

### No Sources Found
1. Check console logs for search queries
2. Verify API keys are configured
3. Try a more mainstream news topic
4. Check if APIs have rate limits

### All Sources Filtered
1. Lower relevance threshold in `scorer.py`
2. Check if article topic is too specific
3. Review Gemini's relevance scores in logs

### Database Errors
1. Run migration: `python migrate_db.py`
2. Or recreate: `rm instance/fact_checker.db && python run.py init-db`

## License

MIT License

## Contributing

Contributions are welcome! Please:
1. Open an issue to discuss changes
2. Follow existing code style
3. Add tests for new features
4. Update documentation

## Support

For issues or questions:
- Check CHANGES.md for technical details
- Review console logs for debugging
- Open an issue on the repository

---

**Version**: 2.0  
**Last Updated**: October 2025  
**Python**: 3.8+  
**Status**: Production Ready
