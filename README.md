# 📦 EquipTrack

> A Flask-based hardware and equipment inventory management system with borrowing workflows, role-based access, audit logging, reporting, and email notifications.

EquipTrack is a web application designed to help organizations manage their hardware and equipment inventory in one place. It allows administrators to manage equipment, monitor stock levels, approve borrowing and return requests, manage user accounts, and maintain a complete audit trail of system activity.

The application supports **SQLite for local development** and automatically switches to **PostgreSQL** when `DATABASE_URL` is configured, making it suitable for production environments such as Supabase.

---

## ✨ Features

### 🔐 Authentication & Security

- User registration with email OTP verification
- OTP expiration after **10 minutes**
- Secure password hashing using **bcrypt**
- Automatic account lockout after **3 failed login attempts**
- Admin-controlled account unlocking
- Password change request workflow
- Role-based access control

### 👥 User Roles

| Role | Description |
|------|-------------|
| 👤 **USER** | Browse equipment, request borrowing and returns, view borrowing history, and request password changes |
| 🛡️ **ADMIN** | Full system access including inventory management, request approvals, reports, audit logs, and account management |

---

## 📦 Inventory Management

Administrators can manage the complete equipment catalog.

Each equipment record can contain:

- Equipment name
- Category
- Quantity
- Unit price
- Serial number
- Condition
- Location
- Minimum stock level

### Inventory Actions

- ➕ Add equipment
- ✏️ Edit equipment
- 🗑️ Delete equipment
- 🔎 Browse equipment
- 📊 Monitor stock levels
- 📄 Export equipment data to CSV

---

## 🔄 Borrowing & Return Workflow

EquipTrack provides a controlled borrowing process between users and administrators.

### Borrow Equipment

```text
USER
  │
  ▼
Submit Borrow Request
  │
  ▼
ADMIN
  │
  ├── Approve ──► Equipment Borrowed
  │
  └── Reject ──► Request Rejected
```

### Return Equipment

```text
USER
  │
  ▼
Submit Return Request
  │
  ▼
ADMIN
  │
  ├── Approve ──► Equipment Returned
  │
  └── Reject ──► Return Rejected
```

Every important action is recorded in the audit log.

---

## 📊 Dashboard & Reports

Administrators can monitor the system through dashboards and reports.

Available functionality includes:

- Inventory overview
- Equipment reports
- Borrowing reports
- Return activity
- Stock monitoring
- CSV exports
- Audit log viewing

---

## 📝 Audit Logging

EquipTrack maintains an audit trail of significant system activities.

Examples include:

- User registration
- Login attempts
- Equipment creation
- Equipment updates
- Equipment deletion
- Borrow requests
- Borrow approvals and rejections
- Return requests
- Return approvals and rejections
- Password requests
- Account resets
- Account unlocking
- Other administrative actions

Application logs are also stored in:

```text
app_logging/app.log
```

The log directory is excluded from Git through `.gitignore`.

---

## 📧 Email Notifications

EquipTrack uses **Brevo SMTP** for email communication.

Email notifications can be sent for:

- 🔑 OTP verification
- 📦 Borrow requests
- 🔄 Return requests
- 🔐 Password change requests
- 👤 Account actions
- 🛡️ Administrator notifications

If SMTP is not configured, OTP codes are printed to the server console for local development.

---

# 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| 🐍 Python | Backend programming language |
| 🌐 Flask 3 | Web framework |
| 🗄️ SQLite | Local development database |
| 🐘 PostgreSQL | Production database |
| ☁️ Supabase | PostgreSQL hosting / connectivity |
| 🔒 bcrypt | Password hashing |
| 📧 Brevo SMTP | Email delivery |
| 🚀 Gunicorn | Production WSGI server |
| ☁️ Render | Production deployment |

---

# 📁 Project Structure

```text
EquipTrack/
│
├── app.py                          # Flask application, routes, authentication, approvals, reports
├── main.py                         # Local entry point and CLI commands
├── db_compat.py                    # SQLite/PostgreSQL compatibility layer
├── db_schema.py                    # Shared PostgreSQL schema
├── migrate_sqlite_to_postgresql.py # SQLite → PostgreSQL migration
├── mailer.py                       # Brevo SMTP email functionality
├── logger.py                       # Application logging setup
│
├── controller/
│   └── HardwareController          # Inventory logic
│
├── models/
│   └── Database models / initialization
│
├── views/
│   └── View layer
│
├── web/
│   ├── templates/                  # HTML templates
│   └── static/                     # CSS, JavaScript, images
│
├── app_logging/
│   └── app.log                     # Application logs
│
├── hardware_inventory.db           # Local SQLite database
├── render.yaml                     # Render deployment configuration
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .gitignore
└── README.md
```

---

# 🚀 Getting Started

## Prerequisites

Make sure you have the following installed:

