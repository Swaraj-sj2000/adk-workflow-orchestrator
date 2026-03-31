#!/usr/bin/env python3
"""
Test Data Setup Script
Creates 10 test users for the AI Workforce Orchestrator
"""

import sys
sys.path.insert(0, '/home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend')

from sqlalchemy.orm import Session
from app.db._database import SessionLocal, engine, Base
from app.models._user import User
from app.core._security import hash_password

# Create tables
Base.metadata.create_all(bind=engine)

# Test users data
test_users = [
    {
        "email": "swaraj@devteam.com",
        "password": "admin123",
        "full_name": "Swaraj",
        "role": "admin"
    },
    {
        "email": "alex.kumar@devteam.com",
        "password": "dev123456",
        "full_name": "Alex Kumar",
        "role": "employee"
    },
    {
        "email": "priya.sharma@devteam.com",
        "password": "dev123456",
        "full_name": "Priya Sharma",
        "role": "employee"
    },
    {
        "email": "raj.patel@devteam.com",
        "password": "frontend123",
        "full_name": "Raj Patel",
        "role": "employee"
    },
    {
        "email": "sara.chen@devteam.com",
        "password": "frontend123",
        "full_name": "Sara Chen",
        "role": "employee"
    },
    {
        "email": "ananya.gupta@devteam.com",
        "password": "aidev123456",
        "full_name": "Ananya Gupta",
        "role": "employee"
    },
    {
        "email": "vikram.singh@devteam.com",
        "password": "marketing123",
        "full_name": "Vikram Singh",
        "role": "employee"
    },
    {
        "email": "sneha.desai@devteam.com",
        "password": "sales123456",
        "full_name": "Sneha Desai",
        "role": "employee"
    },
    {
        "email": "rohan.verma@devteam.com",
        "password": "ba123456",
        "full_name": "Rohan Verma",
        "role": "employee"
    },
    {
        "email": "maya.iyer@devteam.com",
        "password": "cad123456",
        "full_name": "Maya Iyer",
        "role": "employee"
    },
]

def seed_users():
    """Create test users in the database"""
    db = SessionLocal()
    
    try:
        # Clear existing users
        existing = db.query(User).all()
        if existing:
            print(f"Found {len(existing)} existing users. Clearing...")
            for user in existing:
                db.delete(user)
            db.commit()
        
        # Create new users
        created_users = []
        for user_data in test_users:
            user = User(
                email=user_data["email"],
                password=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"]
            )
            db.add(user)
            created_users.append(user_data)
        
        db.commit()
        
        print("\n✅ Successfully created 10 test users!\n")
        print("=" * 80)
        print("TEST USER CREDENTIALS - AI WORKFORCE ORCHESTRATOR")
        print("=" * 80)
        print("\n📊 TEAM BREAKDOWN:\n")
        
        print("👨‍💼 ADMIN:")
        print(f"  • Swaraj (Admin & Developer)")
        print(f"    Email: swaraj@devteam.com")
        print(f"    Password: admin123\n")
        
        print("👨‍💻 BACKEND DEVELOPERS (Senior):")
        print(f"  • Alex Kumar (Senior Backend Dev)")
        print(f"    Email: alex.kumar@devteam.com")
        print(f"    Password: dev123456")
        print(f"\n  • Priya Sharma (Senior Backend Dev)")
        print(f"    Email: priya.sharma@devteam.com")
        print(f"    Password: dev123456\n")
        
        print("🎨 FRONTEND DEVELOPERS:")
        print(f"  • Raj Patel (Frontend Dev)")
        print(f"    Email: raj.patel@devteam.com")
        print(f"    Password: frontend123")
        print(f"\n  • Sara Chen (Frontend Dev)")
        print(f"    Email: sara.chen@devteam.com")
        print(f"    Password: frontend123\n")
        
        print("🤖 AI/ML DEVELOPER:")
        print(f"  • Ananya Gupta (AI/ML Engineer)")
        print(f"    Email: ananya.gupta@devteam.com")
        print(f"    Password: aidev123456\n")
        
        print("📢 MARKETING:")
        print(f"  • Vikram Singh (Marketing Manager)")
        print(f"    Email: vikram.singh@devteam.com")
        print(f"    Password: marketing123\n")
        
        print("💼 SALES:")
        print(f"  • Sneha Desai (Sales Manager)")
        print(f"    Email: sneha.desai@devteam.com")
        print(f"    Password: sales123456\n")
        
        print("📋 BUSINESS ANALYST:")
        print(f"  • Rohan Verma (Business Analyst)")
        print(f"    Email: rohan.verma@devteam.com")
        print(f"    Password: ba123456\n")
        
        print("🎯 CAD DESIGNER:")
        print(f"  • Maya Iyer (CAD Designer)")
        print(f"    Email: maya.iyer@devteam.com")
        print(f"    Password: cad123456\n")
        
        print("=" * 80)
        print("\n🚀 QUICK TEST STEPS:")
        print("1. Go to http://localhost:3000")
        print("2. Click 'Login' tab")
        print("3. Use any email/password from above")
        print("4. Explore the orchestrator dashboard\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("\n🔧 Starting test data setup...\n")
    seed_users()
