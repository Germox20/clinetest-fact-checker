"""Google Gemini API service for AI-powered fact extraction and analysis."""
from google import genai
from google.genai import types
from config import Config
import json
import os


class GeminiService:
    """Service for interacting with Google Gemini API."""
    
    def __init__(self):
        """Initialize the Gemini service with API key."""
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in configuration")
        
        # Initialize the client with API key
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
    
    def extract_facts(self, article_text, article_title=None):
        """
        Extract facts from article text using Gemini with hierarchical structure.
        
        Args:
            article_text (str): The article content to analyze
            article_title (str): Optional article title for context
            
        Returns:
            dict: Dictionary containing extracted facts organized hierarchically
        """
        prompt = self._build_fact_extraction_prompt(article_text, article_title)
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            facts = self._parse_fact_extraction_response(response.text)
            return facts
        except Exception as e:
            print(f"Error extracting facts with Gemini: {e}")
            return {
                'what_facts': [],
                'claims': [],
                'error': str(e)
            }
    
    def compare_facts(self, original_facts, comparison_facts):
        """
        Compare facts from two sources using Gemini with context-aware matching.
        
        Args:
            original_facts (dict): Facts from the original article
            comparison_facts (dict): Facts from comparison article
            
        Returns:
            dict: Analysis of matching, conflicting, and unique facts
        """
        prompt = self._build_fact_comparison_prompt(original_facts, comparison_facts)
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            comparison = self._parse_fact_comparison_response(response.text)
            return comparison
        except Exception as e:
            print(f"Error comparing facts with Gemini: {e}")
            return {
                'matching': [],
                'conflicting': [],
                'unique_to_original': [],
                'unique_to_comparison': [],
                'error': str(e)
            }
    
    def generate_summary(self, article_text, max_words=150):
        """
        Generate a summary of the article.
        
        Args:
            article_text (str): The article content to summarize
            max_words (int): Maximum number of words in summary
            
        Returns:
            str: Summary text
        """
        prompt = f"""Summarize the following article in {max_words} words or less. 
Focus on the main facts and claims.

Article:
{article_text[:3000]}

Summary:"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"Error generating summary with Gemini: {e}")
            return "Error generating summary"
    
    def optimize_search_query(self, facts, attempt=1):
        """
        Generate optimized search queries from hierarchical facts.
        Creates complete, coherent queries for better search results.
        
        Args:
            facts (dict): Hierarchical facts structure
            attempt (int): Attempt number for progressive refinement
            
        Returns:
            dict: {
                'primary_query': str,
                'alternative_queries': list,
                'keywords': list
            }
        """
        prompt = self._build_query_optimization_prompt(facts, attempt)
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            query_data = self._parse_query_optimization_response(response.text)
            return query_data
        except Exception as e:
            print(f"Error optimizing search query with Gemini: {e}")
            # Fallback to basic query
            return self._create_fallback_query(facts)
    
    def _build_fact_extraction_prompt(self, article_text, article_title=None):
        """Build prompt for hierarchical fact extraction."""
        title_context = f"\nTitle: {article_title}\n" if article_title else ""
        
        prompt = f"""You are a fact-checking assistant. Analyze the following article and extract facts using a HIERARCHICAL structure where events and claims are primary, and people/places/times are related entities.

{title_context}
Article:
{article_text[:4000]}

Extract facts in TWO PRIMARY CATEGORIES:

1. **WHAT FACTS** (Events/Actions/Occurrences):
   - Main event or action described
   - Related WHO: entities involved (people, organizations)
   - Related WHERE: locations where it occurred
   - Related WHEN: timeframe/date when it occurred
   - Importance: high/medium/low (based on centrality to article)

2. **CLAIMS** (Assertions/Statements):
   - Main claim, statement, or assertion
   - Related WHO: who made the claim or who it's about
   - Related WHERE: where it applies or was made
   - Related WHEN: when it was made or applies
   - Importance: high/medium/low (based on significance)

**IMPORTANCE GUIDELINES:**
- HIGH: Core events/claims that define the article's main topic
- MEDIUM: Supporting details that add context
- LOW: Minor details or tangential information

Return ONLY a valid JSON object with this EXACT structure:
{{
  "what_facts": [
    {{
      "event": "Clear description of the main event or action (2-3 sentences max)",
      "related_who": ["Person/organization involved", "Another entity"],
      "related_where": ["Location"],
      "related_when": ["Timeframe or date"],
      "importance": "high",
      "confidence": "high"
    }}
  ],
  "claims": [
    {{
      "claim": "Specific claim or assertion made (2-3 sentences max)",
      "related_who": ["Who made it or who it's about"],
      "related_where": ["Where it applies"],
      "related_when": ["When it was made/applies"],
      "importance": "high",
      "confidence": "high"
    }}
  ]
}}

