"""
PDF Tools Backend - Complete Implementation
All tools working with proper error handling
"""

from flask import Flask, render_template, request, jsonify, send_file
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
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============= FILE CLEANUP SYSTEM =============
class FileCleanupManager:
    def __init__(self, expiry_hours=1):
        self.expiry_hours = expiry_hours
        self.metadata_file = os.path.join(UPLOAD_FOLDER, 'file_metadata.json')
        self.running = False
        self._load_metadata()
    
    def _load_metadata(self):
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except:
            self.metadata = {}
    
    def _save_metadata(self):
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except:
            pass
    
    def track_file(self, filename, filepath):
        self.metadata[filename] = {
            'path': filepath,
            'uploaded_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=self.expiry_hours)).isoformat()
        }
        self._save_metadata()
    
    def cleanup_expired(self):
        now = datetime.now()
        to_delete = []
        
        for filename, info in list(self.metadata.items()):
            try:
                expires_at = datetime.fromisoformat(info['expires_at'])
                if now > expires_at:
                    filepath = info.get('path', '')
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"🗑️ Deleted expired file: {filename}")
                    to_delete.append(filename)
            except:
                to_delete.append(filename)
        
        for filename in to_delete:
            del self.metadata[filename]
        
        if to_delete:
            self._save_metadata()
    
    def start_background_cleanup(self, interval=60):
        self.running = True
        def cleanup_loop():
            while self.running:
                self.cleanup_expired()
                time.sleep(interval)
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        print("✅ Background file cleanup started (runs every 60 seconds)")

cleanup_manager = FileCleanupManager(expiry_hours=1)
cleanup_manager.start_background_cleanup(interval=60)
print("✅ File tracking and auto-deletion system initialized (1-hour expiry)")

# ============= ROUTES =============
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tools')
def tools():
    return render_template('tools_working.html')

# ============= PDF TOOLS API =============

@app.route('/api/merge', methods=['POST'])
def api_merge():
    """Merge multiple PDFs into one"""
    try:
        files = []
        i = 0
        while f'file_{i}' in request.files:
            f = request.files[f'file_{i}']
            if f and f.filename:
                files.append(f)
            i += 1
        
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
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='extracted_pages.pdf')
    
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
        
        # Parse page order
        new_order = [int(x.strip()) for x in order_str.split(',')]
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for page_num in new_order:
            if 1 <= page_num <= len(reader.pages):
                writer.add_page(reader.pages[page_num - 1])
        
        if len(writer.pages) == 0:
            return jsonify({'error': 'Invalid page order'}), 400
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='reordered.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compress', methods=['POST'])
def api_compress():
    """Compress PDF to reduce file size"""
    try:
        f = request.files.get('file_0')
        quality = request.form.get('quality', 'Medium')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Read with PyMuPDF for better compression
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Compression settings based on quality
        if 'High' in quality or 'Smallest' in quality:
            garbage = 4
            deflate = True
            clean = True
        elif 'Low' in quality or 'Best' in quality:
            garbage = 1
            deflate = False
            clean = False
        else:
            garbage = 2
            deflate = True
            clean = False
        
        output = io.BytesIO()
        doc.save(output, garbage=garbage, deflate=deflate, clean=clean)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='compressed.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/repair', methods=['POST'])
def api_repair():
    """Repair corrupted PDF"""
    try:
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        pdf_data = f.read()
        
        # Use PyMuPDF to repair
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        output = io.BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='repaired.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    """Rotate PDF pages"""
    try:
        f = request.files.get('file_0')
        rotation_str = request.form.get('rotation', '90° Clockwise')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Determine rotation angle
        if '180' in rotation_str:
            rotation = 180
        elif 'Counter' in rotation_str:
            rotation = -90
        else:
            rotation = 90
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='rotated.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/crop', methods=['POST'])
def api_crop():
    """Crop PDF margins"""
    try:
        f = request.files.get('file_0')
        margins_str = request.form.get('margins', '10,10,10,10')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Parse margins (top, right, bottom, left in mm)
        margins = [float(x.strip()) for x in margins_str.split(',')]
        if len(margins) != 4:
            margins = [10, 10, 10, 10]
        
        # Convert mm to points (1 mm = 2.83465 points)
        top, right, bottom, left = [m * 2.83465 for m in margins]
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for page in reader.pages:
            # Get current dimensions
            media_box = page.mediabox
            
            # Crop by adjusting the crop box
            page.cropbox.lower_left = (media_box.lower_left[0] + left, media_box.lower_left[1] + bottom)
            page.cropbox.upper_right = (media_box.upper_right[0] - right, media_box.upper_right[1] - top)
            
            writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='cropped.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watermark', methods=['POST'])
