import os
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, session, jsonify, flash
from models import db, User, File
from werkzeug.utils import secure_filename
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect, CSRFError

<<<<<<< HEAD
# ── Vercel: /tmp is the only writable directory in the serverless runtime ──
os.makedirs("/tmp", exist_ok=True)
os.makedirs("/tmp/uploads", exist_ok=True)

# Create app with /tmp as the instance path so Flask never touches /var/task/instance
app = Flask(__name__, instance_path="/tmp")

# Configure app BEFORE importing dotenv or doing anything else
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# ── Database: use DATABASE_URL (PostgreSQL on production) or SQLite in /tmp ──
# NOTE: four slashes (sqlite:////tmp/...) = absolute path required for /tmp
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:////tmp/database.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── SQLAlchemy engine options: pool_pre_ping avoids stale connections ──
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True
}

# ── Upload folder: must be writable; /tmp/uploads on Vercel ──
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
=======
# Create app first
app = Flask(__name__)

# Configure app BEFORE importing dotenv or doing anything else
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'  # ← This must come FIRST!
>>>>>>> 5dedea9936bf3cd72f5c44f2d1f36ad00a819e39

# Now try to import dotenv (but make it optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, using default configuration")

# Now initialize other components
csrf = CSRFProtect(app)
db.init_app(app)

# Get base URL (after potential dotenv load)
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8080')

<<<<<<< HEAD
# Create tables and ensure upload folder exists
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("✅ Database and tables created successfully!")
    print(f"   DB  → {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"   Uploads → {app.config['UPLOAD_FOLDER']}")
=======
# Create tables and upload folder
with app.app_context():
    db.create_all()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    print("✅ Database and tables created successfully!")
>>>>>>> 5dedea9936bf3cd72f5c44f2d1f36ad00a819e39

@app.route('/')
def index():
    return render_template('index.html')

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            confirmation = request.form.get('confirmation')

            # Validate inputs
            if not username:
                flash('Username is required!', 'error')
                return render_template('register.html')

            if not password:
                flash('Password is required!', 'error')
                return render_template('register.html')

            if password != confirmation:
                flash('Passwords do not match!', 'error')
                return render_template('register.html')

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists!', 'error')
                return render_template('register.html')

            # Create new user
            new_user = User(username=username)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()  # Commit to get the user ID

            # NOW set the session after successful commit
            session['user_id'] = new_user.id
            session['username'] = new_user.username

            flash('Registration successful! Welcome to ShareXpress.', 'success')
            return redirect(url_for('dashboard') + '#upload')  # ← CHANGED: Go to upload section

        except Exception as e:
            db.session.rollback()  # Important: rollback on error
            print(f"Registration error: {str(e)}")
            flash('Registration failed due to a server error. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')

# Login Route - redirect to dashboard#upload section
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password!', 'error')
            return render_template('login.html')

        # Find user
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard') + '#upload')  # ← ADD #upload anchor
        else:
            flash('Invalid username or password!', 'error')
            return render_template('login.html')

    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Dashboard Route (Protected)
@app.route('/dashboard')
def dashboard():
    try:
        if 'user_id' not in session:
            flash('Please log in to access the dashboard.', 'error')
            return redirect(url_for('login'))

        # Verify user still exists in database
        user = User.query.get(session['user_id'])
        if not user:
            flash('User account not found. Please register again.', 'error')
            session.clear()  # Clear invalid session
            return redirect(url_for('register'))

        # Get user's files
        user_files = File.query.filter_by(user_id=session['user_id']).all()

        return render_template('dashboard.html',
                             username=session['username'],
                             files=user_files,
                             BASE_URL=BASE_URL)

    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        flash('An error occurred while loading the dashboard.', 'error')
        return redirect(url_for('index'))

# API Login endpoint
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        # Check if request contains JSON
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # For API, we'll use session-based auth like the web app
            session['user_id'] = user.id
            session['username'] = user.username
            return jsonify({
                'message': 'Login successful',
                'user_id': user.id,
                'username': user.username
            }), 200
        else:
            return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        print(f"API login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# API Upload endpoint
@app.route('/api/upload', methods=['POST'])
def api_upload():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Generate unique filenames and codes
        original_filename = secure_filename(file.filename)
        file_extension = os.path.splitext(original_filename)[1]
        stored_filename = f"{uuid.uuid4().hex}{file_extension}"
        download_code = str(uuid.uuid4().hex)[:10]

        # Save the file
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], stored_filename))

        # Create database record
        new_file = File(
            original_filename=original_filename,
            stored_filename=stored_filename,
            download_code=download_code,
            user_id=session['user_id']
        )
        db.session.add(new_file)
        db.session.commit()

        # Generate the full download URL
        download_url = f"{BASE_URL}/download/{download_code}"

        return jsonify({
            'message': 'File uploaded successfully',
            'download_url': download_url,
            'file_id': new_file.id
        }), 200

    except Exception as e:
        print(f"API upload error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# API List files endpoint
@app.route('/api/files', methods=['GET'])
def api_files():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        user_files = File.query.filter_by(user_id=session['user_id']).all()

        files_data = []
        for file in user_files:
            files_data.append({
                'id': file.id,
                'original_filename': file.original_filename,
                'upload_date': file.upload_date.strftime('%Y-%m-%d %H:%M'),
                'download_url': f"{BASE_URL}/download/{file.download_code}"
            })

        return jsonify({'files': files_data}), 200

    except Exception as e:
        print(f"API files error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        flash('Please log in to upload files.', 'error')
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['file']

    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))

    if file:
        try:
            # Generate unique filenames and codes
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1]
            stored_filename = f"{uuid.uuid4().hex}{file_extension}"
            download_code = str(uuid.uuid4().hex)[:10]  # Short code for the URL

            # Save the file
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], stored_filename))

            # Create database record
            new_file = File(
                original_filename=original_filename,
                stored_filename=stored_filename,
                download_code=download_code,
                user_id=session['user_id']
            )
            db.session.add(new_file)
            db.session.commit()

            # Generate the full download URL
            download_url = f"{BASE_URL}/download/{download_code}"
            flash(f'File uploaded successfully! Download URL: {download_url}', 'success')

        except Exception as e:
            flash('Error uploading file. Please try again.', 'error')
            # You might want to log the error: print(f"Upload error: {e}")

    return redirect(url_for('dashboard'))