**CRITICAL RULES:**
1. Each WHAT fact must include the event PLUS its context (who/where/when)
2. Each CLAIM must include the assertion PLUS its context
3. Prioritize HIGH importance for facts that are central to the article
4. Keep event/claim descriptions focused and specific
5. Include 3-7 WHAT facts and 2-5 CLAIMS (prioritize quality over quantity)
6. Confidence levels: "high" (clearly stated), "medium" (implied), "low" (uncertain)
"""
        return prompt
    
    def _build_fact_comparison_prompt(self, original_facts, comparison_facts):
        """Build prompt for context-aware fact comparison."""
        prompt = f"""You are a fact-checking assistant. Compare facts from two sources using CONTEXT-AWARE matching. 

**IMPORTANT**: Facts match only when BOTH the event/claim AND its context (who/where/when) align. Don't match based on shared entities alone.

Original Source Facts:
{json.dumps(original_facts, indent=2)}

Comparison Source Facts:
{json.dumps(comparison_facts, indent=2)}

**MATCHING RULES:**
1. WHAT facts match if: same event/action + similar who/where/when context
2. CLAIMS match if: same assertion + similar context
3. Partial matches (same event, different details) are CONFLICTS, not matches
4. Shared entities without same event context are NOT matches

**CRITICAL: NUMBER COMPARISON RULES**
- When comparing numerical values, calculate percentage difference
- Difference < 30% of larger number = MATCH, not conflict
- Example: 45 vs 60 → diff is 15/60 = 25% → MATCH with 'moderate' strength
- Only mark as conflict if difference ≥ 30%

**CRITICAL: AMBIGUOUS EXPRESSION RULES**
Apply these mappings when comparing expressions with numbers:
- 0-20: "few", "some", "any"
- 20-50: "some", "various", "many"
- 50-200: "several", "many", "lot" 
- 200+: "huge", "massive", "big"
Example: "many people" (20-200) matches with "45 people" → MATCH

**CRITICAL: NO DUAL CLASSIFICATION**
- A fact should NEVER appear in both matching AND conflicting lists
- If unsure between match and conflict, classify as matching with 'moderate' strength
- If numbers are within 30% tolerance → Always MATCH, never conflict
- If ambiguous expression aligns with number range → Always MATCH, never conflict

**CONFLICT TYPES:**
- "contradiction": Directly opposite information
- "partial_mismatch": Same event but different details (dates, numbers, participants)
- "emphasis_difference": Same event but different focus or interpretation
- "context_mismatch": Same entity but different events

Return ONLY a valid JSON object:
{{
  "matching": [
    {{
      "original_fact": "Full fact from original with context",
      "comparison_fact": "Matching fact from comparison with context",
      "match_strength": "strong/moderate",
      "category": "what/claim"
    }}
  ],
  "conflicting": [
    {{
      "original": "Fact from original",
      "comparison": "Conflicting fact from comparison",
      "conflict_type": "contradiction/partial_mismatch/emphasis_difference/context_mismatch",
      "conflict_severity": "high/medium/low",
      "category": "what/claim"
    }}
  ],
  "unique_to_original": [
    {{
      "fact": "Fact only in original",
      "category": "what/claim",
      "significance": "high/medium/low"
    }}
  ],
  "unique_to_comparison": [
    {{
      "fact": "Fact only in comparison",
      "category": "what/claim",
      "significance": "high/medium/low"
    }}
  ],
  "relevance_score": 0.0,
  "analysis_notes": "Brief analysis focusing on whether sources cover the SAME EVENTS/CLAIMS"
}}

**RELEVANCE SCORE** (0.0-1.0):
- 0.8-1.0: Highly relevant, covers same core events
- 0.5-0.7: Moderately relevant, some overlap
- 0.0-0.4: Low relevance, different topics despite shared entities

