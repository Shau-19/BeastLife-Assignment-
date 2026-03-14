import sqlite3
import random
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from classifier.categorize import classify, AUTO_RESOLVABLE

app = FastAPI(title="Beastlife Customer Intelligence API")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DB = "data/beastlife.db"

# only auto-reply if confidence is above this threshold
# below 0.65 = LLM is uncertain → safer to escalate
CONFIDENCE_THRESHOLD = 0.65

AUTO_REPLIES = {
    "Order Tracking":     "Hi! Share your order ID and we will send the live tracking link instantly.",
    "Subscription Issue": "You can manage your plan here: beastlife.in/account/subscription",
    "General Inquiry":    "Delivery: 3-5 days | Returns: 7 days | Free delivery above Rs 499",
}

ESCALATION = {
    "Delivery Delay":    "Assign to logistics team",
    "Refund Request":    "Assign to billing team",
    "Product Complaint": "Assign to quality team — HIGH PRIORITY",
    "Payment Failure":   "Assign to payments team",
}


class Query(BaseModel):
    message:   str
    channel:   str = "Unknown"
    sender_id: str = ""
    provider:  str = "auto"


def save_query(message, channel, category, confidence, provider, auto_resolved, sentiment="neutral"):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO queries "
        "(id, message, category, channel, timestamp, status, confidence, auto_resolved, ai_provider) "
        "VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
        (
            random.randint(900000, 999999),
            message, category, channel,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            confidence,
            1 if auto_resolved else 0,
            f"{provider} | sentiment:{sentiment}",   # store provider + sentiment together
        )
    )
    conn.commit()
    conn.close()


def route(result):
    """
    Guardrail: decide if auto-reply is safe.
    Conditions for auto-reply:
      - category is auto-resolvable
      - confidence above threshold
      - sentiment is not negative (already handled in classifier)
    """
    auto = (
        result["auto_resolvable"]
        and result["confidence"] >= CONFIDENCE_THRESHOLD
    )
    return auto


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.post("/classify")
def classify_query(q: Query):
    """Classify a single message. Used for testing."""
    result = classify(q.message, provider=q.provider)
    auto   = route(result)
    return {
        "category":         result["category"],
        "confidence":       result["confidence"],
        "sentiment":        result["sentiment"],
        "auto_resolvable":  auto,
        "provider":         result["provider"],
        "suggested_action": "AUTO-REPLY" if auto else ESCALATION.get(result["category"], "Escalate to agent"),
    }


@app.post("/webhook")
def webhook(q: Query):
    """Called by Make.com when a message arrives from WhatsApp / Instagram / Email."""
    result = classify(q.message, provider=q.provider)
    auto   = route(result)
    cat    = result["category"]

    save_query(q.message, q.channel, cat,
               result["confidence"], result["provider"],
               auto, result["sentiment"])

    return {
        "category":         cat,
        "confidence":       result["confidence"],
        "sentiment":        result["sentiment"],
        "auto_resolvable":  auto,
        "auto_reply":       AUTO_REPLIES.get(cat) if auto else None,
        "suggested_action": "AUTO-REPLY" if auto else ESCALATION.get(cat, "Escalate to agent"),
    }


@app.get("/stats")
def stats():
    """Category distribution + automation rate. Make.com uses this for daily reports."""
    conn  = sqlite3.connect(DB)
    total = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]

    # category distribution
    cats  = conn.execute(
        "SELECT category, COUNT(*) FROM queries GROUP BY category ORDER BY 2 DESC"
    ).fetchall()

    # automation rate: how many queries were auto-resolved
    auto_n = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE auto_resolved=1"
    ).fetchone()[0]

    # provider usage breakdown
    providers = conn.execute(
        "SELECT ai_provider, COUNT(*) FROM queries GROUP BY ai_provider"
    ).fetchall()

    conn.close()

    return {
        "total":           total,
        "automation_rate": round(auto_n / total * 100, 1) if total else 0,
        "distribution": [
            {"category": c, "count": n, "pct": round(n / total * 100, 1)}
            for c, n in cats
        ],
        "providers": dict(providers),
    }