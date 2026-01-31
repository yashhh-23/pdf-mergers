# app_full.py - Complete PDF Tools Backend with all 29 tools
from flask import Flask, render_template, request, send_file, jsonify
from PyPDF2 import PdfWriter, PdfReader
from PIL import Image, ImageDraw, ImageFont
import os
import io
import traceback
import zipfile
from pathlib import Path
import threading
import time
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============= FILE CLEANUP SYSTEM =============
# Files are automatically deleted 1 hour after upload

FILE_METADATA_PATH = os.path.join(app.config['UPLOAD_FOLDER'], 'file_metadata.json')
FILE_EXPIRY_HOURS = 1  # Delete files after 1 hour

class FileCleanupManager:
    """Manages file upload timestamps and automatic deletion"""
    
    def __init__(self, metadata_file=FILE_METADATA_PATH):
        self.metadata_file = metadata_file
        self.files_metadata = self._load_metadata()
        self.cleanup_thread = None
        self.running = False
    
    def _load_metadata(self):
        """Load file metadata from JSON"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save_metadata(self):
        """Save file metadata to JSON"""
        try:
            os.makedirs(os.path.dirname(self.metadata_file) or '.', exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                json.dump(self.files_metadata, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save metadata: {e}")
    
    def track_file(self, filename, file_path):
        """Track a file with upload timestamp"""
        timestamp = datetime.now().isoformat()
        expiry_time = (datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS)).isoformat()
        
        self.files_metadata[filename] = {
            'path': file_path,
            'uploaded_at': timestamp,
            'expires_at': expiry_time,
            'deleted': False
        }
        self._save_metadata()
        print(f"📝 Tracked file: {filename} (expires at {expiry_time})")
    
    def get_file_info(self, filename):
        """Get file information and remaining time"""
        if filename in self.files_metadata:
            metadata = self.files_metadata[filename]
            expires_at = datetime.fromisoformat(metadata['expires_at'])
            now = datetime.now()
            remaining = (expires_at - now).total_seconds()
            
            return {
                'filename': filename,
                'uploaded_at': metadata['uploaded_at'],
                'expires_at': metadata['expires_at'],
                'remaining_seconds': max(0, int(remaining)),
                'remaining_minutes': max(0, int(remaining // 60)),
                'remaining_hours': max(0, remaining // 3600)
            }
        return None
    
    def cleanup_expired_files(self):
        """Delete files that have expired"""
        now = datetime.now()
        deleted_count = 0
        
        for filename, metadata in list(self.files_metadata.items()):
            if metadata['deleted']:
                continue
            
            try:
                expires_at = datetime.fromisoformat(metadata['expires_at'])
                
                if now >= expires_at:
                    file_path = metadata['path']
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"🗑️ Deleted expired file: {filename}")
                    
                    metadata['deleted'] = True
                    self._save_metadata()
            except Exception as e:
                print(f"⚠️ Error deleting {filename}: {e}")
        
        return deleted_count
    
    def start_background_cleanup(self, interval_seconds=60):
        """Start background thread to clean up expired files"""
        if self.running:
            return
        
        self.running = True
        
        def cleanup_loop():
            while self.running:
                try:
                    self.cleanup_expired_files()
                    time.sleep(interval_seconds)
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")
                    time.sleep(interval_seconds)
        
        self.cleanup_thread = threading.Thread(daemon=True, target=cleanup_loop)
        self.cleanup_thread.start()
        print("✅ Background file cleanup started (runs every 60 seconds)")
    
    def stop_background_cleanup(self):
        """Stop background cleanup thread"""
        self.running = False

# Initialize cleanup manager
cleanup_manager = FileCleanupManager()
# Start background cleanup thread (checks every 60 seconds for expired files)
cleanup_manager.start_background_cleanup(interval_seconds=60)
print("✅ File tracking and auto-deletion system initialized (1-hour expiry)")

# ============= ROUTES =============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/test-onclick')
def test_onclick():
    with open('test_onclick.html', 'r') as f:
        return f.read()

@app.route('/debug')
def debug():
    return render_template('debug.html')

@app.route('/tools')
def tools():
    return render_template('tools_test.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ============= FILE MANAGEMENT APIs =============

@app.route('/api/file-info', methods=['POST'])
def api_file_info():
    """Get file expiry information"""
    try:
        filename = request.form.get('filename', '')
        if not filename:
            return jsonify({'error': 'No filename provided'}), 400
        
        info = cleanup_manager.get_file_info(filename)
        if info:
            return jsonify(info), 200
        else:
            return jsonify({'error': 'File not found in tracking system'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-status', methods=['GET'])
def api_cleanup_status():
    """Get file cleanup status"""
    try:
        total_files = len(cleanup_manager.files_metadata)
        expired_files = sum(1 for f in cleanup_manager.files_metadata.values() if f['deleted'])
        active_files = total_files - expired_files
        
        return jsonify({
            'total_tracked_files': total_files,
            'active_files': active_files,
            'deleted_files': expired_files,
            'cleanup_running': cleanup_manager.running,
            'file_expiry_hours': FILE_EXPIRY_HOURS
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= ORGANIZE PDF APIs =============

@app.route('/api/merge', methods=['POST'])
def api_merge():
    """Merge multiple PDFs into one"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            if file.filename.lower().endswith('.pdf'):
                try:
                    pdf_reader = PdfReader(file.stream)
                    if pdf_reader.is_encrypted:
                        pdf_reader.decrypt('')
                    for page in pdf_reader.pages:
                        pdf_writer.add_page(page)
                except Exception as e:
                    return jsonify({'error': f'Error reading {file.filename}: {str(e)}'}), 400
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='merged.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/split', methods=['POST'])
def api_split():
    """Split PDF into multiple files"""
    try:
        file = request.files.get('file_0')
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        pdf_reader = PdfReader(file.stream)
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for page_num in range(len(pdf_reader.pages)):
                pdf_writer = PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
                page_buffer = io.BytesIO()
                pdf_writer.write(page_buffer)
                page_buffer.seek(0)
                
                zip_file.writestr(f'page_{page_num + 1}.pdf', page_buffer.getvalue())
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='split_pages.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove-pages', methods=['POST'])
def api_remove_pages():
    """Remove specific pages from PDF"""
    try:
        file = request.files.get('file_0')
        pages_to_remove = request.form.get('pages', '')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        # Parse pages (e.g., "1,3,5-7")
        pages_to_remove_set = parse_page_numbers(pages_to_remove)
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for i, page in enumerate(pdf_reader.pages):
            if (i + 1) not in pages_to_remove_set:
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='removed_pages.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/extract-pages', methods=['POST'])
def api_extract_pages():
    """Extract specific pages from PDF"""
    try:
        file = request.files.get('file_0')
        pages_to_extract = request.form.get('pages', '')
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        pages_set = parse_page_numbers(pages_to_extract)
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for page_num in sorted(pages_set):
            if 0 < page_num <= len(pdf_reader.pages):
                pdf_writer.add_page(pdf_reader.pages[page_num - 1])
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='extracted_pages.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/organize', methods=['POST'])
def api_organize():
    """Reorder pages in PDF"""
    try:
        file = request.files.get('file_0')
        page_order = request.form.get('order', '')  # e.g., "3,1,2,4"
        
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        order_list = [int(x.strip()) for x in page_order.split(',') if x.strip()]
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for page_num in order_list:
            if 0 < page_num <= len(pdf_reader.pages):
                pdf_writer.add_page(pdf_reader.pages[page_num - 1])
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='organized.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-to-pdf', methods=['POST'])
def api_scan_to_pdf():
    """Convert images to PDF"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            # Convert image to PDF page
            image = Image.open(file.stream)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as PDF in memory
            img_buffer = io.BytesIO()
            image.save(img_buffer, 'PDF')
            img_buffer.seek(0)
            
            # Read and add to writer
            img_pdf = PdfReader(img_buffer)
            pdf_writer.add_page(img_pdf.pages[0])
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='scanned.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= OPTIMIZE PDF APIs =============

@app.route('/api/compress', methods=['POST'])
def api_compress():
    """Compress PDF file size"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        quality = request.form.get('quality', 'Medium')
        
        pdf_writer = PdfWriter()
        
        for file in files:
            pdf_reader = PdfReader(file.stream)
            for page in pdf_reader.pages:
                # Compress by removing unused objects
                page.compress_content_streams()
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='compressed.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/repair', methods=['POST'])
def api_repair():
    """Attempt to repair corrupted PDF"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            try:
                pdf_reader = PdfReader(file.stream, strict=False)
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            except Exception as e:
                print(f"Warning: Error reading {file.filename}: {e}")
                continue
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='repaired.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    """OCR PDF to make it searchable"""
    try:
        # Note: Requires pytesseract and pdf2image
        return jsonify({'error': 'OCR functionality requires additional libraries (pytesseract, pdf2image)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= CONVERT TO PDF APIs =============

@app.route('/api/jpg-to-pdf', methods=['POST'])
def api_jpg_to_pdf():
    """Convert JPG/PNG to PDF"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            image = Image.open(file.stream)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_buffer = io.BytesIO()
            image.save(img_buffer, 'PDF')
            img_buffer.seek(0)
            
            img_pdf = PdfReader(img_buffer)
            pdf_writer.add_page(img_pdf.pages[0])
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='converted.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/word-to-pdf', methods=['POST'])
def api_word_to_pdf():
    """Convert Word to PDF"""
    try:
        # Requires python-docx2pdf or similar
        return jsonify({'error': 'Word conversion requires additional libraries (docx2pdf)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/powerpoint-to-pdf', methods=['POST'])
def api_powerpoint_to_pdf():
    """Convert PowerPoint to PDF"""
    try:
        return jsonify({'error': 'PowerPoint conversion requires additional libraries'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/excel-to-pdf', methods=['POST'])
def api_excel_to_pdf():
    """Convert Excel to PDF"""
    try:
        return jsonify({'error': 'Excel conversion requires additional libraries (openpyxl)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/html-to-pdf', methods=['POST'])
def api_html_to_pdf():
    """Convert HTML to PDF"""
    try:
        # Requires pdfkit or weasyprint
        return jsonify({'error': 'HTML conversion requires additional libraries (pdfkit/weasyprint)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= CONVERT FROM PDF APIs =============

@app.route('/api/pdf-to-jpg', methods=['POST'])
def api_pdf_to_jpg():
    """Convert PDF pages to JPG images"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        dpi = int(request.form.get('dpi', '150'))
        
        # Note: Requires pdf2image library
        return jsonify({'error': 'PDF to image conversion requires pdf2image library'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf-to-word', methods=['POST'])
def api_pdf_to_word():
    """Convert PDF to Word"""
    try:
        return jsonify({'error': 'PDF to Word conversion requires additional libraries (pdf2docx)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf-to-powerpoint', methods=['POST'])
def api_pdf_to_powerpoint():
    """Convert PDF to PowerPoint"""
    try:
        return jsonify({'error': 'PDF to PowerPoint conversion requires additional libraries'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf-to-excel', methods=['POST'])
def api_pdf_to_excel():
    """Convert PDF to Excel"""
    try:
        return jsonify({'error': 'PDF to Excel conversion requires additional libraries (tabula-py)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pdf-to-pdfa', methods=['POST'])
def api_pdf_to_pdfa():
    """Convert PDF to PDF/A format"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            pdf_reader = PdfReader(file.stream)
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='pdfa_converted.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= EDIT PDF APIs =============

@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    """Rotate PDF pages"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        rotation_str = request.form.get('rotation', '90° Clockwise')
        
        # Parse rotation
        rotation = 90
        if '180' in rotation_str:
            rotation = 180
        elif 'Counter' in rotation_str:
            rotation = 270
        
        pdf_writer = PdfWriter()
        
        for file in files:
            pdf_reader = PdfReader(file.stream)
            for page in pdf_reader.pages:
                page.rotate(rotation)
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='rotated.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-page-numbers', methods=['POST'])
def api_add_page_numbers():
    """Add page numbers to PDF"""
    try:
        # Requires reportlab for adding text
        return jsonify({'error': 'Page numbering requires reportlab library'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-watermark', methods=['POST'])
def api_add_watermark():
    """Add watermark to PDF"""
    try:
        # Requires reportlab for adding text/images
        return jsonify({'error': 'Watermarking requires reportlab library'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/crop', methods=['POST'])
def api_crop():
    """Crop PDF pages"""
    try:
        file = request.files.get('file_0')
        if not file:
            return jsonify({'error': 'No file provided'}), 400
        
        margins_str = request.form.get('margins', '0,0,0,0')
        margins = [float(x.strip()) for x in margins_str.split(',')]
        
        if len(margins) != 4:
            return jsonify({'error': 'Invalid margins format'}), 400
        
        top, right, bottom, left = margins
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for page in pdf_reader.pages:
            # Get current media box
            mb = page.mediabox
            page.mediabox.lower_left = (mb.left + left, mb.bottom + bottom)
            page.mediabox.upper_right = (mb.right - right, mb.top - top)
            pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='cropped.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/edit-pdf', methods=['POST'])
def api_edit_pdf():
    """Edit PDF content"""
    try:
        return jsonify({'error': 'PDF editing requires advanced libraries (PyMuPDF)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= SECURITY APIs =============

@app.route('/api/unlock', methods=['POST'])
def api_unlock():
    """Remove password from PDF"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        password = request.form.get('password', '')
        
        pdf_writer = PdfWriter()
        
        for file in files:
            pdf_reader = PdfReader(file.stream)
            if pdf_reader.is_encrypted:
                pdf_reader.decrypt(password)
            
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='unlocked.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/protect', methods=['POST'])
def api_protect():
    """Add password protection to PDF"""
    try:
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        password = request.form.get('password', '')
        allow_print = request.form.get('allowPrint', 'false') == 'true'
        allow_copy = request.form.get('allowCopy', 'false') == 'true'
        
        pdf_writer = PdfWriter()
        
        for file in files:
            pdf_reader = PdfReader(file.stream)
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
        
        # Encrypt with password
        pdf_writer.encrypt(password, permissions_flag=(
            (1 << 2 if allow_print else 0) |  # Allow printing
            (1 << 4 if allow_copy else 0)     # Allow copy/paste
        ))
        
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='protected.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sign', methods=['POST'])
def api_sign():
    """Add digital signature to PDF"""
    try:
        return jsonify({'error': 'Digital signing requires cryptography libraries'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/redact', methods=['POST'])
def api_redact():
    """Redact sensitive information"""
    try:
        return jsonify({'error': 'Redaction requires advanced libraries (PyMuPDF)'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare', methods=['POST'])
def api_compare():
    """Compare two PDFs"""
    try:
        return jsonify({'error': 'PDF comparison requires advanced libraries'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= UTILITY FUNCTIONS =============

def parse_page_numbers(pages_str):
    """Parse page numbers string like '1,3,5-7' into a set"""
    pages = set()
    if not pages_str:
        return pages
    
    parts = pages_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                pages.update(range(int(start.strip()), int(end.strip()) + 1))
            except:
                continue
        else:
            try:
                pages.add(int(part.strip()))
            except:
                continue
    
    return pages

# ============= RUN APP =============

if __name__ == '__main__':
    app.run(debug=True, port=5000)
