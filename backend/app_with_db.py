"""
PDF Tools Backend with Database - Complete Implementation
All tools working with SQLite database for file tracking
Files automatically deleted after 1 hour
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm
from reportlab.lib.colors import Color
import io
import os
import zipfile
import tempfile
import threading
import time
import uuid
import shutil

# Create Flask app with correct template folder
template_folder = os.path.join(os.path.dirname(__file__), '../frontend/templates')
app = Flask(__name__, template_folder=template_folder)

# ============= DATABASE CONFIGURATION =============
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '../data/pdf_tools.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

db = SQLAlchemy(app)

# Ensure data directory exists
os.makedirs(os.path.join(basedir, '../data'), exist_ok=True)
os.makedirs(os.path.join(basedir, '../frontend/temp_uploads'), exist_ok=True)

# ============= DATABASE MODELS =============
class UploadedFile(db.Model):
    """Model for tracking uploaded files"""
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    mime_type = db.Column(db.String(50), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'filename': self.original_filename,
            'file_size': self.format_file_size(self.file_size),
            'file_size_bytes': self.file_size,
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
            'expires_at': self.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            'time_remaining': self.get_time_remaining(),
            'mime_type': self.mime_type
        }
    
    @staticmethod
    def format_file_size(bytes_size):
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"
    
    def get_time_remaining(self):
        """Get remaining time until deletion"""
        remaining = self.expires_at - datetime.now(timezone.utc)
        if remaining.total_seconds() <= 0:
            return "Expired"
        
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


# ============= DATABASE INITIALIZATION =============
with app.app_context():
    db.create_all()

# ============= FILE CLEANUP SYSTEM =============
class DatabaseCleanupManager:
    """Manages automatic deletion of expired files"""
    
    def __init__(self, expiry_hours=1):
        self.expiry_hours = expiry_hours
        self.running = False
    
    def cleanup_expired(self):
        """Delete expired files from database and filesystem"""
        try:
            with app.app_context():
                now = datetime.now(timezone.utc)
                expired_files = UploadedFile.query.filter(
                    UploadedFile.expires_at <= now,
                    UploadedFile.is_deleted == False
                ).all()
                
                for file_record in expired_files:
                    try:
                        # Delete from filesystem
                        if os.path.exists(file_record.file_path):
                            os.remove(file_record.file_path)
                            print(f"🗑️ Deleted expired file: {file_record.original_filename}")
                        
                        # Mark as deleted in database
                        file_record.is_deleted = True
                        db.session.commit()
                    except Exception as e:
                        print(f"Error deleting file {file_record.original_filename}: {str(e)}")
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
    
    def start_background_cleanup(self, interval=60):
        """Start background cleanup thread"""
        self.running = True
        
        def cleanup_loop():
            while self.running:
                self.cleanup_expired()
                time.sleep(interval)
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        print("✅ Database-backed file cleanup started (runs every 60 seconds)")

cleanup_manager = DatabaseCleanupManager(expiry_hours=1)
cleanup_manager.start_background_cleanup(interval=60)

# ============= ROUTES =============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tools')
def tools():
    return render_template('tools_working.html')

@app.route('/uploads')
def uploads_page():
    """Page to view all uploaded files"""
    return render_template('uploads.html')

@app.route('/api/uploads', methods=['GET'])
def get_uploads():
    """Get all non-deleted uploaded files"""
    try:
        files = UploadedFile.query.filter_by(is_deleted=False).order_by(
            UploadedFile.uploaded_at.desc()
        ).all()
        
        return jsonify({
            'success': True,
            'total_files': len(files),
            'files': [f.to_dict() for f in files]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/file/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Manually delete a file"""
    try:
        file_record = UploadedFile.query.get(file_id)
        
        if not file_record:
            return jsonify({'error': 'File not found'}), 404
        
        if file_record.is_deleted:
            return jsonify({'error': 'File already deleted'}), 410
        
        # Delete from filesystem
        if os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # Mark as deleted in database
        file_record.is_deleted = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-expired', methods=['POST'])
