# backend/MULTI_TENANT_SETUP.md

# Phase 1: Multi-Tenant Setup Guide

## What's New 🆕

This setup adds multi-tenant capabilities to the AI Workforce Orchestrator:

- ✅ **Organizations** - Multiple workspaces/tenants per database
- ✅ **AuthUser** - New authentication model with password hashing
- ✅ **EmployeeInvite** - Invite system for employee onboarding
- ✅ **Tenant Context** - Middleware to automatically inject org context
- ✅ **Tenant Isolation** - Auto-scoping queries to current organization

---

## Quick Start (5 minutes)

### 1. Install Dependencies (Already Done ✓)
```bash
# passlib[bcrypt] is already in requirements.txt
pip install -r requirements.txt
```

### 2. Initialize Multi-Tenant Tables

```bash
cd backend
python init_multi_tenant.py
```

**Output**:
```
🗄️  Creating multi-tenant tables...
✅ Tables created successfully!
✓ Seed organization already exists
✓ Admin user admin@seed.local already exists
```

### 3. Add Middleware to FastAPI App

**File**: `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware import Middleware
from app.core._tenant_middleware import TenantMiddleware

# Add tenant middleware AFTER CORS middleware but BEFORE routes
app = FastAPI()

# ... existing middlewares ...

# Add tenant middleware
app.add_middleware(TenantMiddleware)

# ... routes ...
```

### 4. Test the Setup

```bash
# Terminal 1: Start backend
cd backend
source venv/bin/activate
python init_multi_tenant.py
uvicorn app.main:app --reload

# Terminal 2: Test endpoints
curl -X GET http://localhost:8000/health

# See tenant context in action
curl -X GET http://localhost:8000/api/v1/organizations/seed/projects \
  -H "X-Organization-ID: seed"
```

---

## Database Schema Changes

### New Tables

#### `organizations`
```
id (STRING, UUID)          → Primary key
name                       → Organization name
slug (UNIQUE)             → URL-safe identifier
subscription_tier         → free/pro/enterprise
max_employees             → Limit for this org
created_by                → User who created org
created_at                → ISO timestamp
```

#### `auth_users`
```
id (STRING, UUID)              → Primary key
organization_id (FK)           → Which org this user belongs to
email (INDEXED)                → Unique per org
password_hash                  → bcrypt hash
full_name                      → User display name
role                           → admin/manager/employee
is_active                      → Account status
is_verified                    → Email verified
last_login                     → Track login times
created_at, updated_at         → Timestamps
```

#### `employee_invites`
```
id (STRING, UUID)              → Primary key
organization_id (FK)           → Which org
email                          → Target employee email
invite_code (UNIQUE)           → Secure link token
status                         → pending/accepted/expired
expires_at                     → 7-day default expiry
created_by                     → Admin user ID
accepted_by_user_id (FK)       → AuthUser who accepted
accepted_at                    → When accepted
created_at                     → When created
```

### Modified Tables

Added `organization_id` (FK) to:
- `employee_profiles`
- `projects`
- `tasks`
- `client_profiles`

This ensures multi-tenant data isolation.

---

## Code Examples

### Example 1: Create Organization

```python
from app.db._database import SessionLocal
from app.models._organization import Organization

db = SessionLocal()

org = Organization(
    name="Acme Corp",
    slug="acme-corp",
    subscription_tier="pro",
    max_employees=100
)
db.add(org)
db.commit()
```

### Example 2: Create User in Organization

```python
from app.models._auth_user import AuthUser
from app.utils._password import hash_password
import uuid

admin_user = AuthUser(
    id=str(uuid.uuid4()),
    organization_id=org.id,
    email="john@acme.com",
    password_hash=hash_password("secure_password"),
    full_name="John Doe",
    role="admin",
    is_active=True
)
db.add(admin_user)
db.commit()
```

### Example 3: Generate Employee Invite

```python
from app.models._employee_invite import EmployeeInvite

invite = EmployeeInvite.create_invite(
    organization_id=org.id,
    email="jane@acme.com",
    created_by=admin_user.id,
    role="employee",
    expires_in_days=7
)
db.add(invite)
db.commit()

# Generate link to share
invite_link = f"https://app.example.com/accept-invite/{invite.invite_code}"
print(f"Share this link: {invite_link}")
```

