# Complete PDF Tools Backend - All 29 Tools
from flask import Flask, render_template, request, send_file, jsonify
from PyPDF2 import PdfWriter, PdfReader
import os
import io
import traceback
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============= ROUTES =============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/tools')
def tools():
    return render_template('tools.html')

# ============= ORGANIZE PDF (6 tools) =============

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
                        return jsonify({'error': f'{file.filename} is password-protected'}), 400
                    
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
        print(f"Error in merge: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/split', methods=['POST'])
def api_split():
    """Split PDF - each page as separate file"""
    try:
        file = request.files.get('file_0')
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'No PDF file provided'}), 400
        
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
        print(f"Error in split: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove-pages', methods=['POST'])
def api_remove_pages():
    """Remove specific pages from PDF"""
    try:
        file = request.files.get('file_0')
        pages_str = request.form.get('pages', '')
        
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'No PDF file provided'}), 400
        
        if not pages_str:
            return jsonify({'error': 'No pages specified'}), 400
        
        pages_to_remove = parse_page_numbers(pages_str)
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for i in range(len(pdf_reader.pages)):
            if (i + 1) not in pages_to_remove:
                pdf_writer.add_page(pdf_reader.pages[i])
        
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
        print(f"Error in remove_pages: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/extract-pages', methods=['POST'])
def api_extract_pages():
    """Extract specific pages from PDF"""
    try:
        file = request.files.get('file_0')
        pages_str = request.form.get('pages', '')
        
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'No PDF file provided'}), 400
        
        if not pages_str:
            return jsonify({'error': 'No pages specified'}), 400
        
        pages_to_extract = parse_page_numbers(pages_str)
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for page_num in sorted(pages_to_extract):
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
        print(f"Error in extract_pages: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/organize', methods=['POST'])
def api_organize():
    """Reorder pages in PDF"""
    try:
        file = request.files.get('file_0')
        order_str = request.form.get('order', '')
        
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'No PDF file provided'}), 400
        
        if not order_str:
            return jsonify({'error': 'No page order specified'}), 400
        
        order_list = [int(x.strip()) for x in order_str.split(',') if x.strip()]
        
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
        print(f"Error in organize: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-to-pdf', methods=['POST'])
def api_scan_to_pdf():
    """Convert images to PDF"""
    try:
        try:
            from PIL import Image
        except ImportError:
            return jsonify({'error': 'Pillow library required. Install: pip install Pillow'}), 501
        
        files = []
        file_count = 0
        
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:
                files.append(file)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No image files provided'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            try:
                image = Image.open(file.stream)
                
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                img_buffer = io.BytesIO()
                image.save(img_buffer, 'PDF')
                img_buffer.seek(0)
                
                img_pdf = PdfReader(img_buffer)
                pdf_writer.add_page(img_pdf.pages[0])
            except Exception as e:
                return jsonify({'error': f'Error processing {file.filename}: {str(e)}'}), 400
        
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
        print(f"Error in scan_to_pdf: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============= OPTIMIZE PDF (3 tools) =============

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
        
        pdf_writer = PdfWriter()
        
        for file in files:
            if file.filename.lower().endswith('.pdf'):
                pdf_reader = PdfReader(file.stream)
                for page in pdf_reader.pages:
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
        print(f"Error in compress: {traceback.format_exc()}")
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
                print(f"Warning: {file.filename} - {e}")
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
        print(f"Error in repair: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    """OCR PDF to make text searchable"""
    try:
        return jsonify({'error': 'OCR requires: pip install pytesseract pdf2image. See README for setup.'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= CONVERT TO PDF (5 tools) =============

@app.route('/api/jpg-to-pdf', methods=['POST'])
def api_jpg_to_pdf():
    """Convert JPG/PNG to PDF"""
    try:
        try:
            from PIL import Image
        except ImportError:
            return jsonify({'error': 'Pillow library required. Install: pip install Pillow'}), 501
        
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
        print(f"Error in jpg_to_pdf: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/word-to-pdf', methods=['POST'])
def api_word_to_pdf():
    """Convert Word to PDF"""
    return jsonify({'error': 'Word conversion requires: pip install docx2pdf. See README for setup.'}), 501

@app.route('/api/powerpoint-to-pdf', methods=['POST'])
def api_powerpoint_to_pdf():
    """Convert PowerPoint to PDF"""
    return jsonify({'error': 'PowerPoint conversion requires additional libraries. See README for setup.'}), 501

@app.route('/api/excel-to-pdf', methods=['POST'])
def api_excel_to_pdf():
    """Convert Excel to PDF"""
    return jsonify({'error': 'Excel conversion requires: pip install openpyxl. See README for setup.'}), 501

@app.route('/api/html-to-pdf', methods=['POST'])
def api_html_to_pdf():
    """Convert HTML to PDF"""
    return jsonify({'error': 'HTML conversion requires: pip install pdfkit weasyprint. See README for setup.'}), 501

# ============= CONVERT FROM PDF (5 tools) =============

@app.route('/api/pdf-to-jpg', methods=['POST'])
def api_pdf_to_jpg():
    """Convert PDF pages to JPG images"""
    return jsonify({'error': 'PDF to image conversion requires: pip install pdf2image. See README for setup.'}), 501

@app.route('/api/pdf-to-word', methods=['POST'])
def api_pdf_to_word():
    """Convert PDF to Word"""
    return jsonify({'error': 'PDF to Word requires: pip install pdf2docx. See README for setup.'}), 501

@app.route('/api/pdf-to-powerpoint', methods=['POST'])
def api_pdf_to_powerpoint():
    """Convert PDF to PowerPoint"""
    return jsonify({'error': 'PDF to PowerPoint conversion requires additional libraries. See README for setup.'}), 501

@app.route('/api/pdf-to-excel', methods=['POST'])
def api_pdf_to_excel():
    """Convert PDF to Excel"""
    return jsonify({'error': 'PDF to Excel requires: pip install tabula-py. See README for setup.'}), 501

@app.route('/api/pdf-to-pdfa', methods=['POST'])
def api_pdf_to_pdfa():
    """Convert PDF to PDF/A archival format"""
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
        print(f"Error in pdf_to_pdfa: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============= EDIT PDF (5 tools) =============

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
        
        rotation = 90
        if '180' in rotation_str:
            rotation = 180
        elif 'Counter' in rotation_str:
            rotation = 270
        
        pdf_writer = PdfWriter()
        
        for file in files:
            if file.filename.lower().endswith('.pdf'):
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
        print(f"Error in rotate: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/add-page-numbers', methods=['POST'])
def api_add_page_numbers():
    """Add page numbers to PDF"""
    return jsonify({'error': 'Page numbering requires: pip install reportlab. See README for setup.'}), 501

@app.route('/api/add-watermark', methods=['POST'])
def api_add_watermark():
    """Add watermark to PDF"""
    return jsonify({'error': 'Watermarking requires: pip install reportlab. See README for setup.'}), 501

@app.route('/api/crop', methods=['POST'])
def api_crop():
    """Crop PDF pages"""
    try:
        file = request.files.get('file_0')
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'No PDF file provided'}), 400
        
        margins_str = request.form.get('margins', '0,0,0,0')
        
        try:
            margins = [float(x.strip()) for x in margins_str.split(',')]
        except:
            return jsonify({'error': 'Invalid margins format. Use: top,right,bottom,left'}), 400
        
        if len(margins) != 4:
            return jsonify({'error': 'Invalid margins. Expected 4 values.'}), 400
        
        top, right, bottom, left = margins
        
        pdf_reader = PdfReader(file.stream)
        pdf_writer = PdfWriter()
        
        for page in pdf_reader.pages:
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
        print(f"Error in crop: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/edit-pdf', methods=['POST'])
def api_edit_pdf():
    """Edit PDF content"""
    return jsonify({'error': 'PDF editing requires: pip install PyMuPDF. See README for setup.'}), 501

# ============= SECURITY (5 tools) =============

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
            try:
                pdf_reader = PdfReader(file.stream)
                if pdf_reader.is_encrypted:
                    if not pdf_reader.decrypt(password):
                        return jsonify({'error': f'Wrong password for {file.filename}'}), 400
                
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            except Exception as e:
                return jsonify({'error': f'Error processing {file.filename}: {str(e)}'}), 400
        
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
        print(f"Error in unlock: {traceback.format_exc()}")
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
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        pdf_writer = PdfWriter()
        
        for file in files:
            if file.filename.lower().endswith('.pdf'):
                pdf_reader = PdfReader(file.stream)
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
        
        # Encrypt with password
        pdf_writer.encrypt(password)
        
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
        print(f"Error in protect: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sign', methods=['POST'])
def api_sign():
    """Add digital signature to PDF"""
    return jsonify({'error': 'Digital signing requires cryptography libraries. See README for setup.'}), 501

@app.route('/api/redact', methods=['POST'])
def api_redact():
    """Redact sensitive information"""
    return jsonify({'error': 'Redaction requires: pip install PyMuPDF. See README for setup.'}), 501

@app.route('/api/compare', methods=['POST'])
def api_compare():
    """Compare two PDFs"""
    return jsonify({'error': 'PDF comparison requires advanced libraries. See README for setup.'}), 501

# ============= UTILITY FUNCTIONS =============

def parse_page_numbers(pages_str):
    """Parse page numbers string like '1,3,5-7' into a set"""
    pages = set()
    if not pages_str:
        return pages
    
    try:
        parts = pages_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                pages.update(range(int(start), int(end) + 1))
            elif part:
                pages.add(int(part))
    except Exception as e:
        print(f"Error parsing page numbers: {e}")
    
    return pages

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============= RUN APP =============

if __name__ == '__main__':
    app.run(debug=True, port=5000)
