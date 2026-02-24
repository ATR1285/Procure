# Procure-IQ 🤖
### Autonomous Procurement + Decision Intelligence Engine

> An AI-powered system that monitors your Gmail inbox, detects invoices, manages inventory, automates purchase approvals, and provides real-time decision intelligence with system operating modes — end to end, with minimal human intervention.

---

## ✨ Features

### 🧠 AI-Powered Invoice Detection
- **LangChain + Gemini 1.5 Flash** classifies every email as invoice or not (temperature=0.0, max_tokens=512)
- Extracts: vendor name, amount, invoice number, dates, currency — structured JSON output
- **PDF attachment parsing** via `pdfplumber` (first 5 pages)
- Confidence score on every result

### 📬 Gmail Inbox Agent
- Background agent polls **Inbox + Spam** every 60 seconds (configurable via `GMAIL_POLL_INTERVAL`)
- **Auto OAuth token refresh** — no manual re-auth needed
- Smart deduplication: by Gmail message ID *and* by subject+sender (catches forwarded emails)
- All discovered invoices stored in `gmail_invoices` DB table with full audit trail

### 📦 Dedicated Inventory Management
- **ERP-style Inventory Page** (`/inventory`) with 100+ seeded items across 6 categories
- Summary cards: Total Products, Low Stock, Out of Stock, Inventory Value (INR)
- Real-time search by SKU or product name
- Category & status filters with paginated data table
- Stock monitoring agent triggers low-stock alerts automatically
- Sends approval request to owner via **Email + SMS + WhatsApp** (Twilio)

### 🎯 Decision Intelligence Layer
- **System Operating Modes**: Debate (normal), Crisis (high severity), Safe (low AI confidence)
- **Severity Scoring Engine** (0–10) based on stock levels, supplier status, and AI confidence
- **Safe Mode**: Automatically forces invoices to `MANUAL_REVIEW` when AI confidence drops below 60%
- **Real-time Dashboard Bar**: Color-coded mode indicator with severity gauge
- Pure extension layer — removable without affecting core system

### ✅ Approval Workflow
- Owner receives an email with a one-click Approve link
- On approval → purchase order email sent automatically to supplier
- Confirmation email sent back to owner
- Full audit trail logged per invoice

### 📊 Analytics Dashboard
- Spend by vendor with progress bars
- Approval rate, total approved spend, weekly invoice volume
- Real-time agent health status (Gmail agent + Inventory agent)
- Decision Intelligence bar with mode subtitle, color-scaled severity (green/orange/red), and "Normal Operations" baseline
- Polished empty states: invoice scanner with last-scan timestamp, "No invoice data yet" analytics captions
- 🧪 Test Invoice button to inject fake invoices for E2E testing

### 🛡️ Security
- Google OAuth2 login (session-based)
- API key authentication on all endpoints
- Rate limiting via `slowapi` (5 req/min on sensitive endpoints)
- Configurable allowed users list

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Gmail Agent  │  │  Inventory   │  │  Procurement     │  │
│  │ (60s poll)   │  │  Agent       │  │  Agent (Matcher) │  │
│  │              │  │  (30s poll)  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│  ┌──────▼─────────────────▼────────────────────▼──────────┐ │
│  │            Decision Intelligence Layer                  │ │
│  │   Severity Engine → SystemState → Mode (D/C/S)         │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼───────────────────────────────┐ │
│  │              SQLite Database                            │ │
│  │  gmail_invoices │ inventory │ alerts │ system_state     │ │
│  │  vendors │ users │ events │ invoices                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LangChain + Gemini 1.5 Flash (AI Brain)            │    │
│  │  temp=0.0  max_tokens=512  structured_output=True   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/your-repo/procure-iq.git
cd procure_iq_backend
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

### 3. Set Up Gmail OAuth
Run the one-time auth setup to get your refresh token:
```bash
python gmail_auth_setup.py
```
Copy the `GMAIL_REFRESH_TOKEN` printed to your `.env`.

### 4. Seed Inventory Data
```bash
python seed_inventory.py
```
Generates 100+ realistic ERP-style inventory records across 6 categories.

