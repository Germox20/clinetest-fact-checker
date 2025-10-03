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
        Extract facts from article text using Gemini.
        
        Args:
            article_text (str): The article content to analyze
            article_title (str): Optional article title for context
            
        Returns:
            dict: Dictionary containing extracted facts organized by category
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
                'who': [],
                'what': [],
                'when': [],
                'where': [],
                'claims': [],
                'error': str(e)
            }
    
    def compare_facts(self, original_facts, comparison_facts):
        """
        Compare facts from two sources using Gemini.
        
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
    
    def _build_fact_extraction_prompt(self, article_text, article_title=None):
        """Build prompt for fact extraction."""
        title_context = f"\nTitle: {article_title}\n" if article_title else ""
        
        prompt = f"""You are a fact-checking assistant. Analyze the following article and extract key facts organized by category.

{title_context}
Article:
{article_text[:4000]}

Extract facts in the following categories and return them in JSON format:

1. WHO: People, organizations, entities mentioned (with roles)
2. WHAT: Events, actions, occurrences described
3. WHEN: Dates, times, timeframes mentioned
4. WHERE: Locations, places mentioned
5. CLAIMS: Specific claims, statements, or assertions made

Return ONLY a valid JSON object with this structure:
{{
  "who": ["entity1: role/description", "entity2: role/description"],
  "what": ["event1 description", "event2 description"],
  "when": ["date/time1", "date/time2"],
  "where": ["location1", "location2"],
  "claims": ["claim1", "claim2"]
}}

Each fact should be concise (1-2 sentences max) and specific. Include confidence level (high/medium/low) if relevant.
"""
        return prompt
    
    def _build_fact_comparison_prompt(self, original_facts, comparison_facts):
        """Build prompt for fact comparison."""
        prompt = f"""You are a fact-checking assistant. Compare the facts from two sources and identify:
1. Matching facts (same information in both)
2. Conflicting facts (contradictory information)
3. Facts unique to the original source
4. Facts unique to the comparison source

Original Source Facts:
{json.dumps(original_facts, indent=2)}

Comparison Source Facts:
{json.dumps(comparison_facts, indent=2)}

Return ONLY a valid JSON object with this structure:
{{
  "matching": [
    {{
      "fact": "description of matching fact",
      "confidence": "high/medium/low",
      "category": "who/what/when/where/claims"
    }}
  ],
  "conflicting": [
    {{
      "original": "fact from original",
      "comparison": "contradictory fact from comparison",
      "conflict_type": "contradiction/partial_mismatch/emphasis_difference",
      "category": "who/what/when/where/claims"
    }}
  ],
  "unique_to_original": ["fact1", "fact2"],
  "unique_to_comparison": ["fact1", "fact2"],
  "analysis_notes": "Brief analysis of overall agreement"
}}

Be precise and objective in identifying matches and conflicts.
"""
        return prompt
    
    def _parse_fact_extraction_response(self, response_text):
        """Parse Gemini response for fact extraction."""
        try:
            # Try to extract JSON from response
            # Sometimes Gemini includes markdown code blocks
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
            
            # Ensure all required keys exist
            required_keys = ['who', 'what', 'when', 'where', 'claims']
            for key in required_keys:
                if key not in facts:
                    facts[key] = []
            
            return facts
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini response as JSON: {e}")
            print(f"Response text: {response_text[:500]}")
            # Return empty structure on parse error
            return {
                'who': [],
                'what': [],
                'when': [],
                'where': [],
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
            
            return comparison
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini comparison response: {e}")
            print(f"Response text: {response_text[:500]}")
            return {
                'matching': [],
                'conflicting': [],
                'unique_to_original': [],
                'unique_to_comparison': [],
                'parse_error': str(e)
            }
