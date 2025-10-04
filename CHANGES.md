## Fact Checker App - System Improvements

### Overview
This document explains the major changes made to improve source relevance and reduce false matches in the fact-checking system.

---

## Problem Statement

The original system was finding many **unrelated news articles** during source comparison because:

1. **Flat fact structure**: WHO, WHAT, WHEN, WHERE, CLAIMS were stored as separate, unconnected lists
2. **Generic matching**: Articles matched based on shared entities (names, places) even when discussing different events
3. **Equal priority**: All fact types were weighted equally in searches
4. **No relevance filtering**: All found sources were analyzed regardless of topic relevance

**Example Problem:**
- Original article: "Elon Musk launches new AI company in San Francisco"
- False match: "Elon Musk visits San Francisco factory" (different event, same entities)

---

## Solution: Hierarchical Facts with Context-Aware Matching

### 1. Database Schema Changes

**File: `app/models.py`**

**OLD Structure:**
```python
class Fact:
    fact_text = Column(Text)
    category = Column(String)  # 'who', 'what', 'when', 'where', 'claim'
```

**NEW Structure:**
```python
class Fact:
    fact_text = Column(Text)
    category = Column(String)  # Only 'what' or 'claim' (primary categories)
    
    # Related entities (WHO, WHERE, WHEN are now properties of WHAT/CLAIM)
    related_who = Column(Text)  # JSON array
    related_where = Column(Text)  # JSON array
    related_when = Column(Text)  # JSON array
    
    # New fields
    importance_score = Column(Float)  # 0.0-1.0 for search prioritization
    parent_fact_id = Column(Integer)  # For hierarchical relationships
```

**Key Improvement:** Facts now carry their full context. A WHAT fact like "Company launches product" includes WHO (the company), WHERE (location), WHEN (date) as related entities.

---

### 2. AI Prompt Changes

**File: `app/services/gemini_service.py`**

#### OLD Prompt Structure:
```
Extract facts in 5 categories:
1. WHO: List of people/organizations
2. WHAT: List of events
3. WHEN: List of dates
4. WHERE: List of locations
5. CLAIMS: List of assertions
```

#### NEW Prompt Structure:
```
Extract facts in 2 PRIMARY categories:

1. WHAT FACTS (Events with context):
   - event: "Main event description"
   - related_who: ["Entity1", "Entity2"]
   - related_where: ["Location"]
   - related_when: ["Date/timeframe"]
   - importance: "high/medium/low"

2. CLAIMS (Assertions with context):
   - claim: "Main assertion"
   - related_who: ["Who made/subject"]
   - related_where: ["Where applies"]
   - related_when: ["When made/applies"]
   - importance: "high/medium/low"
```

**Key Improvements:**
- Each fact is **self-contained** with full context
- **Importance levels** help prioritize core events
- **Fewer, higher-quality** facts (3-7 WHAT + 2-5 CLAIMS vs. dozens of disconnected items)

---

### 3. Search Query Building

**File: `app/services/news_api_service.py`**

#### OLD Approach:
```python
# Took first 2 WHO entities + first 1 WHAT + first 1 WHERE
query = "Elon Musk Tesla San Francisco"
# Result: ANY article with these terms, regardless of event
```

#### NEW Approach:
```python
# PRIORITY 1: High-importance WHAT facts with context
query = '"launches new AI company" "Elon Musk"'

# PRIORITY 2: High-importance CLAIMS (if present)
# PRIORITY 3: Medium-importance WHAT facts (if needed)
```

**Key Improvements:**
- **Quoted phrases** for exact event matching
- **Prioritizes events over entities**
- **Includes key WHO entity for disambiguation**
- **Focused queries** = More relevant results

---

### 4. Context-Aware Fact Comparison

**File: `app/services/gemini_service.py` - Comparison Prompt**

#### OLD Matching Rules:
```
Match if facts share entities or keywords
```

#### NEW Matching Rules:
```
CRITICAL: Facts match ONLY when BOTH:
1. Same event/claim described
2. Similar context (who/where/when)

Example:
✓ MATCH: Both say "Company X launches Product Y in 2024"
✗ NO MATCH: "Company X" + "Product Y" in different events
✗ NO MATCH: Same person, different locations/actions
```

**Relevance Score (NEW):**
```
0.8-1.0: Highly relevant, same core events
0.5-0.7: Moderately relevant, some overlap  
0.0-0.4: Low relevance, different topics
```