- **Python 3.10 or newer**
- Git
- pip

Optional:

- Supabase/PostgreSQL account
- Brevo account for email notifications

---

## 📥 Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙️ Configuration

Create your environment file from the example:

```bash
cp .env.example .env
```

> On Windows, you can also manually copy `.env.example` and rename it to `.env`.

Then configure your environment variables.

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Production | Flask session secret |
| `DATABASE_URL` | Optional | PostgreSQL connection string |
| `SUPABASE_URL` | Optional | Supabase project URL |
| `SUPABASE_ANON_KEY` | Optional | Supabase publishable/anon key |
| `BREVO_SMTP_LOGIN` | Optional | Brevo SMTP login |
| `BREVO_SMTP_KEY` | Optional | Brevo SMTP key |
| `MAIL_FROM` | Optional | Verified sender email |
| `ADMIN_NOTIFY_EMAIL` | Optional | Email address for admin notifications |
| `BREVO_SMTP_HOST` | Optional | SMTP host |
| `BREVO_SMTP_PORT` | Optional | SMTP port |

### Example `.env`

```env
SECRET_KEY=your-secret-key

DATABASE_URL=your-postgresql-connection-string

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

BREVO_SMTP_LOGIN=your-smtp-login
BREVO_SMTP_KEY=your-smtp-key

MAIL_FROM=EquipTrack <your-email@yourdomain.com>
ADMIN_NOTIFY_EMAIL=admin@yourdomain.com

BREVO_SMTP_HOST=smtp-relay.brevo.com
BREVO_SMTP_PORT=2525
```

> ⚠️ **Never commit your `.env` file or database credentials to GitHub.**

The `.env` file should be included in `.gitignore`.

---

# ▶️ Running the Application

Start EquipTrack with:

```bash
python main.py
```

The application will start at:

```text
http://127.0.0.1:5000
```

The database is automatically created and prepared when the application starts.

---

# 🧰 CLI Options

### Test Supabase connectivity

```bash
python main.py --test-supabase
```

### Test Supabase and query a table

```bash
python main.py --test-supabase --test-table <table_name>
```

### Migrate SQLite to PostgreSQL

```bash
python main.py --migrate-postgres
```

---

# 🗄️ Database

EquipTrack supports two database environments.

### Local Development

When `DATABASE_URL` is not configured, EquipTrack uses SQLite:

```text
EquipTrack
    │
    ▼
SQLite
    │
    └── hardware_inventory.db
```

This allows the application to run locally without requiring an external database.

### Production

When `DATABASE_URL` is configured, EquipTrack automatically uses PostgreSQL:

```text
EquipTrack
    │
    ▼
PostgreSQL
    │
    └── Supabase / PostgreSQL provider
```

---

# 🔄 Migrating SQLite to PostgreSQL

If you already have data stored in the local SQLite database, you can migrate it to PostgreSQL.

### 1. Configure `DATABASE_URL`

Add your PostgreSQL connection string to `.env`:

```env
DATABASE_URL=your-postgresql-connection-string
```

### 2. Run the migration

```bash
python main.py --migrate-postgres
```

The migration process:

- Creates missing tables
- Copies existing SQLite data
- Avoids overwriting existing PostgreSQL records
- Re-syncs PostgreSQL ID sequences

### 3. Start the application

```bash
python main.py
```

EquipTrack will now use PostgreSQL.

---

# ☁️ Deployment

EquipTrack can be deployed using **Render**.

The repository includes:

```text
render.yaml
```

### Render Configuration