def api_watermark():
    """Add text watermark to PDF"""
    try:
        f = request.files.get('file_0')
        text = request.form.get('text', 'WATERMARK')
        opacity = int(request.form.get('opacity', '25')) / 100.0
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not text:
            return jsonify({'error': 'Please provide watermark text'}), 400
        
        # Read original PDF with PyMuPDF
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        for page in doc:
            rect = page.rect
            # Add diagonal text watermark
            text_length = fitz.get_text_length(text, fontsize=60, fontname="helv")
            
            # Center the watermark
            x = (rect.width - text_length) / 2
            y = rect.height / 2
            
            # Create text with opacity
            page.insert_text(
                (x, y),
                text,
                fontsize=60,
                fontname="helv",
                color=(0.5, 0.5, 0.5),
                rotate=45,
                overlay=True,
                fill_opacity=opacity
            )
        
        output = io.BytesIO()
        doc.save(output)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='watermarked.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/page-numbers', methods=['POST'])
def api_page_numbers():
    """Add page numbers to PDF"""
    try:
        f = request.files.get('file_0')
        position = request.form.get('position', 'Bottom Center')
        start_num = int(request.form.get('start', '1'))
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Read with PyMuPDF
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        for i, page in enumerate(doc):
            rect = page.rect
            page_num = start_num + i
            text = str(page_num)
            
            # Determine position
            if 'Bottom' in position:
                y = rect.height - 30
            else:
                y = 30
            
            if 'Right' in position:
                x = rect.width - 50
            elif 'Left' in position:
                x = 50
            else:  # Center
                x = rect.width / 2
            
            page.insert_text(
                (x, y),
                text,
                fontsize=12,
                fontname="helv",
                color=(0, 0, 0)
            )
        
        output = io.BytesIO()
        doc.save(output)
        doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='numbered.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/protect', methods=['POST'])
def api_protect():
    """Add password protection to PDF"""
    try:
        f = request.files.get('file_0')
        password = request.form.get('password', '')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        if not password:
            return jsonify({'error': 'Please provide a password'}), 400
        
        reader = PdfReader(f.stream)
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        writer.encrypt(password)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='protected.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/unlock', methods=['POST'])
def api_unlock():
    """Remove password from PDF"""
    try:
        f = request.files.get('file_0')
        password = request.form.get('password', '')
        
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        reader = PdfReader(f.stream)
        
        if reader.is_encrypted:
            if not reader.decrypt(password):
                return jsonify({'error': 'Incorrect password'}), 400
        
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='unlocked.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= DOCUMENT CONVERSION TOOLS =============

