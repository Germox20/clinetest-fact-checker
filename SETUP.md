# Setup Instructions

This guide will walk you through setting up the Fact Checker App on your local machine.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8 or higher** (Tested with Python 3.13) - [Download Python](https://www.python.org/downloads/)
- **pip** (Python package manager - comes with Python)
- **Git** (optional, for cloning) - [Download Git](https://git-scm.com/)
- A web browser (Chrome, Firefox, Edge, etc.)

To verify your Python installation, run:
```bash
python --version
```

**Note for Windows Users**: This application has been optimized for Windows 10/11 with Python 3.13. Dependencies have been configured to avoid compilation requirements.

## Step 1: Project Setup

### Option A: Clone from Git (if available)
```bash
git clone <repository-url>
cd fact-checker-app
```

### Option B: Use existing directory
If you already have the project files, navigate to the project directory:
```bash
cd path/to/fact-checker-app
```

## Step 2: Create Virtual Environment (Recommended)

Creating a virtual environment keeps your project dependencies isolated:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt when activated.

## Step 3: Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- google-genai (Google Gemini API - latest SDK)
- SQLAlchemy (database ORM)
- newsapi-python (News API client)
- google-api-python-client (Google Search API)
- beautifulsoup4 (HTML parsing)
- python-dotenv (environment variables)
- requests (HTTP requests)

## Step 4: Obtain API Keys

You'll need three API keys for the application to work. Follow these steps:

### 4.1 Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Get API Key"** or **"Create API Key"**
4. Select or create a Google Cloud project
5. Copy the generated API key
6. **Free tier**: 60 requests per minute

**Note**: Keep this key secure and never commit it to version control.

### 4.2 News API Key

1. Go to [NewsAPI.org](https://newsapi.org/)
2. Click **"Get API Key"** in the top navigation
3. Fill out the registration form (choose the free Developer plan)
4. Verify your email address
5. Log in and copy your API key from the dashboard
6. **Free tier**: 100 requests per day, articles up to 1 month old

**Limitations**: The free tier doesn't allow commercial use and has limited historical data.

### 4.3 Google Custom Search API Key and Search Engine ID

This is a two-part process:

#### Part A: Get the API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Custom Search API**:
   - Click on "APIs & Services" > "Library"
   - Search for "Custom Search API"
   - Click on it and click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the generated API key
5. **Free tier**: 100 search queries per day

#### Part B: Create Custom Search Engine and Get Engine ID

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click **"Add"** to create a new search engine
3. Configure your search engine:
   - **Sites to search**: Enter `*.com` to search the entire web (or specific domains)
   - **Name**: Give it a name (e.g., "Fact Checker Search")
   - **Language**: Select your preferred language
4. Click **"Create"**
5. On the overview page, click **"Customize"** in the left sidebar
6. In the "Basic" tab, find the **Search engine ID** and copy it
7. Optional: Turn on "Search the entire web" if you want broader results

## Step 5: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   # On Windows:
   copy .env.example .env
   
   # On macOS/Linux:
   cp .env.example .env
   ```

2. Open the `.env` file in a text editor

3. Replace the placeholder values with your actual API keys:
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   NEWS_API_KEY=your_actual_news_api_key_here
   GOOGLE_SEARCH_API_KEY=your_actual_google_search_api_key_here
   GOOGLE_SEARCH_ENGINE_ID=your_actual_search_engine_id_here
   FLASK_SECRET_KEY=generate_a_random_secret_key_here
   DATABASE_URL=sqlite:///fact_checker.db
   FLASK_ENV=development
   GRPC_VERBOSITY=ERROR
   ```
   
   **Note for Windows users**: The `GRPC_VERBOSITY=ERROR` setting suppresses harmless gRPC/ALTS warnings that appear on non-GCP environments, making it easier to see actual error messages.

4. Generate a Flask secret key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Copy the output and use it for `FLASK_SECRET_KEY`

**Important**: Never commit the `.env` file to version control. It's already in `.gitignore`.

## Step 6: Initialize the Database

Run the database initialization command:

```bash
python run.py init-db
```

This will create the SQLite database file and set up all necessary tables.

## Step 7: Run the Application

Start the Flask development server:

```bash
python run.py
```

You should see output similar to:
```
 * Running on http://127.0.0.1:5000
 * Restarting with stat
 * Debugger is active!
```

## Step 8: Access the Application

Open your web browser and navigate to:
```
http://localhost:5000
```

You should see the Fact Checker App homepage.

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'flask'`
- **Solution**: Make sure you activated the virtual environment and ran `pip install -r requirements.txt`

**Issue**: `API key not found` or `401 Unauthorized` errors
- **Solution**: Verify that your `.env` file exists and contains valid API keys. Check for typos.

**Issue**: Database errors
- **Solution**: Delete the database file (`fact_checker.db`) and run `python run.py init-db` again

**Issue**: `ImportError: cannot import name 'X' from 'Y'`
- **Solution**: Update pip and reinstall requirements:
  ```bash
  pip install --upgrade pip
  pip install -r requirements.txt --upgrade
  ```

**Issue**: Rate limit errors (429 errors)
- **Solution**: You've exceeded the free tier limits. Wait for the rate limit to reset (usually daily or hourly depending on the API)

### API Limits Summary

| API | Free Tier Limit | Reset Period |
|-----|-----------------|--------------|
| Google Gemini | 60 requests/minute | Per minute |
| News API | 100 requests/day | Daily |
| Google Custom Search | 100 queries/day | Daily |

## Deactivating Virtual Environment

When you're done working on the project:

```bash
deactivate
```

## Updating Dependencies

If new packages are added to `requirements.txt`:

```bash
pip install -r requirements.txt --upgrade
```

## Next Steps

Once the application is running:

1. Try analyzing a news article by pasting a URL
2. Review the analysis results and fact-checking report
3. Explore the history of previous analyses
4. Check the console for any errors or warnings

## Development Mode

The application runs in development mode by default with:
- Debug mode enabled (auto-reload on code changes)
- Detailed error messages
- Flask debug toolbar (if installed)

For production deployment, see the main README.md for additional considerations.

## Getting Help

If you encounter issues:

1. Check the error messages in the terminal
2. Review the `.env` file for correct API key configuration
3. Verify all API keys are active and within rate limits
4. Check the [Issues](link-to-issues) page for known problems

## Security Notes

- **Never** share your API keys publicly
- **Never** commit the `.env` file to version control
- Rotate your API keys periodically
- Monitor your API usage to avoid unexpected charges (though all selected APIs have free tiers)
- For production use, implement additional security measures (authentication, rate limiting, etc.)