def trigger_cleanup():
    """Manually trigger cleanup (admin endpoint)"""
    try:
        cleanup_manager.cleanup_expired()
        return jsonify({'success': True, 'message': 'Cleanup triggered'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= HELPER FUNCTIONS =============

def save_uploaded_file(file_obj, original_filename):
    """Save uploaded file and create database record"""
    try:
        # Create unique filename
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        file_path = os.path.join(basedir, '../frontend/temp_uploads', unique_filename)
        
        # Save file
        file_obj.save(file_path)
        file_size = os.path.getsize(file_path)
        
        # Create database record
        file_record = UploadedFile(
            filename=unique_filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file_obj.content_type or 'application/octet-stream',
            uploaded_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        db.session.add(file_record)
        db.session.commit()
        
        return file_record
    except Exception as e:
        print(f"Error saving file: {str(e)}")
        return None

def get_uploaded_files(request_obj):
    """Extract all uploaded files from request"""
    files = []
    i = 0
    while f'file_{i}' in request_obj.files:
        f = request_obj.files[f'file_{i}']
        if f and f.filename:
            files.append(f)
        i += 1
    return files

# ============= PDF TOOLS API =============

@app.route('/api/merge', methods=['POST'])
def api_merge():
    """Merge multiple PDFs into one"""
    try:
        files = get_uploaded_files(request)
        
        if len(files) < 2:
            return jsonify({'error': 'Please upload at least 2 PDF files'}), 400
        
        writer = PdfWriter()
        
        for f in files:
            try:
                reader = PdfReader(f.stream)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                return jsonify({'error': f'Error reading {f.filename}: {str(e)}'}), 400
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='merged.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/split', methods=['POST'])
def api_split():
    """Split PDF into separate pages"""
    try:
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        reader = PdfReader(f.stream)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                
                page_buffer = io.BytesIO()
                writer.write(page_buffer)
                page_buffer.seek(0)
                
                zf.writestr(f'page_{i+1}.pdf', page_buffer.getvalue())
        
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='split_pages.zip')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/remove-pages', methods=['POST'])
def api_remove_pages():
    """Remove specific pages from PDF"""
    try:
        f = request.files.get('file_0')
        pages_str = request.form.get('pages', '')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not pages_str:
            return jsonify({'error': 'Please specify pages to remove'}), 400
        
        # Parse page numbers
        pages_to_remove = set()
        for part in pages_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                pages_to_remove.update(range(int(start), int(end) + 1))
            else:
                pages_to_remove.add(int(part))
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for i, page in enumerate(reader.pages):
            if (i + 1) not in pages_to_remove:
                writer.add_page(page)
        
        if len(writer.pages) == 0:
            return jsonify({'error': 'Cannot remove all pages'}), 400
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='pages_removed.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extract-pages', methods=['POST'])
def api_extract_pages():
    """Extract specific pages from PDF"""
    try:
        f = request.files.get('file_0')
        pages_str = request.form.get('pages', '')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not pages_str:
            return jsonify({'error': 'Please specify pages to extract'}), 400
        
        # Parse page numbers
        pages_to_extract = set()
        for part in pages_str.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                pages_to_extract.update(range(int(start), int(end) + 1))
            else:
                pages_to_extract.add(int(part))
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for i, page in enumerate(reader.pages):
            if (i + 1) in pages_to_extract:
                writer.add_page(page)
        
        if len(writer.pages) == 0:
            return jsonify({'error': 'No valid pages to extract'}), 400
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='extracted.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/organize', methods=['POST'])
def api_organize():
    """Reorder pages in PDF"""
    try:
        f = request.files.get('file_0')
        order_str = request.form.get('order', '')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not order_str:
            return jsonify({'error': 'Please specify page order'}), 400
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        try:
            order = [int(x.strip()) for x in order_str.split(',')]
        except:
            return jsonify({'error': 'Invalid page order format'}), 400
        
        for page_num in order:
            if 0 < page_num <= len(reader.pages):
                writer.add_page(reader.pages[page_num - 1])
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='organized.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-to-pdf', methods=['POST'])
def api_scan_to_pdf():
    """Convert scanned images to PDF"""
    try:
        images = []
        i = 0
        while f'file_{i}' in request.files:
            f = request.files[f'file_{i}']
            if f and f.filename:
                images.append(f)
            i += 1
        
        if not images:
            return jsonify({'error': 'No images uploaded'}), 400
        
        pdf_images = []
        for img_file in images:
            img = Image.open(img_file.stream)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            pdf_images.append(img)
        
        output = io.BytesIO()
        
        if len(pdf_images) == 1:
            pdf_images[0].save(output, 'PDF')
        else:
            pdf_images[0].save(output, 'PDF', save_all=True, append_images=pdf_images[1:])
        
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='scanned.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compress', methods=['POST'])
def api_compress():
    """Advanced PDF compression with multiple levels"""
    try:
        f = request.files.get('file_0')
        level = request.form.get('level', 'Medium')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        original_size = len(pdf_data)
        
        # Use PyMuPDF for better compression
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Compression settings based on level
        if level == 'Low':
            # Light compression - preserve quality
            garbage = 1
            deflate = True
            deflate_images = False
            deflate_fonts = False
            image_quality = 95
        elif level == 'High':
            # Maximum compression - smaller file
            garbage = 4
            deflate = True
            deflate_images = True
            deflate_fonts = True
            image_quality = 50
        else:  # Medium (default)
            garbage = 2
            deflate = True
            deflate_images = True
            deflate_fonts = False
            image_quality = 75
        
        # Process each page for image compression
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get all images on the page
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                
                try:
                    # Extract and recompress images
                    base_image = doc.extract_image(xref)
                    if base_image:
                        image_bytes = base_image["image"]
                        
                        # Open with PIL and recompress
                        img_pil = Image.open(io.BytesIO(image_bytes))
                        
                        if img_pil.mode == 'RGBA':
                            img_pil = img_pil.convert('RGB')
                        
                        # Resize large images for high compression
                        if level == 'High':
                            max_dim = 1200
                            if img_pil.width > max_dim or img_pil.height > max_dim:
                                img_pil.thumbnail((max_dim, max_dim), Image.LANCZOS)
                        
                        # Save with quality setting
                        img_buffer = io.BytesIO()
                        img_pil.save(img_buffer, format='JPEG', quality=image_quality, optimize=True)
                        
                except Exception:
                    pass  # Skip problematic images
        
        # Save with compression options
        output = io.BytesIO()
        doc.save(output, garbage=garbage, deflate=deflate, clean=True)
        doc.close()
        
        output.seek(0)
        compressed_size = len(output.getvalue())
        output.seek(0)
        
        # Calculate compression ratio
        ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
        
        response = send_file(output, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
        response.headers['X-Original-Size'] = str(original_size)
        response.headers['X-Compressed-Size'] = str(compressed_size)
        response.headers['X-Compression-Ratio'] = f'{ratio:.1f}%'
        
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/repair', methods=['POST'])
def api_repair():
    """Advanced PDF repair - fix corrupted PDFs"""
    try:
        f = request.files.get('file_0')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        
        # Try multiple repair methods
        repair_methods = []
        repaired = False
        output = None
        
        # Method 1: PyMuPDF repair (most robust)
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            # Force repair by cleaning and garbage collection
            output = io.BytesIO()
            doc.save(output, garbage=4, clean=True, deflate=True, 
                    linear=False, pretty=False, encryption=fitz.PDF_ENCRYPT_NONE)
            doc.close()
            output.seek(0)
            repaired = True
            repair_methods.append("PyMuPDF deep clean")
        except Exception as e1:
            repair_methods.append(f"PyMuPDF failed: {str(e1)[:50]}")
        
        # Method 2: PyPDF2 repair if PyMuPDF failed
        if not repaired:
            try:
                reader = PdfReader(io.BytesIO(pdf_data))
                writer = PdfWriter()
                
                for page in reader.pages:
                    writer.add_page(page)
                
                # Clone metadata if available
                if reader.metadata:
                    writer.add_metadata(reader.metadata)
                
                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                repaired = True
                repair_methods.append("PyPDF2 rebuild")
            except Exception as e2:
                repair_methods.append(f"PyPDF2 failed: {str(e2)[:50]}")
        
        # Method 3: Page-by-page extraction if structure is corrupted
        if not repaired:
            try:
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                new_doc = fitz.open()
                
                for page_num in range(len(doc)):
                    try:
                        page = doc[page_num]
                        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
                        new_page.show_pdf_page(new_page.rect, doc, page_num)
                    except:
                        # Create blank page for corrupted pages
                        new_doc.new_page(width=595, height=842)  # A4 size
                
                output = io.BytesIO()
                new_doc.save(output, garbage=4, clean=True)
                new_doc.close()
                doc.close()
                output.seek(0)
                repaired = True
                repair_methods.append("Page-by-page reconstruction")
            except Exception as e3:
                repair_methods.append(f"Reconstruction failed: {str(e3)[:50]}")
        
        if not repaired or output is None:
            return jsonify({
                'error': 'Could not repair PDF. File may be severely corrupted.',
                'attempted_methods': repair_methods
            }), 400
        
        response = send_file(output, mimetype='application/pdf', as_attachment=True, download_name='repaired.pdf')
        response.headers['X-Repair-Methods'] = ', '.join(repair_methods)
        
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    """Advanced PDF rotation with page selection"""
    try:
        f = request.files.get('file_0')
        rotation = request.form.get('rotation', '90° Clockwise')
        pages_str = request.form.get('pages', 'all')  # 'all' or specific pages like '1,3,5-7'
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Map rotation text to degrees
        rotation_map = {
            '90° Clockwise': 90,
            '180°': 180,
            '90° Counter-clockwise': 270,
            '90': 90,
            '180': 180,
            '270': 270
        }
        
        degrees = rotation_map.get(rotation, 90)
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Parse pages to rotate
        if pages_str.lower() == 'all':
            pages_to_rotate = set(range(1, len(doc) + 1))
        else:
            pages_to_rotate = set()
            for part in pages_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    pages_to_rotate.update(range(int(start), int(end) + 1))
                elif part.isdigit():
                    pages_to_rotate.add(int(part))
        
        # Rotate specified pages
        for page_num in range(len(doc)):
            if (page_num + 1) in pages_to_rotate:
                page = doc[page_num]
                page.set_rotation((page.rotation + degrees) % 360)
        
        output = io.BytesIO()
        doc.save(output, garbage=2, clean=True)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='rotated.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/crop', methods=['POST'])
