# app.py
from flask import Flask, render_template, request, send_file, jsonify
from PyPDF2 import PdfWriter, PdfReader
import os
from werkzeug.utils import secure_filename
import io
import traceback
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Create temp folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview_pdf():
    """Generate preview of uploaded PDF - returns entire PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid PDF file'}), 400
        
        # Read the entire PDF file
        file_bytes = file.read()
        
        # Validate it's a PDF by trying to read it
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        
        if pdf_reader.is_encrypted:
            return jsonify({'error': 'Cannot preview encrypted PDF'}), 400
        
        if len(pdf_reader.pages) == 0:
            return jsonify({'error': 'PDF has no pages'}), 400
        
        # Return entire PDF as base64 for embedding
        pdf_base64 = base64.b64encode(file_bytes).decode('utf-8')
        
        return jsonify({
            'preview': pdf_base64,
            'pageCount': len(pdf_reader.pages)
        })
    
    except Exception as e:
        print(f"Error in preview_pdf: {traceback.format_exc()}")
        return jsonify({'error': f'Preview error: {str(e)}'}), 500

@app.route('/merge', methods=['POST'])
def merge_pdfs():
    try:
        # Get files in order
        files = []
        orientations = []  # Track rotation for each file
        file_count = 0
        
        # Collect files in order (file_0, file_1, etc.)
        while f'file_{file_count}' in request.files:
            file = request.files[f'file_{file_count}']
            if file and file.filename:  # Ensure file exists
                files.append(file)
                # Get rotation value (default 0)
                rotation = request.form.get(f'rotation_{file_count}', '0')
                try:
                    orientations.append(int(rotation))
                except:
                    orientations.append(0)
            file_count += 1
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        if len(files) > 10:
            return jsonify({'error': 'Maximum 10 files allowed'}), 400
        
        # Merge PDFs
        pdf_writer = PdfWriter()
        merged_count = 0
        
        for idx, file in enumerate(files):
            if file and file.filename.lower().endswith('.pdf'):
                try:
                    # Read PDF from uploaded file
                    pdf_reader = PdfReader(file.stream)
                    
                    # Check if PDF is encrypted
                    if pdf_reader.is_encrypted:
                        return jsonify({'error': f'File {file.filename} is password-protected'}), 400
                    
                    # Add all pages with rotation, preserving original page properties
                    rotation = orientations[idx] if idx < len(orientations) else 0
                    for page in pdf_reader.pages:
                        # Create a new page with same media box to preserve spacing
                        page_copy = page
                        
                        # Apply rotation if specified (rotation is cumulative)
                        if rotation != 0:
                            page_copy.rotate(rotation)
                        
                        # Add page to writer - this preserves all formatting, spacing, and styling
                        pdf_writer.add_page(page_copy)
                    
                    merged_count += 1
                    
                except Exception as pdf_error:
                    return jsonify({
                        'error': f'Error reading {file.filename}: {str(pdf_error)}'
                    }), 400
            else:
                return jsonify({'error': f'Invalid file: {file.filename}'}), 400
        
        if merged_count == 0:
            return jsonify({'error': 'No valid PDFs to merge'}), 400
        
        # Write to bytes buffer
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        # Return file as download
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='merged_pdfs.pdf'
        )
    
    except Exception as e:
        print(f"Error in merge_pdfs: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
