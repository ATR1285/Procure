# API Documentation

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://procure-iq.onrender.com` *(To be deployed)*

## Authentication

All API endpoints (except `/` and `/metrics`) require authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/api/invoices
```

## Interactive Documentation

FastAPI provides auto-generated interactive documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Core Endpoints

### System Status

#### GET `/api/ai-health`
**Description**: Check AI services health and usage statistics

**Headers**:
- `X-API-Key`: Your API key

**Response**:
```json
{
  "status": "ok",
  "services": {
    "gemini": "available",
    "openai": "available",
    "ollama": "unavailable"
  },
  "usage": {
    "total_calls": 145,
    "gemini_calls": 120,
    "openai_calls": 25,
    "total_cost_usd": 0.45
  },
  "timestamp": "2026-02-18T00:10:00"
}
```

### Invoices

#### POST `/api/invoices`
**Description**: Submit a new invoice for processing

**Headers**:
- `X-API-Key`: Your API key
- `Content-Type`: application/json

**Request Body**:
```json
{
  "invoice_number": "INV-2024-001",
  "vendor_name": "Acme Corp",
  "amount": 1500.00,
  "invoice_date": "2024-02-15",
  "extracted_data": {
    "items": [
      {"description": "MacBook Pro", "quantity": 1, "price": 1500.00}
    ]
  }
}
```

**Response**:
```json
{
  "id": 1,
  "invoice_number": "INV-2024-001",
  "status": "pending",
  "confidence_score": 92.5,
  "match_method": "gemini",
  "created_at": "2026-02-18T00:10:00"
}
```

#### GET `/api/invoices`
**Description**: List all invoices with optional filtering

**Query Parameters**:
- `status`: Filter by status (pending, approved, rejected, escalated)
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset (default: 0)

**Response**:
```json
{
  "invoices": [
    {
      "id": 1,
      "invoice_number": "INV-2024-001",
      "vendor_name": "Acme Corp",
      "amount": 1500.00,
      "status": "approved",
      "confidence_score": 92.5,
      "created_at": "2026-02-18T00:10:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### GET `/api/invoices/{id}`
**Description**: Get detailed invoice information

**Response**:
```json
{
  "id": 1,
  "invoice_number": "INV-2024-001",
  "vendor": {
    "id": 5,
    "name": "Acme Corporation",
    "aliases": ["Acme Corp", "ACME", "Acme Inc"]
  },
  "amount": 1500.00,
  "status": "approved",
  "confidence_score": 92.5,
  "match_method": "gemini",
  "reasoning": "High confidence vendor match based on historical data",
  "extracted_data": {...},
  "audit_trail": [
    {
      "action": "created",
      "timestamp": "2026-02-18T00:10:00",
      "user": "system"
    },
    {
      "action": "ai_matched",
      "timestamp": "2026-02-18T00:10:05",
      "confidence": 92.5
    },
    {
      "action": "approved",
      "timestamp": "2026-02-18T00:15:00",
      "user": "owner"
    }
  ]
}
```

### Owner Actions

#### POST `/api/owner/approve-invoice/{id}`
**Description**: Manually approve an invoice

**Response**:
```json
{
  "status": "approved",
  "message": "Invoice INV-2024-001 approved successfully"
}
```

#### POST `/api/owner/reject-invoice/{id}`
**Description**: Reject an invoice

**Request Body**:
```json
{
  "reason": "Incorrect pricing"
}
```

**Response**:
```json
{
  "status": "rejected",
  "message": "Invoice INV-2024-001 rejected"
}
```

### Analytics

#### GET `/api/analytics/summary`
**Description**: Get procurement analytics dashboard data

**Response**:
```json
{
  "total_invoices": 145,
  "auto_approved": 120,
  "pending_review": 15,
  "rejected": 10,
  "avg_confidence": 89.5,
  "total_spent": 45000.00,
  "ai_usage": {
    "total_calls": 145,
    "cost_usd": 0.45
  },
  "inventory_alerts": 3
}
```

### Simulation (Testing)

#### POST `/api/simulate-email`
**Description**: Trigger email processing simulation for testing

**Response**:
```json
{
  "message": "Email simulation triggered",
  "event_id": 42
}
```

#### POST `/api/simulate-stock-alert`
**Description**: Trigger inventory alert simulation

**Response**:
```json
{
  "message": "Stock alert simulation triggered",
  "items_below_threshold": 2
}
```

## Approval Routes (Public)

These endpoints use token-based authentication (no API key required).

#### POST `/api/approval/approve/{token}`
**Description**: Approve invoice via email link

**Response**:
```json
{
  "status": "approved",
  "invoice_number": "INV-2024-001"
}
```

#### POST `/api/approval/reject/{token}`
**Description**: Reject invoice via email link

**Response**:
```json
{
  "status": "rejected",
  "invoice_number": "INV-2024-001"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid invoice data: amount must be positive"
}
```

### 401 Unauthorized
```json
{
  "detail": "Invalid or missing API key. Include X-API-Key header."
}
```

### 404 Not Found
```json
{
  "detail": "Invoice with ID 999 not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "AI service temporarily unavailable. Falling back to fuzzy matching."
}
```

## Rate Limiting

- **Development**: No rate limits
- **Production**: 100 requests/minute per API key

## Webhooks (Future Feature)

Subscribe to events:
- `invoice.created`
- `invoice.approved`
- `invoice.rejected`
- `inventory.low_stock`

## Client Libraries

### Python
```python
import requests

API_KEY = "your_api_key"
BASE_URL = "http://localhost:8000"

headers = {"X-API-Key": API_KEY}

# Create invoice
response = requests.post(
    f"{BASE_URL}/api/invoices",
    json={
        "invoice_number": "INV-001",
        "vendor_name": "Acme Corp",
        "amount": 1500.00
    },
    headers=headers
)
print(response.json())
```

### JavaScript
```javascript
const API_KEY = "your_api_key";
const BASE_URL = "http://localhost:8000";

fetch(`${BASE_URL}/api/invoices`, {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    invoice_number: "INV-001",
    vendor_name: "Acme Corp",
    amount: 1500.00
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

## Support

For API support:
- **GitHub Issues**: [https://github.com/ATR1285/Procure/issues](https://github.com/ATR1285/Procure/issues)
- **Documentation**: See `/docs` in the repository