| Setting | Value |
|---------|-------|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --bind 0.0.0.0:$PORT app:app` |
| Health Check | `/health` |

### Required Environment Variables

Configure the following in the Render dashboard:

```text
DATABASE_URL
SUPABASE_URL
SUPABASE_ANON_KEY
BREVO_SMTP_LOGIN
BREVO_SMTP_KEY
MAIL_FROM
```

`SECRET_KEY` should be generated securely for production.

### SMTP

EquipTrack uses Brevo SMTP on port **2525**, which is suitable for environments where standard SMTP port 587 may be restricted.

---

# 🔐 Security

EquipTrack includes several security mechanisms.

### Password Security

Passwords are never stored as plain text.

They are securely hashed using:

```text
bcrypt
```

### Account Lockout

After **3 failed login attempts**, the account is automatically locked.

An administrator can unlock the account through the account management functionality.

### OTP Verification

Registration uses an email-based OTP.

OTP codes:

- Are sent through Brevo SMTP when configured
- Expire after **10 minutes**
- Are printed to the server console when SMTP is unavailable for local development

### Environment Variables

Sensitive information should be stored in `.env`.

Never commit:

```text
.env
database credentials
SMTP credentials
API keys
production secrets
```

---

# 👥 User Permissions

| Feature | USER | ADMIN |
|---------|:----:|:-----:|
| Register account | ✅ | ✅ |
| Email verification | ✅ | ✅ |
| Login | ✅ | ✅ |
| Browse equipment | ✅ | ✅ |
| Request equipment | ✅ | ✅ |
| Request equipment return | ✅ | ✅ |
| View own borrowing | ✅ | ✅ |
| Request password change | ✅ | ✅ |
| Add equipment | ❌ | ✅ |
| Edit equipment | ❌ | ✅ |
| Delete equipment | ❌ | ✅ |
| Export inventory | ❌ | ✅ |
| Approve borrow requests | ❌ | ✅ |
| Reject borrow requests | ❌ | ✅ |
| Approve return requests | ❌ | ✅ |
| Reject return requests | ❌ | ✅ |
| Approve password requests | ❌ | ✅ |
| Reset accounts | ❌ | ✅ |
| Unlock accounts | ❌ | ✅ |
| View reports | ❌ | ✅ |
| View audit logs | ❌ | ✅ |

---

# 🔁 System Workflow

The overall system works around the following process:

```text
                 ┌─────────────────┐
                 │   Registration  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Email OTP Check │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │     Login       │
                 └────────┬────────┘
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
             👤 USER            🛡️ ADMIN
                 │                 │
                 ▼                 ▼
          Browse Inventory    Manage Inventory
                 │                 │
                 ▼                 ▼
          Borrow Request      Review Requests
                 │                 │
                 └────────┬────────┘
                          ▼
                    Audit Logging
                          │
                          ▼
                    Reports / Logs
```

---

# 📋 Borrowing Process

### User

1. Log in to EquipTrack
2. Browse available equipment
3. Select equipment
4. Submit a borrow request
5. Wait for administrator approval
6. Receive the equipment after approval

### Administrator

1. Log in to the admin dashboard
2. Review pending borrow requests
3. Check equipment availability
4. Approve or reject the request
5. System updates the equipment inventory
6. The action is recorded in the audit log

---

# 🔄 Return Process

### User

1. View currently borrowed equipment
2. Submit a return request
3. Wait for administrator review

### Administrator

1. Review the return request
2. Approve or reject the return
3. Update the equipment status
4. Record the action in the audit log

---

# 📊 Reports & Exports

EquipTrack provides administrators with reporting and export functionality.

Available reports include:

- Equipment inventory
- Stock levels
- Borrowing activity
- Return activity
- System activity
- Audit logs

Equipment and report data can be exported as **CSV files** for further analysis.

---

# 📝 Audit Trail

All important actions are recorded in the `audit_logs` table.

Examples include:

```text
User Registration
Login Attempts
Equipment Added
Equipment Updated
Equipment Deleted
Borrow Request
Borrow Approval
Borrow Rejection
Return Request
Return Approval
Return Rejection
Password Request
Password Approval
Account Reset
Account Unlock
```

Application-level logs are stored in:

```text
app_logging/app.log
```

---

# 🧪 Development

For local development, EquipTrack can run entirely using SQLite.

No PostgreSQL or Supabase configuration is required for basic local development.

Simply run:

```bash
python main.py
```

If Brevo SMTP is not configured, OTP codes will be printed to the server console. This allows authentication features to be tested locally without configuring an email service.

---

# 🎯 Project Goals

EquipTrack was designed to provide a simple and centralized solution for managing hardware and equipment.

The main goals are:

- Reduce manual inventory tracking
- Prevent unauthorized equipment borrowing
- Improve equipment accountability
- Provide controlled approval workflows
- Maintain accurate inventory records
- Keep a complete history of important system actions
- Provide useful reports for administrators

---

# 🚧 Future Improvements

Possible future enhancements include:

- 📱 Improved mobile responsiveness
- 📊 Advanced analytics and charts
- 🔔 Real-time notifications
- 📷 QR/barcode equipment scanning
- 📎 Equipment image uploads
- 📜 Printable borrowing receipts
- 📦 Bulk inventory import
- 🔎 Advanced inventory filtering
- 👤 More granular administrator permissions
- 🧾 PDF report generation
- 📈 Equipment usage analytics

---

# 🤝 Contributing

Contributions, suggestions, and improvements are welcome.

If you would like to contribute:

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Test your changes
5. Commit your changes
6. Push the branch
7. Open a Pull Request

Example:

```bash
git checkout -b feature/new-feature
git add .
git commit -m "Add new feature"
git push origin feature/new-feature
```

---

# 📄 License

This project is currently intended for educational and development use.

If you plan to distribute this project publicly, add your preferred open-source license here.

---

# 👨‍💻 EquipTrack

**Hardware & Equipment Inventory Management System**

Built with:

```text
Python
Flask
SQLite
PostgreSQL
Supabase
Brevo SMTP
Gunicorn
Render
```

⭐ If you find EquipTrack useful, consider giving the repository a star.
