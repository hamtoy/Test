# 🔌 Frontend-Backend Integration Guide

> This guide explains how to connect the Vite/Vitest-based frontend to the FastAPI backend.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Environment Setup](#environment-setup)
3. [Available API Endpoints](#available-api-endpoints)
4. [CORS Configuration](#cors-configuration)
5. [Development Workflow](#development-workflow)
6. [API Usage Examples](#api-usage-examples)

---

## Overview

The project consists of:

- **Backend**: FastAPI server in `src/web/` (Python)
- **Frontend**: Vite + React/TypeScript in `packages/frontend/`

### Architecture

```
┌─────────────────┐     HTTP/JSON     ┌─────────────────┐
│                 │ ◄───────────────► │                 │
│    Frontend     │                   │    Backend      │
│   (Vite/React)  │                   │   (FastAPI)     │
│                 │                   │                 │
└─────────────────┘                   └─────────────────┘
     Port 5173                             Port 8000
```

---

## Environment Setup

### Backend Environment Variables

Create a `.env` file in the project root:

```bash
# API Server
WEB_HOST=127.0.0.1
WEB_PORT=8000

# CORS (allow frontend origin)
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Gemini API (required)
GEMINI_API_KEY=your_api_key_here

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379

# Optional: Neo4j for RAG
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Frontend Environment Variables

Create `.env` in `packages/frontend/`:

```bash
# API Base URL
VITE_API_BASE_URL=http://localhost:8000

# Optional: Enable debug mode
VITE_DEBUG=true
```

---

## Available API Endpoints

### Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/health/ready` | Readiness probe |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/metrics` | Prometheus metrics |

### OCR Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/ocr` | Get current OCR text |
| `POST` | `/api/ocr` | Save OCR text |

**Request/Response Examples:**

```typescript
// GET /api/ocr
interface OCRGetResponse {
  status: "success" | "not_found";
  text?: string;
  message?: string;
}

// POST /api/ocr
interface OCRPostRequest {
  text: string;
}

interface OCRPostResponse {
  status: "success";
  message: string;
}
```

### Cache Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cache/summary` | Get cache hit/miss stats |

**Response:**

```typescript
interface CacheSummaryResponse {
  status: "ok";
  data: {
    total_entries: number;
    cache_hits: number;
    cache_misses: number;
    hit_rate_percent: number;
    total_tokens: {
      input: number;
      output: number;
      total: number;
    };
    total_cost_usd: number;
  };
}
```

### QA Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/qa/generate` | Generate Q&A pairs |
| `POST` | `/api/qa/evaluate` | Evaluate an answer |
| `GET` | `/api/session` | Get current session info |

### Workspace Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workspace/files` | List workspace files |
| `POST` | `/api/workspace/review` | Review workspace content |

---

## CORS Configuration

### Backend CORS Settings

The backend uses environment-based CORS configuration:

```python
# src/web/api.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins,  # From CORS_ALLOW_ORIGINS env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Recommended Development CORS

```bash
# .env
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Production CORS

```bash
# .env (production)
CORS_ALLOW_ORIGINS=https://your-production-domain.com
```

---

## Development Workflow

### 1. Start Backend Server

```bash
# From project root
uv run python -m uvicorn src.web.api:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start Frontend Dev Server

```bash
# From packages/frontend/
cd packages/frontend
pnpm install  # First time only
pnpm run dev
```

### 3. Access the Application

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs> (Swagger UI)
- **ReDoc**: <http://localhost:8000/redoc>

### Concurrent Development

Use a process manager or run in separate terminals:

```bash
# Terminal 1: Backend
uv run python -m uvicorn src.web.api:app --reload

# Terminal 2: Frontend
cd packages/frontend && pnpm run dev
```

---

## API Usage Examples

### Using Fetch API

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Get OCR Text
async function getOCRText(): Promise<string | null> {
  const response = await fetch(`${API_BASE}/api/ocr`);
  const data = await response.json();
  
  if (data.status === 'success') {
    return data.text;
  }
  return null;
}

// Save OCR Text
async function saveOCRText(text: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/api/ocr`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });
  
  const data = await response.json();
  return data.status === 'success';
}

// Get Cache Statistics
async function getCacheStats() {
  const response = await fetch(`${API_BASE}/api/cache/summary`);
  const data = await response.json();
  return data.data;
}

// Health Check
async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    const data = await response.json();
    return data.status === 'healthy';
  } catch {
    return false;
  }
}
```

### Using Axios

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Get OCR Text
export const getOCRText = async () => {
  const { data } = await api.get('/api/ocr');
  return data;
};

// Save OCR Text
export const saveOCRText = async (text: string) => {
  const { data } = await api.post('/api/ocr', { text });
  return data;
};

// Get Cache Summary
export const getCacheSummary = async () => {
  const { data } = await api.get('/api/cache/summary');
  return data.data;
};
```

### React Query Example

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getOCRText, saveOCRText, getCacheSummary } from './api';

// Hook for OCR text
export function useOCRText() {
  return useQuery({
    queryKey: ['ocr'],
    queryFn: getOCRText,
  });
}

// Hook for saving OCR text
export function useSaveOCR() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: saveOCRText,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ocr'] });
    },
  });
}

// Hook for cache statistics
export function useCacheStats() {
  return useQuery({
    queryKey: ['cache-stats'],
    queryFn: getCacheSummary,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}
```

---

## Error Handling

### Common Error Responses

```typescript
interface ErrorResponse {
  detail: string;
  request_id?: string;
}
```

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Check request body |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Check backend logs |

### Error Handling Example

```typescript
async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  
  return response.json();
}
```

---

## Troubleshooting

### CORS Errors

1. Verify `CORS_ALLOW_ORIGINS` includes your frontend URL
2. Ensure no trailing slash in origins
3. Restart backend after changing `.env`

### Connection Refused

1. Verify backend is running on the expected port
2. Check `VITE_API_BASE_URL` in frontend `.env`
3. Try accessing backend directly in browser

### Request Timeout

1. Check if backend is processing (check logs)
2. Increase timeout in fetch/axios config
3. Consider using WebSocket for long operations

---

## Related Documentation

- [API Reference (Swagger UI)](http://localhost:8000/docs)
- [LATS Guide](./LATS_GUIDE.md)
- [Caching Guide](./CACHING.md)
