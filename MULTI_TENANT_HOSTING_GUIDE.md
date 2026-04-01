# 🌐 Multi-Tenant Hosting & Deployment Guide

**Created by**: Swaraj  
**Date**: April 2026  
**Status**: Architecture & Implementation Plan

---

## 📊 Table of Contents

1. [Current State vs. Required State](#current-state-vs-required-state)
2. [Multi-Tenant Architecture](#multi-tenant-architecture)
3. [Hosting Solution Options](#hosting-solution-options)
4. [Authentication & Authorization](#authentication--authorization)
5. [Employee Invite System](#employee-invite-system)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Database Schema Changes](#database-schema-changes)
8. [Deployment & Scaling](#deployment--scaling)

---

## 🔄 Current State vs. Required State

### Current (Single-Tenant/Pre-registered)
- ✅ All employees pre-seeded in database
- ✅ Single admin (implicit)
- ✅ Single workspace/organization
- ✅ No user registration
- ✅ Hardcoded employee setup

### Required (Multi-Tenant/Self-Serve)
- ❌ Multiple organizations/workspaces
- ❌ Multiple admins per organization
- ❌ Dynamic employee registration
- ❌ Invite-based employee onboarding
- ❌ Role-based access control (RBAC)
- ❌ Tenant isolation
- ❌ Multi-tenant database support

---

## 🏗️ Multi-Tenant Architecture

### Option 1: Database-Per-Tenant (Recommended for Enterprise)

**Pros**:
- Complete data isolation
- Maximum security
- Easy backups per tenant
- Better for compliance/GDPR

**Cons**:
- Higher infrastructure costs
- Complex deployment
- Harder to manage

**Implementation**:
```
┌─────────────────────────────────────┐
│   Main Auth Database (Shared)       │
│  - Organizations                    │
│  - Admin Users                      │
│  - SSO/OAuth Config                 │
└─────────────────────────────────────┘
                 ↓
        ┌────────┴────────┐
        ↓                 ↓
    ┌─────────┐      ┌─────────┐
    │ Tenant A│      │ Tenant B│
    │Database │      │Database │
    └─────────┘      └─────────┘
```

### Option 2: Shared Database with Row-Level Security (Recommended for SMB)

**Pros**:
- Lower costs
- Simpler deployment
- Easier scaling
- Single backup strategy

**Cons**:
- Potential data leakage if not properly isolated
- Risk of query contamination

**Implementation**:
```
┌──────────────────────────────────────┐
│      Shared PostgreSQL Database      │
├──────────────────────────────────────┤
│ ✓ Tenant ID on all tables           │
│ ✓ Row-level security policies       │
│ ✓ Tenant-scoped queries             │
│ ✓ Audit logs with tenant tracking   │
└──────────────────────────────────────┘
```

### Recommended: Hybrid Approach (Database-Per-Tenant)

**Why**: Your project involves autonomous agents managing high-stakes decisions. Complete isolation ensures:
- No cross-tenant agent accidents
- Clear audit trails
- Regulatory compliance
- Easy scaling

---

## 🌍 Hosting Solution Options

### Option A: AWS (Recommended)

**Components**:
- **ALB** (Application Load Balancer) - Route by subdomain
- **RDS** (PostgreSQL) - Main auth database
- **RDS** - One per enterprise tenant; shared for SMB
- **ECS/Fargate** - Backend services
- **CloudFront** - React frontend CDN
- **S3** - Static assets
- **Cognito/IAM** - Authentication

**Cost**: ~$200-500/month base + per-tenant costs

**Setup Code**:
```python
# Multi-tenant tenant detection
class TenantMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, scope):
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode()
        
        # Extract subdomain: admin.example.com → admin
        subdomain = host.split(".")[0]
        
        scope["tenant_id"] = self.resolve_tenant(subdomain)
        return self.app(scope)
```

### Option B: Azure (With Multi-Tenant Integration)

**Components**:
- **App Service** - Backend hosting
- **Azure SQL** - Multi-tenant database
- **Azure AD B2C** - Authentication
- **Static Web Apps** - Frontend
- **Application Insights** - Monitoring

**Cost**: ~$150-400/month base + per-tenant

### Option C: Self-Hosted (DigitalOcean/Linode)

**Components**:
- **Docker** containers for backend/frontend
- **PostgreSQL** database
- **Nginx** reverse proxy
- **Certbot** for SSL
- **Kubernetes** for scaling

**Cost**: ~$50-200/month

---

## 🔐 Authentication & Authorization

### New Authentication Flow

```
Admin Signup
    ↓
Create Organization
    ↓
Admin Login → Create Invite Link
    ↓
Share Invite with Employees
    ↓
Employee Registers via Link
    ↓
Employee Login → Join Project Teams
```

### Database Model Updates

```python
# New models needed:
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True)  # For subdomain
    created_by = Column(String, ForeignKey("user.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_tier = Column(String)  # free, pro, enterprise
    max_employees = Column(Integer)

class User(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id"))
    email = Column(String, unique=True)
    password_hash = Column(String)
    role = Column(String)  # admin, manager, employee
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmployeeInvite(Base):
    __tablename__ = "employee_invites"
    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id"))
    email = Column(String)
    invite_code = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    status = Column(String)  # pending, accepted, expired
    created_by = Column(String, ForeignKey("user.id"))
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### JWT Token Structure

```python
{
    "sub": "user_id",
    "org": "organization_id",
    "role": "admin|manager|employee",
    "scopes": ["read:projects", "write:tasks"],
    "exp": 1704067200,
    "tenant_id": "org_123"
}
```

---

## 👥 Employee Invite System

### Invite Flow (Step-by-Step)

#### 1. Admin Generates Invite Link

```python
# backend/app/api/routes/invites.py
@router.post("/organizations/{org_id}/invites", dependencies=[Depends(verify_admin)])
async def create_invite(org_id: str, request: CreateInviteRequest):
    """
    Admin creates employee invite
    request: { "email": "john@company.com", "role": "employee" }
    """
    invite_code = generate_secure_token(24)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    invite = EmployeeInvite(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        email=request.email,
        invite_code=invite_code,
        expires_at=expires_at,
        created_by=current_user.id,
        status="pending"
    )
    
    db.add(invite)
    db.commit()
    
    # Generate invite link
    invite_link = f"https://app.example.com/accept-invite/{invite_code}"
    
    # Send email with link
    send_invite_email(request.email, invite_link)
    
    return {"invite_id": invite.id, "invite_code": invite_code}
```

#### 2. Employee Accepts Invite & Registers

```python
# Frontend: pages/AcceptInvite.jsx
import { useState } from 'react';

export function AcceptInvite({ inviteCode }) {
    const [formData, setFormData] = useState({
        fullName: '',
        email: '',
        password: '',
        role: 'Employee',
        skills: [],
        experience: 0
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        const response = await fetch('/api/auth/accept-invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                invite_code: inviteCode,
                full_name: formData.fullName,
                email: formData.email,
                password: formData.password,
                role: formData.role,
                skills: formData.skills,
                experience_years: formData.experience
            })
        });
        
        if (response.ok) {
            const { user, organization } = await response.json();
            // Redirect to dashboard
            window.location.href = '/dashboard';
        }
    };

    return (
        <div className="accept-invite-form">
            <h1>Join Organization</h1>
            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    placeholder="Full Name"
                    value={formData.fullName}
                    onChange={(e) => setFormData({...formData, fullName: e.target.value})}
                    required
                />
                <input
                    type="email"
                    placeholder="Email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    required
                />
                <input
                    type="password"
                    placeholder="Password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                />
                
                <label>Skills (comma-separated)</label>
                <input
                    type="text"
                    placeholder="e.g., Python, Project Management, Design"
                    value={formData.skills.join(', ')}
                    onChange={(e) => setFormData({
                        ...formData,
                        skills: e.target.value.split(',').map(s => s.trim())
                    })}
                />
                
                <label>Years of Experience</label>
                <input
                    type="number"
                    min="0"
                    max="50"
                    value={formData.experience}
                    onChange={(e) => setFormData({...formData, experience: parseInt(e.target.value)})}
                />
                
                <button type="submit">Join Organization</button>
            </form>
        </div>
    );
}
```

#### 3. Backend Accepts Invite & Creates Employee

```python
# backend/app/api/routes/auth.py
@router.post("/auth/accept-invite")
async def accept_invite(request: AcceptInviteRequest, db: Session = Depends(get_db)):
    """
    Employee completes registration via invite
    """
    # 1. Validate invite
    invite = db.query(EmployeeInvite).filter(
        EmployeeInvite.invite_code == request.invite_code,
        EmployeeInvite.status == "pending",
        EmployeeInvite.expires_at > datetime.utcnow()
    ).first()
    
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite")
    
    # 2. Create user
    user = User(
        id=str(uuid.uuid4()),
        organization_id=invite.organization_id,
        email=request.email,
        password_hash=hash_password(request.password),
        role="employee",
        is_active=True
    )
    db.add(user)
    
    # 3. Create employee profile
    employee = EmployeeProfile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        full_name=request.full_name,
        organization_id=invite.organization_id,
        role=request.role,
        skills=request.skills,
        experience_years=request.experience_years,
        status="active"
    )
    db.add(employee)
    
    # 4. Mark invite as accepted
    invite.status = "accepted"
    invite.accepted_at = datetime.utcnow()
    
    db.commit()
    
    # 5. Return token
    token = create_access_token({
        "sub": user.id,
        "org": invite.organization_id,
        "role": "employee"
    })
    
    return {
        "user": user,
        "organization": {"id": invite.organization_id},
        "access_token": token
    }
```

---

## 🗺️ Implementation Roadmap

### Phase 1: Core Multi-Tenant (Week 1-2)
- [ ] Create Organization model
- [ ] Create User authentication model
- [ ] Implement tenant context middleware
- [ ] Update existing models with org_id
- [ ] Create database migration plan

### Phase 2: Authentication (Week 2-3)
- [ ] Implement JWT token generation
- [ ] Add RBAC middleware
- [ ] Create login/signup endpoints
- [ ] Add password hashing & validation
- [ ] Create auth guards for API routes

### Phase 3: Invite System (Week 3-4)
- [ ] Create EmployeeInvite model
- [ ] Implement invite generation endpoint
- [ ] Create invite acceptance endpoint
- [ ] Build frontend invite page
- [ ] Add email notification service

### Phase 4: Frontend Updates (Week 4-5)
- [ ] Create organization switcher
- [ ] Build admin dashboard
- [ ] Create invite management page
- [ ] Build employee registration page
- [ ] Update navigation for multi-tenant

### Phase 5: Deployment & Testing (Week 5-6)
- [ ] Set up production database
- [ ] Configure cloud hosting (AWS/Azure)
- [ ] Implement tenant isolation tests
- [ ] Load testing with multiple tenants
- [ ] Security audit

---

## 🗄️ Database Schema Changes

### Current DB Migration

```python
# backend/app/db/migrations/001_add_multi_tenant.py
"""
Migration: Add multi-tenant support
- Add Organization table
- Add User table
- Modify existing tables to include org_id
- Create indexes for tenant queries
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('created_by', sa.String(36)),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('subscription_tier', sa.String(50)),
        sa.Column('max_employees', sa.Integer, default=50),
    )
    
    # 2. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('role', sa.String(50)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    
    # 3. Create employee invites table
    op.create_table(
        'employee_invites',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('invite_code', sa.String(100), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('created_by', sa.String(36)),
        sa.Column('accepted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    
    # 4. Add org_id to existing tables
    op.add_column('employee_profile', sa.Column('organization_id', sa.String(36)))
    op.add_column('projects', sa.Column('organization_id', sa.String(36)))
    op.add_column('tasks', sa.Column('organization_id', sa.String(36)))
    # ... add to other tables
    
    # 5. Create indexes
    op.create_index('idx_org_employees', 'employee_profile', ['organization_id'])
    op.create_index('idx_org_projects', 'projects', ['organization_id'])
```

---

## 🚀 Deployment & Scaling

### Local Development Setup

```bash
# 1. Set environment variables
export FLASK_ENV=development
export MULTI_TENANT_MODE=true
export DATABASE_URL=postgresql://user:pass@localhost/agentic_dev
export SECONDARY_DB_URL=postgresql://user:pass@localhost/tenant_1

# 2. Run migrations
python -m alembic upgrade head

# 3. Seed admin organization
python backend/seed_organizations.py

# 4. Start services
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

### Production Deployment (AWS)

```yaml
# docker-compose.prod.yml
version: '3.9'
services:
  backend:
    image: agentic-orchestrator-api:latest
    environment:
      DATABASE_URL: ${PROD_DB_URL}
      ENVIRONMENT: production
      MULTI_TENANT_MODE: true
    ports:
      - "8000:8000"
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  frontend:
    image: agentic-orchestrator-ui:latest
    ports:
      - "3000:3000"

volumes:
  postgres_data:
```

### Scaling Strategy

**For 100+ Tenants**:
1. Use **database sharding** by organization
2. Implement **read replicas** for reports
3. Add **Redis caching** for tenant configs
4. Use **message queues** (RabbitMQ) for async agent jobs

**Cost Optimization**:
- Free tier: Shared database
- Professional: Dedicated database
- Enterprise: Dedicated infrastructure

---

## 📝 Summary of Changes Needed

| Component | Current | Required | Effort |
|-----------|---------|----------|--------|
| Database | Single schema | Multi-tenant schema | 2 days |
| Authentication | Pre-seeded | JWT + OAuth | 3 days |
| API Routes | Single org | Org-scoped routes | 2 days |
| Frontend | No auth | Auth UI + invites | 3 days |
| Middleware | None | Tenant context | 1 day |
| Emails | None | Invite emails | 2 days |
| Deployment | Local | Cloud + multi-db | 3 days |
| **Total Estimate** | | | **16 days** |

---

## 🎯 Next Steps

1. **Choose hosting platform**: AWS (recommended), Azure, or self-hosted
2. **Review multi-tenant approach**: Database-per-tenant vs shared
3. **Start Phase 1**: Database schema migrations
4. **Test multi-tenant isolation**: Security & performance tests
5. **Plan rollout**: Gradual migration from current seeded data

**Questions to address**:
- How many initial organizations/admins?
- What compliance requirements (GDPR, HIPAA, SOC2)?
- Expected growth: 10 orgs? 100? 1000?
- Budget for infrastructure?

---

*This guide can be updated as decisions are made and implementation progresses.*