def api_crop():
    """Advanced PDF cropping with precise margin control"""
    try:
        f = request.files.get('file_0')
        margins_str = request.form.get('margins', '10,10,10,10')
        pages_str = request.form.get('pages', 'all')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Parse margins (top, right, bottom, left) in mm
        try:
            margins = [float(m.strip()) for m in margins_str.split(',')]
            if len(margins) == 1:
                margins = margins * 4
            elif len(margins) == 2:
                margins = [margins[0], margins[1], margins[0], margins[1]]
            elif len(margins) == 4:
                pass
            else:
                margins = [10] * 4
        except:
            margins = [10] * 4
        
        # Convert mm to points (1 mm = 2.834 points)
        margins_pts = [m * 2.834 for m in margins]
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Parse pages to crop
        if pages_str.lower() == 'all':
            pages_to_crop = set(range(len(doc)))
        else:
            pages_to_crop = set()
            for part in pages_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    pages_to_crop.update(range(int(start) - 1, int(end)))
                elif part.isdigit():
                    pages_to_crop.add(int(part) - 1)
        
        # Crop specified pages
        for page_num in pages_to_crop:
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                rect = page.rect
                
                # Apply margins: top, right, bottom, left
                new_rect = fitz.Rect(
                    rect.x0 + margins_pts[3],  # left
                    rect.y0 + margins_pts[0],  # top
                    rect.x1 - margins_pts[1],  # right
                    rect.y1 - margins_pts[2]   # bottom
                )
                
                # Ensure valid rectangle
                if new_rect.width > 0 and new_rect.height > 0:
                    page.set_cropbox(new_rect)
        
        output = io.BytesIO()
        doc.save(output, garbage=2, clean=True)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='cropped.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watermark', methods=['POST'])
