import os
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, send_file, render_template, redirect, url_for, abort, flash, session
from werkzeug.utils import secure_filename


class FileShareApp:
    def __init__(self, upload_folder='uploads', max_file_size=16 * 1024 * 1024):
        self.app = Flask(__name__)

        # Set a secret key for flash messages and potential future sessions
        self.app.secret_key = os.urandom(24)

        self.upload_folder = upload_folder
        self.max_file_size = max_file_size

        # Create folders
        os.makedirs(upload_folder, exist_ok=True)

        # Configure Flask app
        self.app.config['UPLOAD_FOLDER'] = upload_folder
        self.app.config['MAX_CONTENT_LENGTH'] = max_file_size

        # Dictionary to store shared link info
        self.shared_links = {}

        # Setup routes
        self.setup_routes()

    def setup_routes(self):
        """Configure Flask routes for the application"""
        self.app.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.app.add_url_rule('/upload', 'upload', self.upload, methods=['POST'])
        self.app.add_url_rule('/download/<filename>', 'download', self.download, methods=['GET'])
        self.app.add_url_rule('/delete/<filename>', 'delete_file', self.delete_file, methods=['GET', 'POST'])
        self.app.add_url_rule('/list', 'list_files', self.list_files, methods=['GET'])
        self.app.add_url_rule('/share/<filename>', 'share_file', self.share_file, methods=['GET'])
        self.app.add_url_rule('/shared/<share_id>', 'shared_download', self.shared_download, methods=['GET'])

    def index(self):
        """Render the main upload page"""
        return render_template('index.html')

    def upload(self):
        """Handle file uploads"""
        if 'file' not in request.files:
            return render_template('index.html', error='No file part'), 400

        file = request.files['file']

        if file.filename == '':
            return render_template('index.html', error='No selected file'), 400

        if file:
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > self.max_file_size:
                return render_template('index.html',
                                       error=f'File too large. Max size is {self.max_file_size / (1024 * 1024)}MB'
                                       ), 400

            # Generate a secure filename
            filename = self._generate_unique_filename(file.filename)
            filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)

            # Save the file
            file.save(filepath)

            # Flash success message
            flash(f'File {filename} uploaded successfully!', 'success')

            return redirect(url_for('list_files'))

    def download(self, filename):
        """Handle direct file downloads"""
        try:
            return send_file(
                os.path.join(self.app.config['UPLOAD_FOLDER'], filename),
                as_attachment=True
            )
        except FileNotFoundError:
            flash('File not found', 'error')
            return redirect(url_for('list_files'))

    def delete_file(self, filename):
        """Handle file deletion"""
        filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)

        # Verify file exists
        if not os.path.exists(filepath):
            flash('File not found', 'error')
            return redirect(url_for('list_files'))

        try:
            # Remove the file
            os.remove(filepath)

            # Flash success message
            flash(f'File {filename} deleted successfully!', 'success')
        except Exception as e:
            # Handle any errors during deletion
            flash(f'Error deleting file: {str(e)}', 'error')

        return redirect(url_for('list_files'))

    def share_file(self, filename):
        """Generate a temporary sharing link for a file"""
        # Verify file exists
        filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            flash('File not found', 'error')
            return redirect(url_for('list_files'))

        # Generate unique share ID
        share_id = str(uuid.uuid4())

        # Store sharing information
        self.shared_links[share_id] = {
            'filename': filename,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(days=7)  # Link expires in 7 days
        }

        # Generate shareable link
        share_link = url_for('shared_download', share_id=share_id, _external=True)

        return render_template('share.html',
                               filename=filename,
                               share_link=share_link,
                               expiration_days=7
                               )

    def shared_download(self, share_id):
        """Handle downloads via shared link"""
        # Check if share link exists and is valid
        if share_id not in self.shared_links:
            abort(404, description="Invalid or expired sharing link")

        link_info = self.shared_links[share_id]

        # Check if link has expired
        if datetime.now() > link_info['expires_at']:
            del self.shared_links[share_id]
            abort(410, description="Sharing link has expired")

        # Download the file
        filename = link_info['filename']
        filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)

        try:
            return send_file(filepath, as_attachment=True)
        except FileNotFoundError:
            abort(404, description="File not found")

    def list_files(self):
        """List all uploaded files"""
        files = os.listdir(self.app.config['UPLOAD_FOLDER'])
        file_details = []
        for filename in files:
            filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], filename)
            file_size = os.path.getsize(filepath) / 1024  # size in KB
            file_details.append({
                'name': filename,
                'size': f"{file_size:.2f} KB"
            })
        return render_template('files.html', files=file_details)

    def _generate_unique_filename(self, original_filename):
        """Generate a unique filename to prevent overwriting"""
        # Get file extension
        name, ext = os.path.splitext(original_filename)

        # Create a hash of the filename and timestamp
        hash_object = hashlib.md5(f"{original_filename}{os.urandom(32)}".encode())
        unique_hash = hash_object.hexdigest()[:10]

        return f"{name}_{unique_hash}{ext}"

    def run(self, debug=True, host='0.0.0.0', port=5000):
        """Run the Flask application"""
        self.app.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    file_share_app = FileShareApp()
    file_share_app.run()
