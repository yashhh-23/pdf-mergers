# 📄 PDF Merger & Sorter with Preview & Rotation

A Flask-based web application to merge multiple PDFs with preview and orientation controls.

## ✨ Features

- 📤 **Upload up to 10 PDFs** (any size)
- 🔄 **Drag-and-drop reordering** or use Up/Down buttons
- 👁️ **Preview PDFs** before merging (first page preview)
- ↻ **Rotate PDFs** (90°, 180°, 270°) before merging
- 📥 **Download merged PDF** to your local machine
- 🎨 **Modern, responsive UI**
- 🔒 **Secure** - Files processed in memory, not saved on server

## 🚀 Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the application:**
```bash
python app.py
```

3. **Open in browser:**
```
http://localhost:5000
```

## 📖 How to Use

### Step 1: Upload PDFs
- Click the upload area or drag & drop up to 10 PDF files
- Only PDF files are accepted

### Step 2: Arrange & Configure
- **Reorder files**: Drag items or use ↑ Up / ↓ Down buttons
- **Preview**: Click 👁️ Preview to see the first page of any PDF
- **Rotate**: Click ↻ Rotate to rotate PDF 90° clockwise (repeatable)
  - 0° → 90° → 180° → 270° → 0°
  - Rotation indicator shows current angle
- **Remove**: Remove unwanted files

### Step 3: Merge & Download
- Click "Merge & Download PDF"
- Merged PDF downloads automatically with all rotations applied

## 🔧 Technical Details

### Backend (app.py)
- **Framework**: Flask 3.0.0
- **PDF Library**: PyPDF2 3.0.1
- **Features**:
  - `/preview` endpoint - Generates first-page preview (base64)
  - `/merge` endpoint - Merges PDFs with rotation support
  - Password-protected PDF detection
  - Error handling for corrupted files

### Frontend (index.html)
- **Pure JavaScript** - No external dependencies
- **Features**:
  - Drag-and-drop file upload
  - Drag-and-drop reordering
  - Modal preview with embedded PDF viewer
  - Real-time rotation tracking
  - Progress indication
  - Responsive design (mobile-friendly)

## 🛡️ Security Features

- Max file size: 500MB total
- Max files: 10
- File type validation (PDF only)
- Encrypted PDF detection
- In-memory processing (no server-side file storage)

## 📝 Requirements

- Python 3.7+
- Flask 3.0.0
- PyPDF2 3.0.1
- Modern web browser with PDF support

## 🎯 Use Cases

- Combine multiple scanned documents
- Merge reports/presentations
- Reorder pages from different PDFs
- Fix document orientation before merging
- Create consolidated PDF archives

## 🐛 Troubleshooting

**Preview not working?**
- Ensure browser supports embedded PDFs
- Check if PDF is password-protected

**Rotation not applied?**
- Click ↻ Rotate button until desired angle shows
- Preview will show rotation indicator

**Upload fails?**
- Check file is valid PDF
- Ensure total size < 500MB
- Maximum 10 files allowed

## 📄 License

MIT License - Free to use and modify