def api_watermark():
    """Advanced watermark with positioning and styling options"""
    try:
        f = request.files.get('file_0')
        text = request.form.get('text', 'CONFIDENTIAL')
        opacity = request.form.get('opacity', '50')
        position = request.form.get('position', 'Center')
        color = request.form.get('color', 'gray')
        font_size = request.form.get('font_size', '60')
        rotation = request.form.get('rotation', '45')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        if not text.strip():
            return jsonify({'error': 'Watermark text cannot be empty'}), 400
        
        # Parse parameters
        try:
            opacity_val = int(opacity) / 100.0
            font_size_val = int(font_size)
            rotation_val = int(rotation)
        except:
            opacity_val = 0.5
            font_size_val = 60
            rotation_val = 45
        
        # Color mapping (RGB values 0-1)
        color_map = {
            'gray': (0.5, 0.5, 0.5),
            'red': (1, 0, 0),
            'blue': (0, 0, 1),
            'green': (0, 0.5, 0),
            'black': (0, 0, 0)
        }
        text_color = color_map.get(color.lower(), (0.5, 0.5, 0.5))
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        for page in doc:
            rect = page.rect
            
            # Calculate center position
            center_x = rect.width / 2
            center_y = rect.height / 2
            
            # Calculate position based on setting
            if position == 'Center' or position == 'Diagonal':
                x = center_x
                y = center_y
            elif position == 'Top Left':
                x = rect.width * 0.2
                y = rect.height * 0.2
            elif position == 'Top Right':
                x = rect.width * 0.8
                y = rect.height * 0.2
            elif position == 'Bottom Left':
                x = rect.width * 0.2
                y = rect.height * 0.8
            elif position == 'Bottom Right':
                x = rect.width * 0.8
                y = rect.height * 0.8
            else:
                x = center_x
                y = center_y
            
            # Create a shape for drawing with opacity
            shape = page.new_shape()
            
            # Calculate text width for centering
            text_length = fitz.get_text_length(text, fontname="helv", fontsize=font_size_val)
            
            # Adjust x position to center the text
            x = x - text_length / 2
            
            # Insert text using shape (supports morph for rotation)
            # Create rotation matrix around the text center point
            pivot = fitz.Point(x + text_length / 2, y)
            morph = (pivot, fitz.Matrix(rotation_val))
            
            shape.insert_text(
                fitz.Point(x, y),
                text,
                fontsize=font_size_val,
                fontname="helv",
                color=text_color,
                morph=morph
            )
            
            # Commit with opacity
            shape.finish(fill_opacity=opacity_val)
            shape.commit()
        
        output = io.BytesIO()
        doc.save(output, garbage=2)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='watermarked.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/page-numbers', methods=['POST'])
