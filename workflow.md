# Beastlife — AI Customer Intelligence System
## Workflow & Architecture

---

## System Overview

```
WhatsApp / Instagram DM / Email / Website Chat
                    │
                    ▼
          ┌─────────────────┐
          │  n8n Webhook    │  ← public URL, always listening
          └────────┬────────┘
                   │  POST { message, channel, sender_id }
                   ▼
          ┌─────────────────┐
          │   api.py        │  ← FastAPI orchestrator
          │   /webhook      │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────────────────┐
          │   classifier/categorize.py  │
          │                             │
          │   1. Groq llama-3.3-70b     │  primary
          │      ↓ (if fails)           │
          │   2. OpenAI gpt-4o-mini     │  fallback
          │      ↓ (if fails)           │
          │   3. Rule-based keywords    │  offline
          └────────┬────────────────────┘
                   │
                   ▼
          ┌─────────────────────────────┐
          │      Guardrail Layer        │
          │  ① Sanitize  (injection)   │
          │  ② Validate  (output)      │
          │  ③ Sentiment (angry→esc)   │
          │  ④ Confidence (< 65%→esc)  │
          └────────┬────────────────────┘
                   │
                   ▼
             SQLite Database
                   │
          ┌────────┴────────┐
          │                 │
    auto = true       auto = false
          │                 │
          ▼                 ▼
    Auto-Reply         Escalate
    to customer     to support team
          │                 │
          └────────┬────────┘
                   │
                   ▼
         Streamlit Dashboard
         (real-time insights)
```

---

## 1. Customer Query Categorization

**Channels:** WhatsApp · Instagram DM · Email · Website Chat

All 4 channels send messages to a single n8n webhook endpoint.

### 7 Categories

| Category | % Share | Auto-Resolved |
|---|---|---|
| Order Tracking | 28% | ✅ Yes |
| Delivery Delay | 20% | ❌ No |
| Refund Request | 16% | ❌ No |
| Product Complaint | 14% | ❌ No |
| Subscription Issue | 10% | ✅ Yes |
| Payment Failure | 7% | ❌ No |
| General Inquiry | 5% | ✅ Yes |

### AI Classifier — 3-Tier Fallback

```
classify(message)
      │
      ├─► Groq llama-3.3-70b   ── 90-100% confidence, ~200ms
      │     ↓ fails
      ├─► OpenAI gpt-4o-mini   ── 90-95% confidence, ~600ms
      │     ↓ fails
      └─► Keyword rules         ── ~72% confidence, <5ms, offline
```

### Few-Shot Prompt (improves accuracy)

```
"where is my order #845231?"          → Order Tracking
"my order is 5 days late"             → Delivery Delay
"i want refund for damaged product"   → Refund Request
"subscription auto renewed"           → Subscription Issue
"payment failed but money deducted"   → Payment Failure
"what is your return policy?"         → General Inquiry
```

### 4-Layer Guardrail System

```
① Input Sanitization
   "ignore previous instructions..." → blocked before LLM

② Output Validation
   Unknown category returned → defaulted to General Inquiry

③ Sentiment Detection
   "scam / fraud / cheated / 😡" → auto_resolvable = False

④ Confidence Threshold
   confidence < 0.65 → escalate for safety
```

---

## 2. Problem Distribution Dashboard

**Run:** `streamlit run app.py` → `http://localhost:8501`
**Live:** `beastlife.streamlit.app`

```
┌──────────────────────────────────────────────────┐
│  Total  │  Open  │  Resolved  │  Escalated  │ Auto%│
├─────────────────────┬────────────────────────────┤
│  Issue Distribution │  Queries by Channel        │
│  (Donut — % per cat)│  (Bar — WhatsApp/IG/Email) │
├─────────────────────┼────────────────────────────┤
│  Weekly Trend       │  Status Breakdown          │
│  (Stacked area 90d) │  (Open/Resolved/Escalated) │
├─────────────────────┴────────────────────────────┤
│  Live Classifier  |  Recent Queries Feed          │
├──────────────────────────────────────────────────┤
│  Automation Opportunities (6 cards)              │
└──────────────────────────────────────────────────┘
```

**Example output:**

| Issue Type | % of Queries |
|---|---|
| Order Tracking | 27% |
| Delivery Delay | 18% |
| Product Complaint | 16% |
| Refund Request | 14% |
| Subscription Issue | 9% |
| General Inquiry | 7% |
| Payment Failure | 6% |

---

## 3. Automation Opportunities

**43% of queries auto-resolved. Zero human involvement.**

| Category | Action | Impact |
|---|---|---|
| Order Tracking | Auto-send tracking link | ~35% workload cut |
| General Inquiry | FAQ smart responder | ~100% auto-handled |
| Subscription Issue | Self-service bot | ~70% auto-handled |
| Delivery Delay | Proactive apology + ETA | ~60% query reduction |
| Refund Request | Auto-check eligibility | ~50% faster cycle |
| Payment Failure | Auto-send retry link | ~80% faster resolution |
| Product Complaint | Auto-log → HIGH PRIORITY | Faster routing |

**Escalation payload sent to agent:**
```json
{
  "category":   "Payment Failure",
  "confidence":  0.9,
  "sentiment":  "neutral",
  "action":     "Assign to payments team",
  "message":    "my payment failed but rs 1500 got deducted"
}
```

---

## 4. Tools & Workflow

### Tools Used

| Layer | Tool | Why |
|---|---|---|
| AI Primary | Groq llama-3.3-70b | Fast, free, 90-100% accuracy |
| AI Fallback | OpenAI gpt-4o-mini | Reliable backup |
| AI Offline | Keyword rules | No API dependency |
| API Server | FastAPI + Uvicorn | Async, auto-docs at /docs |
| Automation | n8n | Proven live — both routes tested |
| Database | SQLite → PostgreSQL | Zero-setup, trivially scalable |
| Dashboard | Streamlit + Plotly | Python-native, real-time |

**Why not LangChain?** Direct LLM API calls with structured JSON output are faster and simpler here. LangChain would be added only if RAG-based FAQ retrieval from a knowledge base is needed in v2.

### n8n Workflow

```
Incoming Message (Webhook)
         │
         ▼
HTTP Request → POST /webhook
         │
         ▼
Switch — auto_resolvable?
    │               │
  true            false
    │               │
    ▼               ▼
Auto-Reply      Escalate
(webhook.site)  (webhook.site / email)
```

**Proven live test results:**

| Message | Result |
|---|---|
| "where is my order #845231?" | AUTO-REPLY SENT — Order Tracking, 100% |
| "payment failed rs 1500 deducted" | ESCALATED — Payment Failure, 90% |

---

## 5. Deliverables

| # | Deliverable | File |
|---|---|---|
| 1 | Workflow explanation | `docs/workflow.md` (this file) |
| 2 | Sample dataset — 200 queries | `data/queries.json` |
| 3 | AI categorization logic | `classifier/categorize.py` |
| 4 | Working dashboard | `app.py` → `beastlife.streamlit.app` |
| 5 | Scalability plan | Below |

### Scalability

```
Current     SQLite + single server + n8n free
10K/day  →  PostgreSQL        (change 1 env var, zero code change)
100K/day →  Redis queue + multiple uvicorn workers
1M+/day  →  Kafka + microservices + cloud deployment
```

Classifier is **stateless** — horizontal scaling needs no code changes.
DB layer is **modular** — swap SQLite to PostgreSQL by changing `DB_PATH` in `.env`.

---

*GitHub: github.com/Shau-19/beastlife-customer-intelligence*
*Dashboard: beastlife.streamlit.app*