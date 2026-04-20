import os
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, session, jsonify, flash
from models import db, User, File
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect, CSRFError

# Now try to import dotenv (but make it optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[+] Environment variables loaded from .env file")
except ImportError:
    print("[!] python-dotenv not installed, using default configuration")

# ── Vercel: /tmp is the only writable directory in the serverless runtime ──
temp_dir = os.path.abspath("/tmp")
os.makedirs(temp_dir, exist_ok=True)
os.makedirs(os.path.join(temp_dir, "uploads"), exist_ok=True)

# Create app with /tmp as the instance path so Flask never touches /var/task/instance
app = Flask(__name__, instance_path=temp_dir)

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT', 'my_precious_salt')

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'notifications@sharexpress.com')

mail = Mail(app)
ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])

def send_email(subject, recipients, html_template, **template_kwargs):
    """Helper function to send emails using Flask-Mail."""
    try:
        html = render_template(html_template, **template_kwargs)
        msg = Message(subject, recipients=recipients, html=html)
        mail.send(msg)
        return True
    except Exception as e:
        import traceback
        print(f"\n[!] MAIL ERROR: {e}")
        print(traceback.format_exc())
        # In development/local mode, we might want to still provide the URL for testing
        if 'verification_url' in template_kwargs:
            print(f"DEBUG: Verification Link -> {template_kwargs['verification_url']}")
        if 'reset_url' in template_kwargs:
            print(f"DEBUG: Password Reset Link -> {template_kwargs['reset_url']}")
        return False

# ── Database: use DATABASE_URL (PostgreSQL on production) or SQLite in /tmp ──
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///database.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── SQLAlchemy engine options: pool_pre_ping avoids stale connections ──
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True
}

# ── Upload folder: must be writable; /tmp/uploads on Vercel ──
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', os.path.join(temp_dir, "uploads"))
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 104857600))  # Default 100MB

# ── Allowed extensions ──
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'txt,pdf,png,jpg,jpeg,gif,doc,docx,zip,rar,7z,tar,gz').split(','))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Now initialize other components
csrf = CSRFProtect(app)
db.init_app(app)

# Get base URL (after potential dotenv load)
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8080')

# Create tables and ensure upload folder exists
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("[+] Database and tables created successfully!")
    print(f"   DB  -> {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"   Uploads -> {app.config['UPLOAD_FOLDER']}")


@app.route('/')
def index():
    return render_template('index.html')

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirmation = request.form.get('confirmation')

            # Validate inputs
            if not username or not email or not password:
                flash('All fields are required!', 'error')
                return render_template('register.html')

            if password != confirmation:
                flash('Passwords do not match!', 'error')
                return render_template('register.html')

            # Check if username or email already exists
            user_by_username = User.query.filter_by(username=username).first()
            if user_by_username:
                flash('Username already exists!', 'error')
                return render_template('register.html')
            
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                if not existing_user.is_verified:
                    # Resend verification if already registered but not verified
                    token = ts.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])
                    verification_url = url_for('verify_email', token=token, _external=True)
                    
                    send_email(
                        "Please confirm your email - ShareXpress",
                        [email],
                        'email/verify_email.html',
                        verification_url=verification_url,
                        username=existing_user.username
                    )
                    flash('This email is already registered but not verified. A new verification link has been sent.', 'info')
                    return redirect(url_for('login'))
                else:
                    flash('Email already exists! Please login.', 'error')
                    return render_template('register.html')

            # Create new user (unverified by default)
            new_user = User(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            # Send verification email
            token = ts.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])
            verification_url = url_for('verify_email', token=token, _external=True)
            
            email_sent = send_email(
                "Please confirm your email - ShareXpress",
                [email],
                'email/verify_email.html',
                verification_url=verification_url,
                username=username
            )

            if email_sent:
                flash('A confirmation email has been sent to your email address. Please check your inbox.', 'info')
            else:
                flash('Account created, but we couldn\'t send the verification email. Link printed to console.', 'warning')
                
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            flash('Registration failed. Please ensure your email is correct.', 'error')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    try:
        email = ts.loads(token, salt=app.config['SECURITY_PASSWORD_SALT'], max_age=86400) # 24 hours
    except:
        flash('The verification link is invalid or has expired.', 'error')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first_or_404()
    if user.is_verified:
        flash('Account already verified. Please login.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        
        # Send welcome email
        send_email(
            "Welcome to ShareXpress! Verification Successful",
            [user.email],
            'email/welcome.html',
            username=user.username,
            login_url=url_for('login', _external=True)
        )
        
        flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('login'))

@app.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            if user.is_verified:
                flash('This account is already verified. Please login.', 'info')
                return redirect(url_for('login'))
            
            token = ts.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])
            verification_url = url_for('verify_email', token=token, _external=True)
            
            email_sent = send_email(
                "Please confirm your email - ShareXpress",
                [email],
                'email/verify_email.html',
                verification_url=verification_url,
                username=user.username
            )
            
            if email_sent:
                flash('A new verification email has been sent.', 'info')
            else:
                flash('Could not send email. [DEV MODE] Link printed to console.', 'warning')
                
        else:
            # We don't want to reveal if an email exists, but for resend it's usually fine
            flash('No account found with that email.', 'error')
            
        return redirect(url_for('login'))
    
    return render_template('resend_verification.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('username')
        password = request.form.get('password')

        if not identity or not password:
            flash('Please provide both username and password!', 'error')
            return render_template('login.html')

        # Find user by username OR email
        user = User.query.filter((User.username == identity) | (User.email == identity)).first()

        if user and user.check_password(password):
            if not user.is_verified:
                flash('Please verify your email address first!', 'warning')
                return render_template('login.html')
                
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            token = ts.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])
            reset_url = url_for('reset_password', token=token, _external=True)
            
            email_sent = send_email(
                "Password Reset Request - ShareXpress",
                [email],
                'email/reset_password.html',
                reset_url=reset_url,
                username=user.username
            )
            
            if email_sent:
                flash('If an account exists with that email, a password reset link has been sent.', 'info')
            else:
                flash('Error sending reset email. [DEV MODE] Link printed to console.', 'warning')
        else:
            # Generic message for security
            flash('If an account exists with that email, a password reset link has been sent.', 'info')
            
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = ts.loads(token, salt=app.config['SECURITY_PASSWORD_SALT'], max_age=3600) # 1 hour
    except:
        flash('The reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))

    user = User.query.filter_by(email=email).first_or_404()

    if request.method == 'POST':
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

        if not password:
            flash('Password is required!', 'error')
            return render_template('reset_password.html', token=token)

        if password != confirmation:
            flash('Passwords do not match!', 'error')
            return render_template('reset_password.html', token=token)

        user.set_password(password)
        db.session.commit()
        flash('Your password has been reset. You can now login.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)

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

        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

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
        if not allowed_file(file.filename):
            flash(f'File type not allowed! Allowed types: {", ".join(ALLOWED_EXTENSIONS)}', 'error')
            return redirect(url_for('dashboard'))

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



