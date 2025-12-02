# Unified Workspace Workflow Documentation

## Overview

The unified workspace provides automatic workflow detection based on the combination of inputs provided (query, answer, edit_request). This allows for a flexible and intelligent workflow system that adapts to user needs.

## Workflow Detection Logic

The `detect_workflow()` function automatically determines the appropriate workflow based on the presence or absence of:
- **Query**: The question/query text
- **Answer**: The answer/response text
- **Edit Request**: Instructions for modifying content

## Workflow Matrix

| Query | Answer | Edit Request | Workflow | Action |
|-------|--------|--------------|----------|--------|
| ✗ | ✗ | ✗ | `full_generation` | Generate both query and answer from OCR |
| ✗ | ✓ | ✗ | `query_generation` | Generate query from answer |
| ✓ | ✗ | ✗ | `answer_generation` | Generate answer from query |
| ✓ | ✓ | ✗ | `rewrite` | Review/rewrite existing Q&A pair |
| ✓ | ✗ | ✓ | `edit_query` | Edit the query based on instructions |
| ✗ | ✓ | ✓ | `edit_answer` | Edit the answer based on instructions |
| ✓ | ✓ | ✓ | `edit_both` | Edit both query and answer |

## Workflow Labels

Frontend labels for each workflow type:

- `full_generation`: 🎯 전체 생성
- `query_generation`: ❓ 질의 생성
- `answer_generation`: 💡 답변 생성
- `edit_query`: ✏️ 질의 수정
- `edit_answer`: ✏️ 답변 수정
- `edit_both`: ✏️ 질의+답변 수정
- `rewrite`: ✅ 재작성/검수

## API Endpoint

### POST `/api/workspace/unified`

Unified workspace endpoint that automatically detects and executes the appropriate workflow.

**Request Body:**
```json
{
  "query": "Optional query text",
  "answer": "Optional answer text",
  "edit_request": "Optional edit instructions",
  "ocr_text": "Optional OCR text (loads from file if not provided)"
}
```

**Response:**
```json
{
  "workflow": "detected_workflow_type",
  "query": "Final query text",
  "answer": "Final answer text",
  "changes": ["List of changes applied"]
}
```

## Usage Examples

### 1. Full Generation
Generate both query and answer from OCR text:
```json
{
  "query": "",
  "answer": "",
  "edit_request": ""
}
```

### 2. Query Generation
Generate a query from existing answer:
```json
{
  "query": "",
  "answer": "2024년 매출액은 100억원입니다.",
  "edit_request": ""
}
```

### 3. Answer Generation
Generate an answer from a query:
```json
{
  "query": "2024년 매출액은?",
  "answer": "",
  "edit_request": ""
}
```

### 4. Edit Query
Edit/refine an existing query:
```json
{
  "query": "2024년 매출액은?",
  "answer": "",
  "edit_request": "더 구체적으로"
}
```
Result: "2024년 1분기부터 4분기까지의 분기별 매출액은 각각 얼마인가?"

### 5. Edit Answer
Edit/refine an existing answer:
```json
{
  "query": "",
  "answer": "2024년 매출액은 100억원입니다.",
  "edit_request": "숫자 강조"
}
```
Result: "2024년 매출액은 **100억원**입니다."

### 6. Edit Both
Edit both query and answer together:
```json
{
  "query": "작년 실적?",
  "answer": "좋았습니다",
  "edit_request": "구체적인 수치 포함"
}
```
Result:
- Query: "2024년 연간 실적은?"
- Answer: "2024년 연간 매출 100억원, 영업이익 20억원을 달성했습니다."

### 7. Rewrite/Review
Review and refine existing Q&A pair:
```json
{
  "query": "2024년 매출액은?",
  "answer": "2024년 매출액은 100억원입니다.",
  "edit_request": ""
}
```

## Implementation Details

### Backend (Python)

The workflow detection is implemented in `src/web/api.py`:

```python
def detect_workflow(query: Optional[str], answer: Optional[str], 
                    edit_request: Optional[str]) -> str:
    """Detect workflow based on input combination."""
    has_query = bool(query and query.strip())
    has_answer = bool(answer and answer.strip())
    has_edit = bool(edit_request and edit_request.strip())
    
    # Detection logic...
    # See src/web/api.py for full implementation
```

### Frontend (JavaScript)

The workflow labels are displayed using the `getWorkflowLabel()` function in `static/app.js`:

```javascript
function getWorkflowLabel(workflow) {
    const labels = {
        'full_generation': '🎯 전체 생성',
        'query_generation': '❓ 질의 생성',
        'answer_generation': '💡 답변 생성',
        'edit_query': '✏️ 질의 수정',
        'edit_answer': '✏️ 답변 수정',
        'edit_both': '✏️ 질의+답변 수정',
        'rewrite': '✅ 재작성/검수'
    };
    return labels[workflow] || workflow;
}
```

## Testing

Comprehensive tests are available in `tests/unit/web/test_unified_workspace.py`:

- Tests for all 7 workflow detection scenarios
- Tests for the unified workspace API endpoint
- Tests for error handling and edge cases

Run tests with:
```bash
pytest tests/unit/web/test_unified_workspace.py -v
```

## Benefits

1. **Flexibility**: Single endpoint handles all workflow combinations
2. **Automatic Detection**: No need to manually specify workflow type
3. **Extensibility**: Easy to add new workflow types
4. **Type Safety**: Full type checking with mypy
5. **Test Coverage**: Comprehensive test suite ensures reliability