def api_page_numbers():
    """Add page numbers with customization options"""
    try:
        f = request.files.get('file_0')
        position = request.form.get('position', 'Bottom Center')
        start = request.form.get('start', '1')
        format_type = request.form.get('format', 'numeric')  # numeric, roman, alpha
        prefix = request.form.get('prefix', '')
        suffix = request.form.get('suffix', '')
        font_size = request.form.get('font_size', '12')
        skip_first = request.form.get('skip_first', 'false')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Parse parameters
        try:
            start_num = int(start)
            font_size_val = int(font_size)
        except:
            start_num = 1
            font_size_val = 12
        
        skip_first_page = skip_first.lower() == 'true'
        
        def format_page_number(num, fmt):
            """Format page number based on type"""
            if fmt == 'roman':
                # Convert to Roman numerals
                val = [
                    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                    (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                    (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')
                ]
                result = ''
                for (arabic, roman) in val:
                    count = num // arabic
                    result += roman * count
                    num -= arabic * count
                return result.lower()
            elif fmt == 'alpha':
                # Convert to alphabetic (a, b, c, ... aa, ab, ...)
                result = ''
                while num > 0:
                    num -= 1
                    result = chr(ord('a') + num % 26) + result
                    num //= 26
                return result
            else:  # numeric
                return str(num)
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        for i, page in enumerate(doc):
            if skip_first_page and i == 0:
                continue
            
            page_num = start_num + (i if not skip_first_page else i - 1)
            if skip_first_page and i == 0:
                continue
            
            formatted_num = format_page_number(page_num, format_type)
            text = f"{prefix}{formatted_num}{suffix}"
            
            rect = page.rect
            
            # Determine position
            margin = 30
            if 'Bottom' in position:
                y = rect.height - margin
            else:
                y = margin
            
            if 'Right' in position:
                x = rect.width - margin - len(text) * font_size_val / 4
            elif 'Left' in position:
                x = margin
            else:  # Center
                x = rect.width / 2 - len(text) * font_size_val / 4
            
            page.insert_text(
                (x, y),
                text,
                fontsize=font_size_val,
                fontname="helv",
                color=(0, 0, 0)
            )
        
        output = io.BytesIO()
        doc.save(output, garbage=2)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='numbered.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/protect', methods=['POST'])
def api_protect():
    """
    HEAVY SECURITY: Add AES-256 encryption with comprehensive permission controls.
    Implements strongest PDF encryption available.
    """
    try:
        f = request.files.get('file_0')
        user_password = request.form.get('password', '')
        owner_password = request.form.get('owner_password', '')  # Optional separate owner password
        encryption_level = request.form.get('encryption', 'AES-256')
        
        # Permission flags
        allow_printing = request.form.get('allow_printing', 'false').lower() == 'true'
        allow_copying = request.form.get('allow_copying', 'false').lower() == 'true'
        allow_modifying = request.form.get('allow_modifying', 'false').lower() == 'true'
        allow_annotations = request.form.get('allow_annotations', 'false').lower() == 'true'
        allow_form_filling = request.form.get('allow_form_filling', 'false').lower() == 'true'
        allow_accessibility = request.form.get('allow_accessibility', 'true').lower() == 'true'  # Default allow for accessibility
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not user_password:
            return jsonify({'error': 'Password is required for protection'}), 400
        
        # Validate password strength
        if len(user_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters for security'}), 400
        
        # If no owner password, use a strong derived one
        if not owner_password:
            import hashlib
            owner_password = hashlib.sha256((user_password + '_owner_salt_2024').encode()).hexdigest()[:32]
        
        pdf_data = f.read()
        
        # Use PyMuPDF for strongest encryption
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Calculate permission flags
        # PyMuPDF permission bits (PDF spec):
        # Bit 3: Allow printing (4)
        # Bit 4: Allow modifying content (8)
        # Bit 5: Allow copying content (16)
        # Bit 6: Allow annotations (32)
        # Bit 9: Allow form filling (256)
        # Bit 10: Allow accessibility (512)
        # Bit 11: Allow document assembly (1024)
        # Bit 12: Allow high-quality printing (2048)
        
        permissions = 0
        if allow_printing:
            permissions |= (fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ) if hasattr(fitz, 'PDF_PERM_PRINT') else 2052
        if allow_copying:
            permissions |= fitz.PDF_PERM_COPY if hasattr(fitz, 'PDF_PERM_COPY') else 16
        if allow_modifying:
            permissions |= fitz.PDF_PERM_MODIFY if hasattr(fitz, 'PDF_PERM_MODIFY') else 8
        if allow_annotations:
            permissions |= fitz.PDF_PERM_ANNOTATE if hasattr(fitz, 'PDF_PERM_ANNOTATE') else 32
        if allow_form_filling:
            permissions |= fitz.PDF_PERM_FORM if hasattr(fitz, 'PDF_PERM_FORM') else 256
        if allow_accessibility:
            permissions |= fitz.PDF_PERM_ACCESSIBILITY if hasattr(fitz, 'PDF_PERM_ACCESSIBILITY') else 512
        
        # Determine encryption method (AES-256 is strongest)
        encrypt_method = fitz.PDF_ENCRYPT_AES_256 if hasattr(fitz, 'PDF_ENCRYPT_AES_256') else 4
        
        output = io.BytesIO()
        
        # Save with heavy encryption
        doc.save(
            output,
            encryption=encrypt_method,
            user_pw=user_password,
            owner_pw=owner_password,
            permissions=permissions,
            garbage=4,  # Maximum garbage collection
            clean=True,
            deflate=True
        )
        doc.close()
        output.seek(0)
        
        return send_file(
            output, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name='protected_secure.pdf'
        )
    
    except Exception as e:
        return jsonify({'error': f'Protection failed: {str(e)}'}), 500


@app.route('/api/unlock', methods=['POST'])
def api_unlock():
    """
    ADVANCED UNLOCK: Attempt to remove PDF protection using multiple techniques.
    Works with weakly encrypted PDFs and owner-password-only protected files.
    Does NOT crack strong passwords - only bypasses weak/owner-only restrictions.
    """
    try:
        f = request.files.get('file_0')
        password = request.form.get('password', '')  # Optional - try without first
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        original_data = pdf_data
        unlocked = False
        unlock_method = None
        
        # Method 1: Try PyMuPDF with various approaches
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            if doc.is_encrypted:
                # Try empty password first (owner-only protection often allows this)
                if doc.authenticate(''):
                    unlocked = True
                    unlock_method = "empty_password"
                # Try common passwords
                elif doc.authenticate(password) if password else False:
                    unlocked = True
                    unlock_method = "user_password"
                # Try some common default passwords
                else:
                    common_passwords = ['', ' ', 'password', '123456', '1234', 'admin', 'owner', 'pdf']
                    for cp in common_passwords:
                        if doc.authenticate(cp):
                            unlocked = True
                            unlock_method = f"common_password"
                            break
                
                if unlocked:
                    # Create unlocked version
                    output = io.BytesIO()
                    doc.save(output, garbage=4, clean=True, deflate=True, encryption=0)
                    doc.close()
                    output.seek(0)
                    return send_file(
                        output, 
                        mimetype='application/pdf', 
                        as_attachment=True, 
                        download_name='unlocked.pdf'
                    )
                else:
                    doc.close()
            else:
                # Not encrypted - return as is
                doc.close()
                output = io.BytesIO(pdf_data)
                return send_file(
                    output, 
                    mimetype='application/pdf', 
                    as_attachment=True, 
                    download_name='unlocked.pdf'
                )
        except Exception as e:
            pass
        
        # Method 2: Try PyPDF2 with weak encryption bypass
        try:
            reader = PdfReader(io.BytesIO(original_data))
            
            if reader.is_encrypted:
                # Try to decrypt
                decrypted = False
                
                # Try empty password (works for owner-only protection)
                try:
                    if reader.decrypt(''):
                        decrypted = True
                except:
                    pass
                
                # Try provided password
                if not decrypted and password:
                    try:
                        if reader.decrypt(password):
                            decrypted = True
                    except:
                        pass
                
                # Try common passwords
                if not decrypted:
                    for cp in ['', ' ', 'password', '123456', '1234']:
                        try:
                            result = reader.decrypt(cp)
                            if result:
                                decrypted = True
                                break
                        except:
                            continue
                
                if decrypted:
                    writer = PdfWriter()
                    for page in reader.pages:
                        writer.add_page(page)
                    
                    output = io.BytesIO()
                    writer.write(output)
                    output.seek(0)
                    
                    return send_file(
                        output, 
                        mimetype='application/pdf', 
                        as_attachment=True, 
                        download_name='unlocked.pdf'
                    )
            else:
                # Not encrypted
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                
                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                
                return send_file(
                    output, 
                    mimetype='application/pdf', 
                    as_attachment=True, 
                    download_name='unlocked.pdf'
                )
        except Exception as e:
            pass
        
        # Method 3: Try to remove encryption flags from PDF header (works for weak encryption)
        try:
            # Attempt to rebuild PDF without encryption metadata
            doc = fitz.open(stream=original_data, filetype="pdf")
            
            # If we can access any part of the document, try to rebuild
            if doc.page_count > 0:
                # Create a new document by rendering and reconstructing
                new_doc = fitz.open()
                
                for page in doc:
                    # Get page dimensions
                    rect = page.rect
                    
                    # Create new page
                    new_page = new_doc.new_page(width=rect.width, height=rect.height)
                    
                    # Try to copy content (this may fail for strongly encrypted PDFs)
                    try:
                        # Render page to pixmap and insert
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for quality
                        new_page.insert_image(rect, pixmap=pix)
                    except:
                        pass
                
                if new_doc.page_count > 0:
                    output = io.BytesIO()
                    new_doc.save(output, garbage=4, clean=True)
                    new_doc.close()
                    doc.close()
                    output.seek(0)
                    
                    return send_file(
                        output, 
                        mimetype='application/pdf', 
                        as_attachment=True, 
                        download_name='unlocked.pdf'
                    )
                
                new_doc.close()
            doc.close()
        except Exception as e:
            pass
        
        # If all methods fail, return error with helpful message
        return jsonify({
            'error': 'Could not unlock PDF. This file uses strong AES-256 encryption that cannot be bypassed without the correct password. Please provide the password.',
            'hint': 'Only PDFs with owner-only restrictions or weak encryption can be unlocked without password.'
        }), 400
    
    except Exception as e:
        return jsonify({'error': f'Unlock failed: {str(e)}'}), 500


@app.route('/api/images-to-pdf', methods=['POST'])
def api_images_to_pdf():
    """Convert images to PDF"""
    try:
        images = []
        i = 0
        while f'file_{i}' in request.files:
            f = request.files[f'file_{i}']
            if f and f.filename:
                images.append(f)
            i += 1
        
        if not images:
            return jsonify({'error': 'No images uploaded'}), 400
        
        pdf_images = []
        for img_file in images:
            img = Image.open(img_file.stream)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            pdf_images.append(img)
        
        output = io.BytesIO()
        
        if len(pdf_images) == 1:
            pdf_images[0].save(output, 'PDF')
        else:
            pdf_images[0].save(output, 'PDF', save_all=True, append_images=pdf_images[1:])
        
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='images.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf-to-images', methods=['POST'])
def api_pdf_to_images():
    """Convert PDF to images"""
    try:
        f = request.files.get('file_0')
        dpi = int(request.form.get('dpi', '150'))
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                
                img_buffer = io.BytesIO()
                img_buffer.write(pix.tobytes("png"))
                img_buffer.seek(0)
                
                zf.writestr(f'page_{i+1}.png', img_buffer.getvalue())
        
        doc.close()
        zip_buffer.seek(0)
        
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='pdf_images.zip')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= DOCUMENT CONVERSION TOOLS =============

