#!/usr/bin/env python3
"""
Initialize multi-tenant database tables.
Run this AFTER the existing schema is set up.
"""

import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def init_database():
    """Create all multi-tenant tables"""
    # Lazy import to avoid circular dependencies
    from app.db._database import engine, Base
    from app.models._organization import Organization
    from app.models._auth_user import AuthUser
    from app.models._employee_invite import EmployeeInvite
    
    print("🗄️  Creating multi-tenant tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")


def create_default_organization():
    """Create a default 'seed' organization"""
    from app.db._database import SessionLocal
    from app.models._organization import Organization
    from app.utils._password import hash_password
    
    db = SessionLocal()
    try:
        existing = db.query(Organization).filter_by(slug="seed").first()
        if existing:
            print("✓ Seed organization already exists")
            return existing
        
        org = Organization(
            id=str(uuid.uuid4()),
            name="Seed Organization",
            slug="seed",
            description="Default organization for seeded test data",
            subscription_tier="free",
            max_employees=50,
            max_projects=10,
            is_active=True
        )
        db.add(org)
        db.commit()
        print(f"✅ Created seed organization: {org.slug}")
        return org
    finally:
        db.close()


def create_default_admin(org_id, email="admin@seed.local", password="admin123"):
    """Create a default admin user"""
    from app.db._database import SessionLocal
    from app.models._auth_user import AuthUser
    from app.utils._password import hash_password
    
    db = SessionLocal()
    try:
        existing = db.query(AuthUser).filter_by(email=email).first()
        if existing:
            print(f"✓ Admin user {email} already exists")
            return existing
        
        admin = AuthUser(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            email=email,
            password_hash=hash_password(password),
            full_name="Admin User",
            role="admin",
            is_active=True,
            is_verified=True
        )
        db.add(admin)
        db.commit()
        print(f"✅ Created admin user: {email}")
        return admin
    finally:
        db.close()


def main():
    """Run initialization"""
    print("\n" + "="*60)
    print("🚀 Multi-Tenant Initialization Script")
    print("="*60 + "\n")
    
    try:
        # 1. Create tables
        init_database()
        
        # 2. Create default organization
        org = create_default_organization()
        
        # 3. Create default admin
        create_default_admin(org.id)
        
        print("\n" + "="*60)
        print("✅ Multi-tenant database initialized successfully!")
        print("="*60)
        print("\n📝 Next steps:")
        print("   1. Start backend: uvicorn app.main:app --reload")
        print("   2. Login with: admin@seed.local / admin123")
        print()
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
