# 📄 PDF Tools Suite - Complete PDF Processing Solution

A comprehensive Flask-based web application with 20 PDF tools including merging, splitting, conversion, editing, and OCR capabilities.

## ✨ Features

### �️ ORGANIZE PDF (6 tools)
- **Merge PDF**: Combine multiple PDFs into one
- **Split PDF**: Split PDF into separate pages
- **Remove Pages**: Delete specific pages from PDF
- **Extract Pages**: Extract specific pages to new PDF
- **Reorder Pages**: Rearrange pages within PDF
- **Scan to PDF**: Convert images to PDF

### ⚡ OPTIMIZE PDF (2 tools)
- **Compress PDF**: Reduce file size
- **Repair PDF**: Fix corrupted PDF files

### ➡️ CONVERT TO PDF (3 tools)
- **Images to PDF**: Convert JPG, PNG to PDF
- **Word to PDF**: Convert DOCX to PDF
- **Excel to PDF**: Convert XLSX to PDF

### ⬅️ CONVERT FROM PDF (4 tools)
- **PDF to Images**: Convert PDF pages to JPG/PNG
- **PDF to Word**: Convert PDF to editable DOCX
- **PDF to Excel**: Extract tables to XLSX
- **OCR**: Extract text from images/PDFs

### ✏️ EDIT PDF (4 tools)
- **Rotate PDF**: Rotate pages 90°, 180°, 270°
- **Crop PDF**: Trim margins
- **Add Watermark**: Text watermark
- **Add Page Numbers**: Numbering system

### 🔒 SECURITY (2 tools)
- **Protect PDF**: Add password protection
- **Unlock PDF**: Remove password

## 🏗️ Project Structure

```
pdf-mergers/
├── backend/                 # Python backend files
│   ├── app_working.py      # Main application (20 tools)
│   ├── app_full.py         # Previous version (12 tools)
│   ├── app.py              # Original merger app
│   └── BACKEND_STATUS.md   # Tool status documentation
├── frontend/               # Frontend files
│   ├── templates/          # HTML templates
│   │   ├── index.html      # Home page
│   │   └── tools_working.html # Tools page
│   ├── pdf_merger/         # Static files
│   └── temp_uploads/       # Upload directory
├── requirements.txt        # Python dependencies
├── start_server.bat       # Windows startup script
└── README.md              # This file
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+
- Tesseract OCR (for OCR tool)
- Git

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/yashhh-23/pdf-mergers.git
cd pdf-mergers
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (for OCR tool)
**Windows:**
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Add to PATH environment variable

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract
```

### 3. Run the Application
```bash
# Option 1: Use the batch file (Windows)
start_server.bat

# Option 2: Manual start
python backend/app_working.py
```

### 4. Open in Browser
```
http://localhost:5000
```

## 📖 How to Use

### Access Tools
1. Open `http://localhost:5000/tools`
2. Choose from 6 categories of PDF tools
3. Click any tool card to open the processing modal

### File Upload & Processing
- **Drag & Drop**: Drop files directly onto the upload area
- **Click to Upload**: Click the upload area to browse files
- **Multiple Files**: Some tools support multiple file uploads
- **File Validation**: Automatic file type checking
- **Progress Tracking**: Real-time processing progress
- **Auto-Download**: Processed files download automatically

### Security Features
- 🔒 **Auto-Deletion**: Uploaded files deleted after 1 hour
- 🛡️ **Memory Processing**: Files processed in memory, not saved permanently
- 🔐 **Password Protection**: Secure PDF protection/unlocking

## 🔧 Technical Stack

### Backend
- **Flask 3.0.0**: Web framework
- **PyPDF2 3.0.1**: Core PDF manipulation
- **PyMuPDF (fitz)**: Advanced PDF processing
- **Pillow**: Image processing
- **ReportLab**: PDF generation
- **python-docx**: Word document processing
- **pdf2docx**: PDF to Word conversion
- **openpyxl**: Excel processing
- **pytesseract**: OCR functionality

### Frontend
- **HTML5/CSS3**: Modern responsive design
- **Vanilla JavaScript**: No frameworks, lightweight
- **File API**: Drag-and-drop file handling
- **FormData**: AJAX file uploads
- **Progress Tracking**: Real-time upload progress

## 📊 Tool Status

| Tool | Status | Backend | Frontend |
|------|--------|---------|----------|
| Merge PDF | ✅ Ready | ✅ | ✅ |
| Split PDF | ✅ Ready | ✅ | ✅ |
| Remove Pages | ✅ Ready | ✅ | ✅ |
| Extract Pages | ✅ Ready | ✅ | ✅ |
| Reorder Pages | ✅ Ready | ✅ | ✅ |
| Images to PDF | ✅ Ready | ✅ | ✅ |
| PDF to Images | ✅ Ready | ✅ | ✅ |
| Compress PDF | ✅ Ready | ✅ | ✅ |
| Repair PDF | ✅ Ready | ✅ | ✅ |
| Rotate PDF | ✅ Ready | ✅ | ✅ |
| Crop PDF | ✅ Ready | ✅ | ✅ |
| Watermark | ✅ Ready | ✅ | ✅ |
| Page Numbers | ✅ Ready | ✅ | ✅ |
| Protect PDF | ✅ Ready | ✅ | ✅ |
| Unlock PDF | ✅ Ready | ✅ | ✅ |
| Word to PDF | ✅ Ready | ✅ | ✅ |
| Excel to PDF | ✅ Ready | ✅ | ✅ |
| PDF to Word | ✅ Ready | ✅ | ✅ |
| PDF to Excel | ✅ Ready | ✅ | ✅ |
| OCR | ✅ Ready | ✅ | ✅ |

## 🐛 Troubleshooting

### Common Issues

**OCR Tool Not Working:**
- Install Tesseract OCR and add to PATH
- Check if `pytesseract` is installed: `pip install pytesseract`

**File Upload Issues:**
- Check file size limits (100MB max)
- Ensure correct file types for each tool
- Clear browser cache

**Memory Errors:**
- Large PDFs may require more RAM
- Try processing smaller files
- Close other applications

### Development Mode
```bash
# Run with debug mode
python backend/app_working.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source. Feel free to use and modify.

## � Support

For issues or questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Ensure all dependencies are installed

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