### Example 4: Use Tenant Context in Routes

```python
from fastapi import FastAPI, Request, Depends
from app.core._tenant_context import TenantContext
from sqlalchemy.orm import Session
from app.db._database import get_db

app = FastAPI()

@app.get("/api/v1/projects")
async def list_projects(request: Request, db: Session = Depends(get_db)):
    """List projects for current organization"""
    
    # Tenant context is automatically set by middleware
    org_id = TenantContext.get_org_id()
    
    # Query scoped to organization
    projects = db.query(Project).filter_by(organization_id=org_id).all()
    
    return {
        "organization_id": org_id,
        "projects": projects,
        "count": len(projects)
    }
```

### Example 5: Multi-Tenant Route Pattern

```python
@app.get("/api/v1/orgs/{org_slug}/projects")
async def get_org_projects(org_slug: str, db: Session = Depends(get_db)):
    """
    Get projects for specific organization.
    URL: GET /api/v1/orgs/acme-corp/projects
    """
    
    # Find organization
    org = db.query(Organization).filter_by(slug=org_slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Set context
    TenantContext.set_org_id(org.id)
    
    # Query
    projects = db.query(Project).filter_by(organization_id=org.id).all()
    
    return {"organization": org.slug, "projects": projects}
```

---

## Tenant Detection Strategies

The middleware tries these in order:

### 1. **Custom Headers** (Highest Priority)
```bash
curl -H "X-Organization-ID: acme-corp" http://localhost:8000/...
```

### 2. **URL Path**
```
GET /api/v1/orgs/acme-corp/projects  # Extracts: acme-corp
```

### 3. **Subdomain** (For Multi-Tenant SaaS)
```
GET http://acme-corp.example.com/projects  # Extracts: acme-corp
```

---

## Migration Path

### Phase 1 (Current) ✅
- [x] Create multi-tenant tables
- [x] Add org_id to existing models
- [x] Create tenant middleware
- [x] Password hashing utility

### Phase 2 (Next)
- [ ] Migrate existing data to seed organization
- [ ] Create authentication endpoints (login, signup)
- [ ] Create invite endpoints (generate, accept)
- [ ] Create auth guards for routes

### Phase 3
- [ ] Create frontend for invite acceptance
- [ ] Create admin dashboard for invite management
- [ ] Implement JWT token generation
- [ ] Add role-based access control (RBAC)

### Phase 4
- [ ] Cloud deployment (Google Cloud Run)
- [ ] Multi-database sharding
- [ ] Audit logging per organization

---

## Testing Checklist

- [ ] Run `python init_multi_tenant.py` successfully
- [ ] Verify `organizations` table created
- [ ] Verify `auth_users` table created
- [ ] Verify `employee_invites` table created
- [ ] Verify existing models have org_id column
- [ ] Test middleware detects organization
- [ ] Test tenant context is set correctly
- [ ] Test queries are org-scoped

---

## Troubleshooting

### Error: "tables already exist"
**Solution**: Tables won't override if they exist. Safe to run multiple times.

### Error: "passlib not found"
**Solution**: `pip install passlib[bcrypt]`

### Tenant context not set
**Verify**:
1. Middleware is added to app: `app.add_middleware(TenantMiddleware)`
2. Request has org ID in headers/path/subdomain
3. Organization exists in database

### SQLAlchemy errors about foreign keys
**Solution**: This is normal during transition. Old User FK's still work, new AuthUser FK's added.

---

## Environment Variables (Optional)

```bash
# .env
DATABASE_URL=sqlite:///./agentic_orchestrator.db
MULTI_TENANT_MODE=true
DEFAULT_ORG_SLUG=seed
JWT_SECRET=your-secret-key-here
```

---

## Next Steps

1. ✅ **Now**: Run `python init_multi_tenant.py`
2. ⏭️ **Next**: Start building Phase 2 (auth endpoints)
3. ⏭️ **Then**: Create invite flow frontend

Questions? Check [MULTI_TENANT_HOSTING_GUIDE.md](../MULTI_TENANT_HOSTING_GUIDE.md)
