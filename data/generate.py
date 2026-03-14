import json
import random
import sqlite3
from datetime import datetime, timedelta

CATEGORIES = {
    "Order Tracking":     0.28,
    "Delivery Delay":     0.20,
    "Refund Request":     0.16,
    "Product Complaint":  0.14,
    "Subscription Issue": 0.10,
    "Payment Failure":    0.07,
    "General Inquiry":    0.05,
}

CHANNELS        = ["WhatsApp", "Instagram DM", "Email", "Website Chat"]
CHANNEL_WEIGHTS = [0.35, 0.30, 0.20, 0.15]

# realistic + informal messages with emojis and typos
# mirrors what real customers actually send on WhatsApp / Instagram
TEMPLATES = {
    "Order Tracking": [
        "where is my order #{id}??",
        "Where is my order #{id}? I placed it {n} days ago.",
        "wheres my package bro order #{id}",
        "Can you share the tracking number for order #{id}?",
        "order #{id} still showing processing when will it ship??",
        "no update on my order placed on {date} 😤",
        "track my order #{id} please",
    ],
    "Delivery Delay": [
        "my order still not here its been {n} days 😡",
        "order was supposed to arrive {n} days ago. still waiting!!",
        "delivery delayed again. order #{id}. very frustrated.",
        "expected delivery was {date} but nothing arrived wtf",
        "order #{id} stuck in transit for a week now",
        "i paid for express delivery but its {n} days late already",
        "courier keeps rescheduling. order #{id}. pathetic service",
    ],
    "Refund Request": [
        "refund pls for order #{id}",
        "i want to return order #{id} and get full refund",
        "received wrong product need refund for #{id}",
        "its been {n} days still no refund. where is my money??",
        "charged twice for order #{id} please refund the extra",
        "refund of rs {amt} not credited yet. order #{id}",
        "product not as described requesting refund and return pickup",
    ],
    "Product Complaint": [
        "wrong item sent!! i ordered {product} not this",
        "my {product} stopped working after {n} days only",
        "packaging torn product damaged inside",
        "quality is terrible not what was shown on website",
        "received expired product seal already broken 😡",
        "got wrong flavor. ordered {product} got something else",
        "product broke on first use. total scam",
    ],
    "Subscription Issue": [
        "charged for subscription i cancelled last month wtf",
        "my subscription didnt renew cant access benefits",
        "auto renewed without any notification!!",
        "how do i pause subscription for {n} days?",
        "subscription discount not applying at checkout",
        "how do i cancel my plan?",
        "want to switch from monthly to quarterly plan",
    ],
    "Payment Failure": [
        "payment failed but money got deducted 😤",
        "upi failed but rs {amt} debited. order #{id}",
        "getting payment gateway error every time i try",
        "charged twice for same order #{id}",
        "transaction pending for {n} days is order confirmed?",
        "wallet balance deducted but order not placed",
    ],
    "General Inquiry": [
        "what are your delivery timings?",
        "do you deliver to {city}?",
        "whats your return policy",
        "how long does standard delivery take?",
        "minimum order for free delivery?",
        "do you have loyalty program?",
    ],
}

PRODUCTS = ["protein powder", "whey protein", "creatine", "pre-workout", "multivitamin"]
CITIES   = ["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai", "Hyderabad"]


def fill(text):
    return (text
        .replace("{id}",      str(random.randint(100000, 999999)))
        .replace("{n}",       str(random.randint(2, 12)))
        .replace("{date}",    (datetime.now() - timedelta(days=random.randint(2, 10))).strftime("%d %b"))
        .replace("{amt}",     str(random.randint(200, 3000)))
        .replace("{product}", random.choice(PRODUCTS))
        .replace("{city}",    random.choice(CITIES))
    )


def random_time():
    delta = timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))
    return (datetime.now() - delta).strftime("%Y-%m-%d %H:%M:%S")


def generate(n=200):
    cats, wts = list(CATEGORIES.keys()), list(CATEGORIES.values())
    rows = []
    for i in range(n):
        cat     = random.choices(cats, weights=wts)[0]
        message = fill(random.choice(TEMPLATES[cat]))
        channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
        status  = random.choices(["open", "resolved", "escalated"], weights=[0.55, 0.35, 0.10])[0]
        rows.append({
            "id": 1000 + i, "message": message, "category": cat,
            "channel": channel, "timestamp": random_time(), "status": status,
        })
    rows.sort(key=lambda x: x["timestamp"], reverse=True)
    return rows


def save(rows):
    with open("data/queries.json", "w") as f:
        json.dump(rows, f, indent=2)
    print(f"Saved {len(rows)} queries → data/queries.json")

    conn = sqlite3.connect("data/beastlife.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY, message TEXT, category TEXT,
            channel TEXT, timestamp TEXT, status TEXT DEFAULT 'open',
            confidence REAL, auto_resolved INTEGER DEFAULT 0, ai_provider TEXT
        )
    """)
    conn.executemany(
        "INSERT OR REPLACE INTO queries "
        "VALUES (:id, :message, :category, :channel, :timestamp, :status, NULL, 0, NULL)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Saved {len(rows)} queries → data/beastlife.db")


if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)
    save(generate(200))