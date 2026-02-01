# 🗄️ PDF Tools Database System

## Overview

The PDF Tools Suite now includes a **SQLite database** that automatically tracks all uploaded files with:

- ✅ **File metadata storage** (name, size, upload time, expiry time)
- ✅ **Automatic 1-hour expiry** with background cleanup
- ✅ **Upload dashboard** to view all files
- ✅ **Manual file deletion** option
- ✅ **REST API** to query uploaded files

---

## 🚀 Quick Start

### 1. Run the Database-Enabled Server

```bash
python backend/app_with_db.py
```

### 2. Access the Dashboard

- **Tools Page**: http://127.0.0.1:5000/tools
- **Uploads Dashboard**: http://127.0.0.1:5000/uploads
- **API Endpoint**: http://127.0.0.1:5000/api/uploads

---

## 📊 Database Structure

### SQLite Database Location
```
data/pdf_tools.db
```

### UploadedFile Table Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (UUID) | Unique file identifier |
| `filename` | String | System filename (UUID + original) |
| `original_filename` | String | Original user-provided filename |
| `file_path` | String | Full path to uploaded file |
| `file_size` | Integer | File size in bytes |
| `mime_type` | String | MIME type (e.g., application/pdf) |
| `uploaded_at` | DateTime | Upload timestamp |
| `expires_at` | DateTime | Automatic deletion time (now + 1 hour) |
| `is_deleted` | Boolean | Soft delete flag |

---

## 🌐 API Endpoints

### Get All Uploaded Files
```
GET /api/uploads
```

**Response:**
```json
{
  "success": true,
  "total_files": 3,
  "files": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "document.pdf",
      "file_size": "2.45 MB",
      "file_size_bytes": 2568123,
      "uploaded_at": "2026-02-01 14:30:00",
      "expires_at": "2026-02-01 15:30:00",
      "time_remaining": "45m",
      "mime_type": "application/pdf"
    }
  ]
}
```

### Delete a Specific File
```
DELETE /api/file/<file_id>
```

**Response:**
```json
{
  "success": true,
  "message": "File deleted"
}
```

### Manually Trigger Cleanup
```
POST /api/cleanup-expired
```

**Response:**
```json
{
  "success": true,
  "message": "Cleanup triggered"
}
```

---

## 📱 Uploads Dashboard Features

The `/uploads` page provides:

### File Listing
- **Name**: Original filename
- **Size**: Human-readable file size
- **Uploaded At**: Upload timestamp
- **Expires In**: Time remaining before auto-deletion
- **Action**: Manual delete button

### Color-Coded Expiry Times
- **Green** (Safe): More than 15 minutes remaining
- **Yellow** (Warning): Less than 15 minutes remaining
- **Red** (Danger): File expired

### Auto-Refresh
- Dashboard auto-refreshes every 30 seconds
- Shows real-time countdown for expiry times
- Updates file count automatically

---

## ⚙️ Background Cleanup System

### How It Works

1. **Thread-Based Cleanup**
   - Runs in background every 60 seconds
   - Doesn't block main application

2. **Deletion Process**
   - Checks for expired files
   - Deletes from filesystem
   - Marks as deleted in database (soft delete)

3. **Zero Data Loss**
   - Soft deletes preserve data for auditing
   - `is_deleted` flag prevents data loss
   - Can be modified to permanent delete if needed

### Cleanup Configuration

Edit in `app_with_db.py`:

```python
cleanup_manager = DatabaseCleanupManager(expiry_hours=1)  # Change expiry time
cleanup_manager.start_background_cleanup(interval=60)     # Change check interval
```

---

## 📝 File Storage

### Upload Directory Structure

```
frontend/
├── temp_uploads/           # Uploaded files stored here
│   ├── 550e8400-xxxx_document.pdf
│   ├── 661f9511-yyyy_image.png
│   └── 772g0622-zzzz_spreadsheet.xlsx
└── ...
```

### Filename Convention

Files are stored with unique names to prevent conflicts:

```
{UUID}_{original_filename}
```

Example: `550e8400-e29b-41d4-a716-446655440000_report.pdf`

---

## 🔍 Monitoring & Debugging

### View Active Sessions

```bash
# Check database contents
sqlite3 data/pdf_tools.db
```

```sql
-- View all non-deleted files
SELECT original_filename, file_size, uploaded_at, expires_at 
FROM uploaded_files 
WHERE is_deleted = FALSE;

-- Count files by status
SELECT COUNT(*), is_deleted 
FROM uploaded_files 
GROUP BY is_deleted;

-- Files expiring soon
SELECT original_filename, expires_at 
FROM uploaded_files 
WHERE is_deleted = FALSE 
AND expires_at < datetime('now', '+15 minutes');
```

### Server Logs

Watch for database operations:

```
✅ Database-backed file cleanup started (runs every 60 seconds)
🗑️ Deleted expired file: document.pdf
```

---

## 🛡️ Security Features

### 1. Unique Identifiers
- UUID prevents file enumeration
- Unpredictable filenames

### 2. Automatic Expiry
- 1-hour retention by default
- Automatic cleanup prevents disk bloat

### 3. Soft Deletes
- Marks as deleted instead of removing
- Preserves audit trail

### 4. Database Isolation
- SQLite local database
- No external dependencies

---

## 🐛 Troubleshooting

### Issue: Database Lock Error
**Cause**: Multiple processes accessing database

**Solution**:
```bash
# Rebuild the database
rm data/pdf_tools.db
# Restart the server
python backend/app_with_db.py
```

### Issue: Files Not Deleting
**Cause**: Cleanup thread not running

**Solution**:
```bash
# Check server logs for errors
# Manually trigger cleanup
curl -X POST http://127.0.0.1:5000/api/cleanup-expired
```

### Issue: Uploads Page Shows Empty
**Cause**: No files uploaded yet or wrong database path

**Solution**:
```bash
# Check database exists
ls -la data/pdf_tools.db
# Upload a file using tools page
```

---

## 📦 Dependencies

All database dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages:
- `flask-sqlalchemy` - Database ORM
- `sqlalchemy` - SQL toolkit
- `sqlite3` - Built-in, no install needed

---

## 🚀 Future Enhancements

Potential improvements:

1. **PostgreSQL Support**
   - Replace SQLite for production
   - Multiple concurrent users

2. **File Recovery**
   - 7-day recovery window
   - "Trash" page for recently deleted files

3. **User Accounts**
   - Track files per user
   - User quotas

4. **Advanced Search**
   - Search by filename, size, date
   - Filter by file type

5. **Audit Logging**
   - Track all operations
   - Compliance reporting

---

## 📞 Support

For issues or questions:
1. Check server logs
2. Run cleanup manually
3. Reset database if needed
4. Check file permissions on temp_uploads folder

---

**Happy file uploading! 📄**