**Key Improvement:** Sources with relevance < 0.4 are **automatically filtered out**.

---

### 5. Source Filtering

**File: `app/agents/scorer.py`**

#### NEW Feature:
```python
def compare_and_score(...):
    comparison_result = self.gemini.compare_facts(...)
    relevance_score = comparison_result.get('relevance_score', 0.5)
    
    # Filter out irrelevant sources
    if relevance_score < 0.4:
        print(f"Skipping low-relevance source...")
        return None  # Don't analyze this source
```

**Key Improvement:** Unrelated sources are now **excluded from analysis**, not just scored lower.

---

## Migration Process

### Database Migration Script

**File: `migrate_db.py`**

```bash
# Run migration
python migrate_db.py

# Prompts user for confirmation
# Deletes old database
# Creates new schema with hierarchical structure
```

**What It Does:**
1. Backs up/deletes existing `instance/fact_checker.db`
2. Creates new schema with updated Fact model
3. Verifies all tables created successfully

---

## Before & After Comparison

### Example Article: "Tesla opens new factory in Germany"

#### OLD SYSTEM:

**Search Query:**
```
"Tesla" "opens new" "Germany"
```

**Sources Found:**
1. ✓ Tesla Germany factory opening (RELEVANT)
2. ✗ Tesla CEO visits Germany (IRRELEVANT - different event)
3. ✗ Germany approves Tesla permit (IRRELEVANT - different timeframe)
4. ✗ Tesla stock rises after Germany news (IRRELEVANT - different topic)

**Result:** 25% relevant sources

---

#### NEW SYSTEM:

**Search Query:**
```
"Tesla opens new factory" "Tesla" "Germany"
```

**Facts Extracted:**
```json
{
  "what_facts": [{
    "event": "Tesla opens new manufacturing facility",
    "related_who": ["Tesla", "Elon Musk"],
    "related_where": ["Germany", "Brandenburg"],
    "related_when": ["2024"],
    "importance": "high"
  }]
}
```

**Sources Found & Filtered:**
1. ✓ Tesla Germany factory opening (relevance: 0.95) → ANALYZED
2. ✗ Tesla CEO visits Germany (relevance: 0.35) → **SKIPPED**
3. ✗ Germany approves Tesla permit (relevance: 0.45) → ANALYZED (related event)
4. ✗ Tesla stock rises (relevance: 0.25) → **SKIPPED**

**Result:** 100% of analyzed sources are relevant

---

## Key Benefits

1. **Higher Precision**: Only analyzes sources discussing the same events
2. **Better Scores**: Accuracy scores reflect true agreement, not entity overlap  
3. **Faster Analysis**: Fewer irrelevant sources = quicker processing
4. **Clearer Reports**: Users see genuinely corroborating/conflicting sources
5. **Scalable**: Importance scoring allows focusing on core facts

---

## Technical Implementation Summary

| Component | Change | Impact |
|-----------|--------|--------|
| **Database** | Hierarchical facts | Context preserved |
| **AI Prompts** | Structured extraction | Fewer, richer facts |
| **Search** | Event-focused queries | Relevant results |
| **Comparison** | Context-aware matching | Accurate scoring |
| **Filtering** | Relevance threshold | Removes noise |

---

## Files Modified

1. `app/models.py` - New Fact schema
2. `app/services/gemini_service.py` - Updated prompts & parsing
3. `app/services/news_api_service.py` - Priority-based search queries
4. `app/agents/fact_extractor.py` - Hierarchical fact storage
5. `app/agents/scorer.py` - Relevance filtering
6. `app/routes.py` - Handle None returns from filtering
7. `migrate_db.py` - NEW - Database migration tool

---

## Usage

### For Users:

1. **Run Migration:**
   ```bash
   python migrate_db.py
   ```

2. **Start App:**
   ```bash
   python run.py
   ```

3. **Analyze Articles:**
   - Paste article URL or text
   - System now finds more relevant sources
   - Better accuracy scores

### For Developers:

The new system is **backward compatible** for display:
- `get_facts_for_article()` returns hierarchical structure
- `get_facts_for_display()` returns flattened structure for templates

---

## Future Enhancements

1. **Semantic Search**: Use embeddings for even better relevance
2. **Entity Resolution**: Link same entities across sources
3. **Temporal Analysis**: Track how facts evolve over time
4. **Source Clustering**: Group sources by sub-topics

---

**Last Updated:** October 4, 2025
**Version:** 2.0