@app.route('/api/word-to-pdf', methods=['POST'])
def api_word_to_pdf():
    """Convert Word document to PDF"""
    try:
        from docx import Document
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Read the Word document
        doc = Document(f.stream)
        
        # Create PDF
        output = io.BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=letter, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Add a custom style for normal text
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
                # Escape special characters for reportlab
                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                # Check if it's a heading
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
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        
        f = request.files.get('file_0')
        if not f:
            return jsonify({'error': 'No file uploaded'}), 400
        
        # Read Excel file
        wb = load_workbook(f.stream, data_only=True)
        ws = wb.active
        
        # Create PDF
        output = io.BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=landscape(letter),
                               rightMargin=30, leftMargin=30,
                               topMargin=30, bottomMargin=30)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Get data from worksheet
        data = []
        for row in ws.iter_rows(values_only=True):
            row_data = [str(cell) if cell is not None else '' for cell in row]
            if any(row_data):  # Skip empty rows
                data.append(row_data)
        
        if not data:
            story.append(Paragraph("(Empty spreadsheet)", styles['Normal']))
        else:
            # Calculate column widths
            num_cols = max(len(row) for row in data)
            available_width = landscape(letter)[0] - 60
            col_width = available_width / num_cols
            
            # Truncate cell content if too long
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
        
        # Save PDF to temp file (pdf2docx requires file path)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(f.read())
            temp_pdf_path = temp_pdf.name
        
        # Create temp output file
        temp_docx_path = temp_pdf_path.replace('.pdf', '.docx')
        
        try:
            # Convert PDF to Word
            cv = Converter(temp_pdf_path)
            cv.convert(temp_docx_path)
            cv.close()
            
            # Read the converted file
            with open(temp_docx_path, 'rb') as docx_file:
                output = io.BytesIO(docx_file.read())
            
            output.seek(0)
            
            return send_file(output, 
                           mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                           as_attachment=True, 
                           download_name='converted.docx')
        finally:
            # Clean up temp files
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
        
        # Read PDF and extract text using PyMuPDF
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Create Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "PDF Content"
        
        current_row = 1
        
        for page_num, page in enumerate(doc):
            # Add page header
            ws.cell(row=current_row, column=1, value=f"--- Page {page_num + 1} ---")
            ws.cell(row=current_row, column=1).font = ws.cell(row=current_row, column=1).font.copy(bold=True)
            current_row += 1
            
            # Try to extract tables
            tables = page.find_tables()
            
            if tables and len(tables.tables) > 0:
                for table in tables:
                    # Extract table data
                    for row in table.extract():
                        col = 1
                        for cell in row:
                            if cell:
                                ws.cell(row=current_row, column=col, value=str(cell))
                            col += 1
                        current_row += 1
                    current_row += 1  # Add spacing between tables
            else:
                # If no tables found, extract text line by line
                text = page.get_text("text")
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        # Try to split by common delimiters
                        if '\t' in line:
                            parts = line.split('\t')
                        elif '|' in line:
                            parts = [p.strip() for p in line.split('|') if p.strip()]
                        elif '  ' in line:  # Multiple spaces
                            parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]
                        else:
                            parts = [line]
                        
                        for col, part in enumerate(parts, 1):
                            ws.cell(row=current_row, column=col, value=part)
                        current_row += 1
            
            current_row += 1  # Add spacing between pages
        
        doc.close()
        
        # Auto-adjust column widths
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
        # Check if pytesseract and tesseract are available
        try:
            import pytesseract
        except ImportError:
            return jsonify({'error': 'OCR library not installed. Please install pytesseract.'}), 500
        
        files = []
        i = 0
        while f'file_{i}' in request.files:
            f = request.files[f'file_{i}']
            if f and f.filename:
                files.append(f)
            i += 1
        
        if not files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        output_format = request.form.get('output_format', 'pdf')
        language = request.form.get('language', 'eng')
        
        all_text = []
        
        for file in files:
            filename = file.filename.lower()
            
            if filename.endswith('.pdf'):
                # Extract images from PDF and OCR them
                pdf_data = file.read()
                doc = fitz.open(stream=pdf_data, filetype="pdf")
                
                for page_num, page in enumerate(doc):
                    # Get page as image
                    mat = fitz.Matrix(2, 2)  # 2x resolution for better OCR
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Convert to PIL Image
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # OCR the image
                    try:
                        text = pytesseract.image_to_string(img, lang=language)
                        all_text.append(f"--- Page {page_num + 1} ---\n{text}")
                    except Exception as e:
                        all_text.append(f"--- Page {page_num + 1} ---\n[OCR Error: {str(e)}]")
                
                doc.close()
            else:
                # Direct image OCR
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
            # Return as text file
            output = io.BytesIO()
            output.write(combined_text.encode('utf-8'))
            output.seek(0)
            
            return send_file(output, mimetype='text/plain', as_attachment=True, download_name='ocr_result.txt')
        else:
            # Create PDF with extracted text
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            
            output = io.BytesIO()
            pdf = SimpleDocTemplate(output, pagesize=letter,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=72)
            
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=20
            )
            story.append(Paragraph("OCR Extracted Text", title_style))
            story.append(Spacer(1, 12))
            
            # Content
            text_style = ParagraphStyle(
                'OCRText',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                spaceAfter=8
            )
            
            # Process text, escape special characters
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
        
        # Convert images to PDF using Pillow
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
        
        # Use PyMuPDF to convert
        pdf_data = f.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                # Render page to image
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


# ============= ORIGINAL MERGE ENDPOINT (for index.html) =============
@app.route('/merge', methods=['POST'])
def merge_pdfs():
    """Original merge endpoint for the home page"""
    try:
        files = request.files.getlist('pdfs')
        
        if not files or len(files) < 2:
            return jsonify({'error': 'Please upload at least 2 PDF files'}), 400
        
        writer = PdfWriter()
        
        for f in files:
            reader = PdfReader(f.stream)
            for page in reader.pages:
                writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='merged.pdf')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 PDF Tools Server Starting...")
    print("="*50)
    print("📍 Home Page: http://127.0.0.1:5000/")
    print("📍 All Tools: http://127.0.0.1:5000/tools")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
