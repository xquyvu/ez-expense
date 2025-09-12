# Phase 2 Backend API Documentation

## Overview

The EZ Expense Flask application provides a comprehensive RESTful API for managing expenses and receipts. All endpoints return JSON responses with consistent structure.

## Base URL
```
http://localhost:5001
```

## Response Format

All successful responses follow this structure:
```json
{
  "success": true,
  "message": "Description of the operation",
  "data": [...], // Optional data payload
  "count": 0     // Optional count of items
}
```

Error responses:
```json
{
  "error": "Error type",
  "message": "Detailed error description"
}
```

## Health Check

### GET /health
Check if the application is running.

**Response:**
```json
{
  "status": "healthy",
  "message": "EZ Expense app is running"
}
```

## Expense Endpoints

### POST /api/expenses/import
Import expenses from external website using the existing `expense_importer.py` module.

**Response:**
```json
{
  "success": true,
  "message": "Successfully imported 2 expenses",
  "data": [
    {
      "id": 1,
      "Created ID": 1,
      "Amount": 100.0,
      "Description": "Office Supplies"
    }
  ],
  "count": 2
}
```

### POST /api/expenses/mock
Get mock expense data for testing purposes.

**Response:**
```json
{
  "success": true,
  "message": "Mock data loaded with 3 expenses",
  "data": [
    {
      "id": 1,
      "Created ID": 1,
      "Amount": 45.99,
      "Description": "Office Supplies",
      "date": "2024-01-15",
      "category": "Office"
    }
  ],
  "count": 3
}
```

### POST /api/expenses/upload-csv
Upload and parse a CSV file containing expense data.

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `file` (CSV file)

**Response:**
```json
{
  "success": true,
  "message": "Successfully uploaded and parsed 2 expenses from CSV",
  "data": [
    {
      "id": 1,
      "Amount": "45.99",
      "Description": "Office Supplies",
      "Date": "2024-01-15"
    }
  ],
  "count": 2,
  "columns": ["id", "Amount", "Description", "Date"]
}
```

### POST /api/expenses/match-receipt
Calculate confidence score for expense-receipt matching.

**Request:**
```json
{
  "expense_data": {
    "id": 1,
    "Amount": 45.99,
    "Description": "Office Supplies"
  },
  "receipt_path": "/path/to/receipt.png"
}
```

**Response:**
```json
{
  "success": true,
  "confidence_score": 0.85,
  "expense_id": 1,
  "receipt_path": "/path/to/receipt.png",
  "message": "Match confidence calculated: 85.00%"
}
```

### POST /api/expenses/export
Export finalized expenses with receipt information to CSV.

**Request:**
```json
{
  "expenses": [
    {
      "id": 1,
      "Amount": 45.99,
      "Description": "Office Supplies",
      "receipt_path": "receipt1.png"
    }
  ],
  "filename": "exported_expenses.csv"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully exported 2 expenses",
  "export_info": {
    "filename": "exported_expenses_20240101_120000.csv",
    "file_path": "/path/to/export/file.csv",
    "file_size": 1024,
    "expense_count": 2
  }
}
```

### GET /api/expenses/list
Get a list of all stored expenses (placeholder endpoint).

**Response:**
```json
{
  "success": true,
  "message": "No stored expenses found",
  "data": [],
  "count": 0
}
```

## Receipt Endpoints

### POST /api/receipts/upload
Upload a receipt file (PDF, PNG, JPG, JPEG, GIF).

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `file` (receipt file)
- Form field: `expense_id` (optional, expense ID this receipt belongs to)

**Response:**
```json
{
  "success": true,
  "message": "Receipt uploaded successfully",
  "file_info": {
    "original_filename": "receipt.png",
    "saved_filename": "receipt_20240101_120000.png",
    "file_path": "/path/to/uploads/receipt_20240101_120000.png",
    "file_size": 2048,
    "file_type": ".png"
  },
  "expense_id": "1"
}
```

### GET /api/receipts/list
Get a list of all uploaded receipt files.

**Response:**
```json
{
  "success": true,
  "message": "Found 3 receipt files",
  "receipts": [
    {
      "filename": "receipt_20240101_120000.png",
      "file_path": "/path/to/uploads/receipt_20240101_120000.png",
      "file_size": 2048,
      "file_type": "png"
    }
  ],
  "count": 3
}
```

### GET /api/receipts/download/{filename}
Download a specific receipt file.

**Parameters:**
- `filename`: Name of the file to download

**Response:**
- File download (attachment)

### GET /api/receipts/preview/{filename}
Preview a specific receipt file.

**Parameters:**
- `filename`: Name of the file to preview

**Response:**
- File content for display

### DELETE /api/receipts/delete/{filename}
Delete a specific receipt file.

**Parameters:**
- `filename`: Name of the file to delete

**Response:**
```json
{
  "success": true,
  "message": "Receipt 'filename.png' deleted successfully",
  "filename": "filename.png"
}
```

## Error Codes

- `400 Bad Request`: Invalid input data or missing required fields
- `404 Not Found`: Requested resource does not exist
- `413 Request Entity Too Large`: File size exceeds maximum limit (16MB)
- `500 Internal Server Error`: Server-side error

## File Upload Constraints

- **Maximum file size**: 16MB
- **Allowed receipt formats**: PDF, PNG, JPG, JPEG, GIF
- **Allowed CSV formats**: CSV files with UTF-8 encoding
- **Upload directory**: `front_end/uploads/`
- **Export directory**: `front_end/uploads/exports/`

## Integration Points

### expense_importer.py
- Function: `import_expense()` → Returns pandas DataFrame
- Used by: `/api/expenses/import`

### expense_matcher.py
- Function: `receipt_match_score()` → Returns float confidence score
- Used by: `/api/expenses/match-receipt`

## Phase 2 Completion Status

✅ **Task 2.1**: Flask application entry point (`app.py`)
✅ **Task 2.2**: Expense import endpoint (`/api/expenses/import`)
✅ **Task 2.3**: CSV file upload and parsing endpoint (`/api/expenses/upload-csv`)
✅ **Task 2.4**: Receipt file upload endpoint (`/api/receipts/upload`)
✅ **Task 2.5**: Receipt matching endpoint (`/api/expenses/match-receipt`)
✅ **Task 2.6**: Expense export endpoint (`/api/expenses/export`)

## Additional Features Implemented

- Comprehensive error handling and validation
- File type and size restrictions
- Unique filename generation to prevent conflicts
- Separate receipt management endpoints
- File download and preview capabilities
- Logging for debugging and monitoring
- CORS support for frontend integration
- Modular route organization with blueprints

## Testing

A comprehensive test suite is available at:
```
front_end/tests/test_phase2_backend_fixed.py
```

Run tests with:
```bash
cd front_end
python tests/test_phase2_backend_fixed.py
```

## Running the Application

```bash
cd front_end
python app.py
```

The application will start on `http://localhost:5001`