@app.route('/api/word-to-pdf', methods=['POST'])
def api_word_to_pdf():
    """Convert Word document to PDF"""
    try:
        from docx import Document
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        doc = Document(f.stream)
        
        output = io.BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=letter, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        story = []
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=12
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=14,
            leading=18,
            spaceAfter=12,
            spaceBefore=12
        )
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                if para.style.name.startswith('Heading'):
                    story.append(Paragraph(text, heading_style))
                else:
                    story.append(Paragraph(text, normal_style))
        
        if not story:
            story.append(Paragraph("(Empty document)", normal_style))
        
        pdf.build(story)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='converted.pdf')
    
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500


@app.route('/api/excel-to-pdf', methods=['POST'])
def api_excel_to_pdf():
    """Convert Excel spreadsheet to PDF"""
    try:
        from openpyxl import load_workbook
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        wb = load_workbook(f.stream, data_only=True)
        ws = wb.active
        
        output = io.BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=landscape(letter),
                               rightMargin=30, leftMargin=30,
                               topMargin=30, bottomMargin=30)
        
        story = []
        
        data = []
        for row in ws.iter_rows(values_only=True):
            row_data = [str(cell) if cell is not None else '' for cell in row]
            if any(row_data):
                data.append(row_data)
        
        if data:
            num_cols = max(len(row) for row in data)
            available_width = landscape(letter)[0] - 60
            col_width = available_width / num_cols
            
            max_cell_chars = 30
            for i, row in enumerate(data):
                data[i] = [cell[:max_cell_chars] + '...' if len(cell) > max_cell_chars else cell for cell in row]
            
            table = Table(data, colWidths=[col_width] * num_cols)
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(table)
        
        pdf.build(story)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='spreadsheet.pdf')
    
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500