Be strict about matching - similar context is required, not just shared names.
"""
        return prompt
    
    def _parse_fact_extraction_response(self, response_text):
        """Parse Gemini response for hierarchical fact extraction."""
        try:
            # Try to extract JSON from response
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            facts = json.loads(json_text)
            
            # Ensure required keys exist
            if 'what_facts' not in facts:
                facts['what_facts'] = []
            if 'claims' not in facts:
                facts['claims'] = []
            
            return facts
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini response as JSON: {e}")
            print(f"Response text: {response_text[:500]}")
            return {
                'what_facts': [],
                'claims': [],
                'parse_error': str(e)
            }
    
    def _parse_fact_comparison_response(self, response_text):
        """Parse Gemini response for fact comparison."""
        try:
            # Extract JSON from response
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            comparison = json.loads(json_text)
            
            # Ensure required keys exist
            required_keys = ['matching', 'conflicting', 'unique_to_original', 'unique_to_comparison']
            for key in required_keys:
                if key not in comparison:
                    comparison[key] = []
            
            # Ensure relevance_score exists
            if 'relevance_score' not in comparison:
                comparison['relevance_score'] = 0.5
            
            return comparison
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini comparison response: {e}")
            print(f"Response text: {response_text[:500]}")
            return {
                'matching': [],
                'conflicting': [],
                'unique_to_original': [],
                'unique_to_comparison': [],
                'relevance_score': 0.0,
                'parse_error': str(e)
            }
    
    def _build_query_optimization_prompt(self, facts, attempt):
        """Build prompt for query optimization."""
        attempt_context = ""
        if attempt > 1:
            attempt_context = f"\n**This is attempt {attempt}** - Previous searches didn't find enough sources. Create MORE SPECIFIC and VARIED queries."
        
        prompt = f"""You are a search query optimization assistant. Given hierarchical facts from an article, create COMPLETE, EFFECTIVE search queries for News API and Google Search.

{attempt_context}

Facts from Article:
{json.dumps(facts, indent=2)}

Create search queries that will find news articles about the SAME EVENTS and CLAIMS.

**QUERY REQUIREMENTS:**
1. Use COMPLETE SENTENCES with full context
2. Include main event + key entities + location/time if relevant
3. Avoid incomplete fragments
4. Each query should be self-contained and clear

Return ONLY a valid JSON object:
{{
  "primary_query": "Main complete sentence describing the core event with entities",
  "alternative_queries": [
    "Alternative phrasing of the event",
    "Query focusing on different aspect of same event",
    "Query with different keywords but same meaning"
  ],
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}

**EXAMPLES:**

Bad queries (DON'T do this):
- "launches new"  ❌ (incomplete)
- "Elon Musk"  ❌ (just a name)
- "San Francisco 2024"  ❌ (no context)

Good queries (DO this):
- "Elon Musk launches new artificial intelligence company in San Francisco"  ✓
- "SpaceX CEO announces AI startup in California January 2024"  ✓
- "Tesla founder Musk unveils new tech venture artificial intelligence"  ✓

Focus on the HIGH-IMPORTANCE WHAT facts and CLAIMS from the input.
"""
        return prompt
    
    def _parse_query_optimization_response(self, response_text):
        """Parse Gemini response for query optimization."""
        try:
            # Extract JSON from response
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            query_data = json.loads(json_text)
            
            # Ensure required keys exist
            if 'primary_query' not in query_data:
                query_data['primary_query'] = ''
            if 'alternative_queries' not in query_data:
                query_data['alternative_queries'] = []
            if 'keywords' not in query_data:
                query_data['keywords'] = []
            
            return query_data
        except json.JSONDecodeError as e:
            print(f"Error parsing query optimization response: {e}")
            print(f"Response text: {response_text[:500]}")
            return {
                'primary_query': '',
                'alternative_queries': [],
                'keywords': [],
                'parse_error': str(e)
            }
    
    def _create_fallback_query(self, facts):
        """Create a basic fallback query if Gemini fails."""
        query_parts = []
        
        # Extract from WHAT facts
        if facts.get('what_facts'):
            for fact in facts['what_facts'][:2]:
                if isinstance(fact, dict):
                    event = fact.get('event', '')
                    if event:
                        # Take first sentence
                        first_sentence = event.split('.')[0]
                        query_parts.append(first_sentence)
        
        # Extract from CLAIMS
        if facts.get('claims'):
            for claim in facts['claims'][:1]:
                if isinstance(claim, dict):
                    claim_text = claim.get('claim', '')
                    if claim_text:
                        first_sentence = claim_text.split('.')[0]
                        query_parts.append(first_sentence)
        
        primary_query = ' '.join(query_parts[:2]) if query_parts else "news"
        
        return {
            'primary_query': primary_query,
            'alternative_queries': [],
            'keywords': []
        }
