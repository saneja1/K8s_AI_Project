"""
User Authentication Models
STEP 2: Database model for storing users with roles
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt
from datetime import datetime

# Initialize database
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """
    User model for authentication
    
    UserMixin provides Flask-Login required methods:
    - is_authenticated: Always True for logged-in users
    - is_active: User account is active (not banned)
    - is_anonymous: Always False for real users
    - get_id(): Returns user.id as string
    """
    
    __tablename__ = 'users'
    
    # Database columns
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')  # viewer, operator, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        """String representation for debugging"""
        return f'<User {self.username} ({self.role})>'
    
    def set_password(self, password):
        """
        Hash password using bcrypt before storing
        
        Why bcrypt?
        - One-way encryption (cannot be reversed)
        - Adds "salt" (random data) so same password = different hash
        - Slow on purpose (prevents brute force attacks)
        
        Example:
        password="admin123" -> hash="$2b$12$abcd...xyz" (60 chars)
        """
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password):
        """
        Verify password against stored hash
        
        Returns True if password matches, False otherwise
        bcrypt compares the provided password with the stored hash
        """
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            self.password_hash.encode('utf-8')
        )
    
    # Role-based permission checks
    
    def is_viewer(self):
        """Check if user has viewer role (lowest permission)"""
        return self.role == 'viewer'
    
    def is_operator(self):
        """Check if user has operator role (medium permission)"""
        return self.role == 'operator'
    
    def is_admin(self):
        """Check if user has admin role (highest permission)"""
        return self.role == 'admin'
    
    def can_view(self):
        """All roles can view"""
        return True
    
    def can_operate(self):
        """Only operator and admin can perform safe operations"""
        return self.role in ['operator', 'admin']
    
    def can_delete(self):
        """Only admin can perform destructive operations"""
        return self.role == 'admin'
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()


def init_db(app):
    """
    Initialize database with app context
    Called from app.py during startup
    
    This creates the SQLite database file and users table
    """
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully")


def create_default_admin(app):
    """
    Create default admin user if no users exist
    
    Default credentials (CHANGE THESE AFTER FIRST LOGIN!):
    Username: admin
    Password: admin123
    Role: admin
    
    This runs automatically on first startup
    """
    with app.app_context():
        # Check if any users exist
        if User.query.first() is None:
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            
            db.session.add(admin)
            db.session.commit()
            
            print("=" * 60)
            print("⚠️  DEFAULT ADMIN USER CREATED")
            print("=" * 60)
            print("Username: admin")
            print("Password: admin123")
            print("Role: admin")
            print("")
            print("⚠️  IMPORTANT: Change this password after first login!")
            print("=" * 60)
        else:
            print(f"✅ Found {User.query.count()} existing user(s) in database")
        
        # Always ensure guest user exists
        create_guest_user(app)


def create_guest_user(app):
    """
    Create or update guest user for anonymous access
    
    Guest credentials (NO PASSWORD REQUIRED):
    Username: guest
    Role: viewer (read-only)
    
    This runs automatically on startup
    """
    with app.app_context():
        guest = User.query.filter_by(username='guest').first()
        
        if guest is None:
            # Create new guest user
            guest = User(username='guest', role='viewer')
            guest.set_password('guest123')  # Password not used, but required by model
            
            db.session.add(guest)
            db.session.commit()
            
            print("✅ Guest user created (username: guest, role: viewer)")
