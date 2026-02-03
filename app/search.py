"""
Search Module for Multi-Tenant Document Search

This module implements keyword-based search with strict tenant isolation.

MULTI-TENANT SEARCH ISOLATION:
- All search functions require explicit tenant_id parameter
- Search ONLY operates on the specified tenant's documents
- No cross-tenant document access is possible
- Results always include source document information

SEARCH ALGORITHM:
Simple keyword matching is used for this MVP:
1. Question is tokenized into keywords
2. Each document is scored by keyword matches
3. Best matching document is returned
4. If no match, explicit "no information" response
"""

from typing import Optional, Tuple, List
import re
import logging
import unicodedata

from .data_loader import get_tenant_documents
from .models import Document

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """
    Normalize text for accent-insensitive comparison.
    Removes accents and converts to lowercase.
    
    Example: "résiliation" -> "resiliation"
    """
    # Decompose unicode characters (é -> e + combining accent)
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining characters (accents)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.lower()


# =============================================================================
# SEARCH CONFIGURATION
# =============================================================================

# Minimum keyword length to consider (filters out common short words)
MIN_KEYWORD_LENGTH: int = 3

# Minimum match score to consider a document relevant
MIN_RELEVANCE_SCORE: float = 0.1

# Stop words to ignore in search (French + English common words)
STOP_WORDS = {
    # French
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "est", "en",
    "que", "qui", "dans", "pour", "sur", "avec", "ce", "cette", "ces",
    "son", "sa", "ses", "au", "aux", "par", "pas", "plus", "moins",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "and", "or", "but", "if", "then",
    "than", "so", "as", "of", "to", "for", "with", "on", "at", "by",
    "from", "this", "that", "these", "those", "what", "which", "who",
}


# =============================================================================
# TEXT PROCESSING
# =============================================================================

def _extract_keywords(text: str) -> List[str]:
    """
    Extract meaningful keywords from text.
    
    Args:
        text: Input text to process
        
    Returns:
        List of normalized lowercase keywords (accents removed)
    """
    # Normalize text (remove accents, lowercase)
    text_normalized = _normalize_text(text)
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text_normalized)
    
    # Filter out short words and stop words
    keywords = [
        word for word in words 
        if len(word) >= MIN_KEYWORD_LENGTH and word not in STOP_WORDS
    ]
    
    logger.debug(f"Extracted keywords from '{text[:50]}...': {keywords}")
    
    return keywords


def _calculate_relevance_score(question_keywords: List[str], document: Document) -> float:
    """
    Calculate relevance score between question and document.
    
    Uses accent-insensitive matching for French text support.
    
    Args:
        question_keywords: Extracted keywords from question (already normalized)
        document: Document to score
        
    Returns:
        Relevance score between 0.0 and 1.0
    """
    if not question_keywords:
        return 0.0
    
    # Normalize document content for accent-insensitive comparison
    content_normalized = _normalize_text(document.content)
    
    # Count matches
    matches = sum(1 for kw in question_keywords if kw in content_normalized)
    
    # Normalize score
    score = matches / len(question_keywords)
    
    return score


# =============================================================================
# MAIN SEARCH FUNCTION (TENANT-ISOLATED)
# =============================================================================

def search_tenant_documents(
    tenant_id: str, 
    question: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Search for an answer to a question within a specific tenant's documents.
    
    MULTI-TENANT ISOLATION:
    - Searches ONLY within the specified tenant's documents
    - tenant_id must be validated before calling this function
    - Returns explicit "no information" if no relevant document found
    
    SEARCH FLOW:
    1. Get tenant's documents (isolated access)
    2. Extract keywords from question
    3. Score each document by keyword relevance
    4. Return best matching document's content (or "no information")
    
    Args:
        tenant_id: Validated tenant identifier (from middleware)
        question: User's question to answer
        
    Returns:
        Tuple of (answer, source_document_title)
        If no relevant document: ("No information available for this client.", None)
    """
    logger.info(f"Searching documents for tenant: {tenant_id}")
    
    # =================================================================
    # STEP 1: Get Tenant's Documents (ISOLATED ACCESS)
    # =================================================================
    documents = get_tenant_documents(tenant_id)
    
    logger.info(f"Found {len(documents)} documents for tenant {tenant_id}")
    
    if not documents:
        logger.warning(f"No documents found for tenant: {tenant_id}")
        return "No information available for this client.", None
    
    # =================================================================
    # STEP 2: Extract Keywords from Question
    # =================================================================
    question_keywords = _extract_keywords(question)
    
    logger.info(f"Extracted keywords: {question_keywords} from question: {question}")
    
    if not question_keywords:
        logger.warning(f"No keywords extracted from question: {question}")
        return "No information available for this client.", None
    
    # =================================================================
    # STEP 3: Score Each Document
    # =================================================================
    scored_documents: List[Tuple[float, Document]] = []
    
    for doc in documents:
        score = _calculate_relevance_score(question_keywords, doc)
        logger.info(f"Document '{doc.title}' scored: {score:.2f} (content preview: {doc.content[:100]}...)")
        if score > 0:
            scored_documents.append((score, doc))
    
    # =================================================================
    # STEP 4: Return Best Match or "No Information"
    # =================================================================
    if not scored_documents:
        logger.info(f"No relevant documents found for question: {question}")
        return "No information available for this client.", None
    
    # Sort by score descending and get best match
    scored_documents.sort(key=lambda x: x[0], reverse=True)
    best_score, best_doc = scored_documents[0]
    
    # Check minimum relevance threshold
    if best_score < MIN_RELEVANCE_SCORE:
        logger.info(f"Best score {best_score:.2f} below threshold for: {question}")
        return "No information available for this client.", None
    
    logger.info(f"Found answer in '{best_doc.title}' with score: {best_score:.2f}")
    
    # =================================================================
    # STEP 5: Extract Relevant Answer
    # =================================================================
    answer = _extract_answer_from_document(question_keywords, best_doc)
    
    return answer, best_doc.title


def _extract_answer_from_document(keywords: List[str], document: Document) -> str:
    """
    Extract the most relevant portion of a document as an answer.
    
    Strategy: Find sentences containing keywords and return them.
    Uses accent-insensitive matching.
    
    Args:
        keywords: Question keywords to match (already normalized)
        document: Document to extract from
        
    Returns:
        Extracted answer text
    """
    content = document.content
    
    # Split into sentences (handling multiple languages)
    sentences = re.split(r'[.!?\n]+', content)
    
    # Find sentences with keyword matches (accent-insensitive)
    relevant_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Normalize sentence for comparison
        sentence_normalized = _normalize_text(sentence)
        if any(kw in sentence_normalized for kw in keywords):
            relevant_sentences.append(sentence)  # Keep original sentence for display
    
    if relevant_sentences:
        # Return up to 3 most relevant sentences
        return ". ".join(relevant_sentences[:3]) + "."
    
    # Fallback: return first few sentences
    all_sentences = [s.strip() for s in sentences if s.strip()]
    if all_sentences:
        return ". ".join(all_sentences[:2]) + "."
    
    return content[:500]  # Ultimate fallback


# =============================================================================
# HELPER FUNCTIONS FOR TESTING/DEBUGGING
# =============================================================================

def list_tenant_documents(tenant_id: str) -> List[str]:
    """
    List all document titles for a tenant.
    
    Useful for debugging and testing tenant isolation.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        List of document titles
    """
    documents = get_tenant_documents(tenant_id)
    return [doc.title for doc in documents]