### 5. Run the Server
```bash
python run.py
```
Open **http://localhost:8888** — agents start automatically.

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `GMAIL_CLIENT_ID` | ✅ | Gmail OAuth client ID |
| `GMAIL_CLIENT_SECRET` | ✅ | Gmail OAuth client secret |
| `GMAIL_REFRESH_TOKEN` | ✅ | Gmail OAuth refresh token |
| `GOOGLE_CLIENT_ID` | ✅ | Google Sign-In client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google Sign-In client secret |
| `SECRET_KEY` | ✅ | Session encryption key |
| `API_KEY` | ✅ | API authentication key |
| `OWNER_EMAIL` | ✅ | Owner email for alerts |
| `OWNER_PHONE` | ⭐ | Owner phone for SMS/WhatsApp (E.164 format) |
| `SUPPLIER_EMAIL` | ⭐ | Default supplier email |
| `TWILIO_ACCOUNT_SID` | ⭐ | Twilio account SID (for SMS/WhatsApp) |
| `TWILIO_AUTH_TOKEN` | ⭐ | Twilio auth token |
| `TWILIO_FROM_NUMBER` | ⭐ | Twilio phone number |
| `GMAIL_POLL_INTERVAL` | — | Seconds between inbox scans (default: `60`) |
| `INVOICE_APPROVAL_THRESHOLD` | — | Invoice amount requiring human approval (default: `1000`) |
| `DATABASE_URL` | — | Database URL (default: `sqlite:///./procure_iq.db`) |
| `PORT` | — | Server port (default: `8888`) |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard (protected) |
| `GET` | `/inventory` | ERP-style Inventory page |
| `GET` | `/settings` | Settings page |
| `GET` | `/api/inventory` | Paginated inventory (search, filter, pagination) |
| `GET` | `/api/inventory/summary` | Inventory summary cards |
| `GET` | `/api/system-state` | Decision Intelligence state (mode + severity) |
| `GET` | `/api/gmail-invoices` | List AI-detected Gmail invoices |
| `PATCH` | `/api/gmail-invoices/{id}/status` | Approve or reject an invoice |
| `GET` | `/api/analytics` | Spend analytics (vendor breakdown, rates) |
| `GET` | `/api/agent-status` | Live health of all background agents |
| `POST` | `/api/test/inject-invoice` | Inject a test invoice (rate limited: 5/min) |
| `GET` | `/api/alerts` | Active low-stock alerts |
| `POST` | `/api/owner/approve-refill/{id}` | Approve a restock order |
| `GET` | `/api/erp/current` | Current ERP connection status |
| `GET` | `/api/ai-status` | AI engine status |
| `GET` | `/auth/login` | Google OAuth login |
| `GET` | `/auth/callback` | OAuth callback |
| `GET` | `/metrics` | Prometheus metrics |

---

## 🗂️ Project Structure

```
Procure-IQ/
├── app/
│   ├── agent/
│   │   ├── ai_client.py            # Gemini + GPT-4o AI brain
│   │   ├── matcher.py              # Vendor matching, 3-way match + Safe Mode
│   │   ├── inventory_manager.py    # Inventory management logic
│   │   └── worker.py               # Autonomous agent loop + Decision Intel hook
│   ├── api/
│   │   ├── owner_actions.py        # Inventory, system-state, approval endpoints
│   │   ├── approval_routes.py      # Owner approval endpoints
│   │   ├── invoices.py             # Invoice API
│   │   └── ...
│   ├── services/
│   │   ├── severity_engine.py      # Decision Intelligence severity calculator
│   │   ├── ai_extractor.py         # LangChain + Gemini invoice extraction
│   │   ├── email_service.py        # Gmail email ingestion
│   │   ├── python_erp.py           # ERP adapter
│   │   ├── alert_service.py        # Email + SMS + WhatsApp alerts
│   │   └── token_refresh.py        # Auto OAuth token refresh
│   ├── templates/
│   │   ├── index.html              # Main dashboard + Decision Intel bar
│   │   ├── inventory.html          # ERP-style inventory page
│   │   └── settings.html           # Settings page
│   ├── models.py                   # SQLAlchemy models (incl. SystemState)
│   ├── main.py                     # FastAPI app + all routes
│   ├── auth.py                     # Google OAuth login
│   └── database.py
├── seed_inventory.py               # Inventory data seeder (100+ items)
├── gmail_auth_setup.py             # One-time Gmail OAuth setup
├── config.py                       # Centralized settings
├── requirements.txt
├── run.py                          # Server entrypoint
├── .env.example                    # Environment variable template
├── docker-compose.yml
└── nixpacks.toml                   # Railway deployment config
```

---

## 🎯 Decision Intelligence Modes

| Mode | Trigger | Effect |
|---|---|---|
| 🟢 **Debate** | Severity 0–6 | Normal operation, AI processes invoices automatically |
| 🔴 **Crisis** | Severity 7–10 | High alert — stock critically low or supplier unavailable |
| ⚫ **Safe** | AI confidence < 60% | Auto-approval disabled, invoices forced to manual review |

### Severity Scoring

| Condition | Score |
|---|---|
| Stock > reorder level | 2 |
| Stock ≤ reorder level | 6 |
| Stock = 0 (out of stock) | 9 |
| Supplier unavailable | +2 |
| *Capped at 10* | |

---

## 🐳 Docker

```bash
docker-compose up --build
```

---

## 🚢 Deploy to Railway

1. Push to GitHub
2. Connect repo in [Railway](https://railway.app)
3. Add all environment variables from the table above
4. Railway auto-detects `nixpacks.toml` — no additional config needed

---

## 🧪 Testing

Click the **🧪 Test Invoice** button on the dashboard to inject a fake invoice and verify the full pipeline without needing a real email.

Or via API:
```bash
curl -X POST http://localhost:8888/api/test/inject-invoice \
  -H "X-API-Key: your-api-key"
```

---

## 📄 License

MIT
