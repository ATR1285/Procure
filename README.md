# ProcureIQ - AI-Powered Invoice Matching System

Production-grade invoice processing system with Ollama AI, Odoo ERP integration, and three-way matching.

## Features

- **Local AI**: Ollama integration for vendor name matching and reasoning
- **ERP Integration**: Real-time Odoo Community Edition connection via JSON-RPC
- **Three-Way Matching**: Invoice + Purchase Order + Goods Receipt verification
- **Fuzzy Matching**: Fuse.js fallback when AI is unavailable
- **Alias Learning**: Auto-learns vendor name variations on approval
- **SQLite Database**: Zero-setup local storage
- **Live Accuracy**: Real-time accuracy rate calculation from decisions

## Tech Stack

- **Frontend**: React + TypeScript + Wouter
- **Backend**: Express + TypeScript + Drizzle ORM
- **Database**: SQLite (better-sqlite3)
- **LLM**: Ollama (llama3.1:8b) via OpenAI SDK
- **ERP**: Odoo Community 17 via JSON-RPC
- **Fuzzy Match**: Fuse.js

## Quick Start

### Prerequisites

- Node.js 20+
- Ollama installed and running (`ollama serve`)
- Odoo Community Edition (optional - runs in fallback mode without it)

### Installation

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Start Odoo (optional - runs in fallback mode without it)
docker-compose up -d

# Pull Ollama model
ollama pull llama3.1:8b

# Initialize database
npx drizzle-kit push

# Start development server
npm run dev
```

### Environment Variables

Required in `.env`:
```
ODOO_URL=http://localhost:8069
ODOO_DB=odoo
ODOO_USER=admin
ODOO_PASSWORD=admin
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1:8b
```

## Database Schema

### Vendors
- Canonical names + JSON array of aliases
- Contact email
- Active status

### Invoices
- Invoice number, amount, date
- Linked vendor ID
- Status (pending/approved/rejected/escalated)
- Confidence score
- Extracted data (JSON)

### Matches
- Invoice → Odoo PO mapping
- Match method (ollama/fuse-fuzzy/manual)
- Decision tracking

### Goods Receipts
- Odoo PO ID
- Receipt details (date, quantity, amount)
- Received by

## Architecture

```
client/          # React frontend
server/          # Express API
  db.ts          # SQLite connection
  storage.ts     # Data access layer
  odoo-client.ts # Odoo JSON-RPC client
  ollama-service.ts # AI analysis
  routes.ts      # API endpoints
shared/          # Shared TypeScript types
  schema.ts      # Drizzle schema
```

## Confidence Scoring

Weighted three-way match:
- **50%** Vendor match confidence (from Ollama)
- **35%** PO amount match (±5% tolerance)
- **15%** Goods receipt exists

**≥85%** → Auto-approved  
**60-84%** → Pending review  
**<60%** → Escalated

## Fallback Strategy

1. **Ollama unavailable** → Fuse.js fuzzy matching
2. **Odoo offline** → Local vendor database
3. **Both offline** → Manual escalation

## Demo Flow

1. Trigger invoice: "Acme Supplies Ltd" → 94% confidence → auto-approved
2. Trigger invoice: "GLOBALTECH PVT" → 71% → pending
3. Approve pending → alias learned
4. Re-trigger "GLOBALTECH PVT" → 95% → auto-approved (alias matched)

## Production Checklist

- [ ] Set strong Odoo credentials
- [ ] Enable HTTPS for Odoo
- [ ] Configure Ollama API authentication
- [ ] Set up automated backups (SQLite file)
- [ ] Monitor accuracy rate trends
- [ ] Review escalated invoices daily

## License

MIT