@app.route('/download/<download_code>')
def download_file(download_code):
    file_record = File.query.filter_by(download_code=download_code).first()

    if not file_record:
        flash('File not found.', 'error')
        return redirect(url_for('index'))

    # Increment download count (optional - you can add this field to your File model later)
    # file_record.download_count += 1
    # db.session.commit()

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_record.stored_filename)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('index'))

    return send_file(file_path, as_attachment=True, download_name=file_record.original_filename)

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session:
        flash('Please log in to manage files.', 'error')
        return redirect(url_for('login'))

    try:
        # Find the file and verify ownership
        file_to_delete = File.query.filter_by(id=file_id, user_id=session['user_id']).first()

        if not file_to_delete:
            flash('File not found or you do not have permission to delete it.', 'error')
            return redirect(url_for('dashboard'))

        # Remove the physical file from uploads folder
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_to_delete.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove the database record
        db.session.delete(file_to_delete)
        db.session.commit()

        flash('File deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        print(f"Delete error: {str(e)}")
        flash('Error deleting file. Please try again.', 'error')

    return redirect(url_for('dashboard'))


@app.route('/debug/db-status')
def debug_db_status():
    """Check if database is working"""
    try:
        with app.app_context():
            # Define basedir here
            basedir = os.path.abspath(os.path.dirname(__file__))

            # Check if database file exists
            db_exists = os.path.exists(os.path.join(basedir, "database.db"))

            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # Try a simple query
            user_count = User.query.count()

            return f"""
            <h1>Database Status</h1>
            <p>Database file exists: {db_exists}</p>
            <p>Tables: {tables}</p>
            <p>Users in database: {user_count}</p>
            <p>Database path: {app.config['SQLALCHEMY_DATABASE_URI']}</p>
            <p>Current directory: {basedir}</p>
            """
    except Exception as e:
        return f"❌ Database error: {str(e)}"


@app.route('/debug/session')
def debug_session():
    """Debug session data"""
    return f"""
    <h1>Session Data</h1>
    <pre>user_id: {session.get('user_id', 'NOT SET')}</pre>
    <pre>username: {session.get('username', 'NOT SET')}</pre>
    <pre>Session keys: {list(session.keys())}</pre>
    """

@app.route('/debug/check-user/<user_id>')
def debug_check_user(user_id):
    """Check if user exists in database"""
    user = User.query.get(user_id)
    if user:
        return f"User exists: {user.username}"
    else:
        return "User not found in database"

# Exempt API routes from CSRF protection
csrf.exempt(api_login)
csrf.exempt(api_upload)
csrf.exempt(api_files)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return jsonify({'error': 'CSRF token missing or invalid'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)