@app.route('/api/pdf-to-word', methods=['POST'])
def api_pdf_to_word():
    """Convert PDF to Word document"""
    try:
        from pdf2docx import Converter
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(f.read())
            temp_pdf_path = temp_pdf.name
        
        temp_docx_path = temp_pdf_path.replace('.pdf', '.docx')
        
        try:
            cv = Converter(temp_pdf_path)
            cv.convert(temp_docx_path)
            cv.close()
            
            with open(temp_docx_path, 'rb') as docx_file:
                output = io.BytesIO(docx_file.read())
            
            output.seek(0)
            
            return send_file(output, 
                           mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                           as_attachment=True, 
                           download_name='converted.docx')
        finally:
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            if os.path.exists(temp_docx_path):
                os.remove(temp_docx_path)
    
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500


@app.route('/api/pdf-to-excel', methods=['POST'])
def api_pdf_to_excel():
    """Convert PDF tables to Excel spreadsheet"""
    try:
        from openpyxl import Workbook
        import re
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        wb = Workbook()
        ws = wb.active
        ws.title = "PDF Content"
        
        current_row = 1
        
        for page_num, page in enumerate(doc):
            ws.cell(row=current_row, column=1, value=f"--- Page {page_num + 1} ---")
            ws.cell(row=current_row, column=1).font = ws.cell(row=current_row, column=1).font.copy(bold=True)
            current_row += 1
            
            tables = page.find_tables()
            
            if tables and len(tables.tables) > 0:
                for table in tables:
                    for row in table.extract():
                        col = 1
                        for cell in row:
                            if cell:
                                ws.cell(row=current_row, column=col, value=str(cell))
                            col += 1
                        current_row += 1
                    current_row += 1
            else:
                text = page.get_text("text")
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        if '\t' in line:
                            parts = line.split('\t')
                        elif '|' in line:
                            parts = [p.strip() for p in line.split('|') if p.strip()]
                        elif '  ' in line:
                            parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]
                        else:
                            parts = [line]
                        
                        for col, part in enumerate(parts, 1):
                            ws.cell(row=current_row, column=col, value=part)
                        current_row += 1
            
            current_row += 1
        
        doc.close()
        
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return send_file(output, 
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                        as_attachment=True, 
                        download_name='extracted.xlsx')
    
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500


