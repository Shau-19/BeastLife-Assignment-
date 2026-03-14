import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import re
import json

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ── valid categories ──────────────────────────────────────────────────────────
# used both for classification and output validation guardrail

CATEGORIES = [
    "Order Tracking",
    "Delivery Delay",
    "Refund Request",
    "Product Complaint",
    "Subscription Issue",
    "Payment Failure",
    "General Inquiry",
]

# categories safe to auto-reply without a human agent
AUTO_RESOLVABLE = {
    "Order Tracking":     True,
    "Subscription Issue": True,
    "General Inquiry":    True,
    "Delivery Delay":     False,
    "Refund Request":     False,
    "Product Complaint":  False,
    "Payment Failure":    False,
}

# Using few shot prompting with proper guardrails to ensure LLM outputs structured JSON with category + confidence score.
# Use of guardrails like NeMo can be made in future

PROMPT = """You are a customer support classifier for Beastlife, a fitness supplements brand.

Classify the message into ONE of these categories:
Order Tracking, Delivery Delay, Refund Request, Product Complaint,
Subscription Issue, Payment Failure, General Inquiry

Examples:
- "where is my order #845231?" -> Order Tracking
- "my order is 5 days late still not arrived" -> Delivery Delay
- "i want refund for damaged product" -> Refund Request
- "wrong item sent quality is terrible" -> Product Complaint
- "subscription auto renewed without notice" -> Subscription Issue
- "payment failed but money deducted from account" -> Payment Failure
- "what is your return policy?" -> General Inquiry

Reply ONLY with JSON: {"category": "...", "confidence": 0.0-1.0, "reason": "..."}"""

# ── keyword rules for offline fallback ───────────────────────────────────────

KEYWORDS = {
    "Order Tracking":     ["order status", "where is my order", "tracking", "dispatched", "order #", "when will it ship"],
    "Delivery Delay":     ["delayed", "late", "not arrived", "still waiting", "stuck in transit", "days ago"],
    "Refund Request":     ["refund", "return", "money back", "refund pls", "cancel", "reimburse", "charged twice"],
    "Product Complaint":  ["wrong product", "damaged", "defective", "expired", "poor quality", "broken", "scam", "broke", "fake"],
    "Subscription Issue": ["subscription", "auto-renew", "cancel plan", "pause", "billing cycle", "plan"],
    "Payment Failure":    ["payment failed", "declined", "deducted", "double charge", "gateway error", "upi"],
    "General Inquiry":    ["return policy", "delivery time", "do you deliver", "working hours", "free delivery", "whats your", "what is your"],
}

# ── sentiment guardrail words ─────────────────────────────────────────────────
# angry customers always escalate regardless of category

NEGATIVE_WORDS = [
    "terrible", "worst", "horrible", "angry", "furious", "disgusting",
    "scam", "fraud", "useless", "pathetic", "cheated", "lawsuit",
    "never buying", "consumer forum",
]

# ── prompt injection patterns ─────────────────────────────────────────────────
# block these before sending to LLM

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "developer mode",
    "jailbreak",
    "act as",
]


def sanitize(message):
    #Guardrail 1: block prompt injection attempts.
    msg_lower = message.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in msg_lower:
            return "[blocked: injection attempt detected]"
    return message


def detect_sentiment(message):
    #Guardrail 2: detect negative sentiment. Angry customers always escalate.
    if any(word in message.lower() for word in NEGATIVE_WORDS):
        return "negative"
    return "neutral"


def validate_output(result):
    
    #Guardrail 3: output validation.
    #If LLM returns unknown category or out-of-range confidence, correct it.
    
    if result.get("category") not in CATEGORIES:
        result["category"]   = "General Inquiry"
        result["confidence"] = 0.4
        result["reason"]     = "Invalid category returned — defaulted"

    # clamp confidence to valid range (LLMs can sometimes return 1.7 etc.)
    result["confidence"] = max(0.0, min(float(result.get("confidence", 0.5)), 1.0))
    return result


def _llm_classify(message, client, model):
    #Passing the JSON response to LLM API and parsing the output. Guardrails ensure structured output and prevent prompt injection.
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user",   "content": message},
        ],
        temperature=0.1,
        max_tokens=100,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def _rule_classify(message):
    #Rule-based fallback using keyword matching. No API needed.
    msg    = message.lower()
    scores = {cat: sum(1 for kw in kws if kw in msg) for cat, kws in KEYWORDS.items()}
    best   = max(scores, key=scores.get)
    count  = scores[best]
    return {
        "category":   best if count > 0 else "General Inquiry",
        "confidence": min(0.55 + count * 0.08, 0.82),
        "reason":     f"Matched {count} keyword(s)",
    }


def classify(message, provider="auto"):
    """
    Full classification pipeline with guardrails:
      1. Sanitize   — block prompt injection
      2. LLM        — Groq → OpenAI → Rule-based
      3. Validate   — check category + clamp confidence
      4. Sentiment  — negative sentiment forces escalation
    """
    # guardrail 1: sanitize before touching LLM
    clean = sanitize(message)

    result = None

    if Groq and provider in ("auto", "groq") and os.getenv("GROQ_API_KEY"):
        try:
            result = _llm_classify(clean, Groq(), "llama-3.3-70b-versatile")
            result["provider"] = "Groq"
        except Exception:
            pass

    if result is None and OpenAI and provider in ("auto", "openai") and os.getenv("OPENAI_API_KEY"):
        try:
            result = _llm_classify(clean, OpenAI(), "gpt-4o-mini")
            result["provider"] = "OpenAI"
        except Exception:
            pass

    if result is None:
        result = _rule_classify(clean)
        result["provider"] = "Rule-Based"

    # guardrail 3: validate output
    result = validate_output(result)

    # guardrail 2: sentiment check — overrides auto_resolvable if angry
    sentiment          = detect_sentiment(message)
    result["sentiment"] = sentiment
    auto               = AUTO_RESOLVABLE.get(result["category"], False)
    result["auto_resolvable"] = False if sentiment == "negative" else auto

    return result