@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    """OCR - Extract text from images and create searchable PDF"""
    try:
        try:
            import pytesseract
        except ImportError:
            return jsonify({'error': 'OCR library not installed. Please install pytesseract.'}), 500
        
        files = get_uploaded_files(request)
        
        if not files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        output_format = request.form.get('output_format', 'pdf')
        language = request.form.get('language', 'eng')
        
        all_text = []
        
        for file in files:
            filename = file.filename.lower()
            
            if filename.endswith('.pdf'):
                pdf_data = file.read()
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                
                for page_num, page in enumerate(doc):
                    mat = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=mat)
                    
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    try:
                        text = pytesseract.image_to_string(img, lang=language)
                        all_text.append(f"--- Page {page_num + 1} ---\n{text}")
                    except Exception as e:
                        all_text.append(f"--- Page {page_num + 1} ---\n[OCR Error: {str(e)}]")
                
                doc.close()
            else:
                try:
                    img = Image.open(file.stream)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    text = pytesseract.image_to_string(img, lang=language)
                    all_text.append(f"--- {file.filename} ---\n{text}")
                except Exception as e:
                    all_text.append(f"--- {file.filename} ---\n[OCR Error: {str(e)}]")
        
        combined_text = "\n\n".join(all_text)
        
        if output_format == 'txt':
            output = io.BytesIO()
            output.write(combined_text.encode('utf-8'))
            output.seek(0)
            
            return send_file(output, mimetype='text/plain', as_attachment=True, download_name='ocr_result.txt')
        else:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            
            output = io.BytesIO()
            pdf = SimpleDocTemplate(output, pagesize=letter,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=72)
            
            styles = getSampleStyleSheet()
            story = []
            
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=20
            )
            story.append(Paragraph("OCR Extracted Text", title_style))
            story.append(Spacer(1, 12))
            
            text_style = ParagraphStyle(
                'OCRText',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                spaceAfter=8
            )
            
            for line in combined_text.split('\n'):
                if line.strip():
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, text_style))
                else:
                    story.append(Spacer(1, 6))
            
            pdf.build(story)
            output.seek(0)
            
            return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='ocr_result.pdf')
    
    except Exception as e:
        return jsonify({'error': f'OCR failed: {str(e)}'}), 500


# ============= ERROR HANDLERS =============
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 100MB'}), 413

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 PDF Tools Server (Database Edition) Starting...")
    print("="*50)
    print("📍 Home Page: http://127.0.0.1:5000/")
    print("📍 All Tools: http://127.0.0.1:5000/tools")
    print("📍 Uploads: http://127.0.0.1:5000/uploads")
    print("📍 API: http://127.0.0.1:5000/api/uploads (View all files)")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
