EquipTrack

EquipTrack is a Flask web application for managing a hardware/equipment inventory. It tracks stock, handles borrow and return requests with admin approval, and keeps an audit trail of everything that happens.

It runs on a local SQLite file for offline development and switches to PostgreSQL (e.g. Supabase) automatically when DATABASE_URL is set.

Features
Authentication: registration with email OTP verification (10-minute expiry), bcrypt password hashing, and automatic account lockout after 3 failed logins.
Roles: USER and ADMIN, with admin-only pages and actions.
Inventory catalog: add, edit, delete, and export equipment (category, quantity, unit price, serial number, condition, location, minimum stock level).
Borrowing workflow: users submit borrow requests; admins approve or reject them. Users submit return requests, which admins also review.
Password management: users can request a password change that admins approve, and admins can reset or unlock accounts.
Reports and exports: dashboard, reports, and CSV export for equipment and reports.
Audit logging: every significant action is written to audit_logs, and application logs go to app_logging/app.log.
Email notifications: OTP delivery and admin alerts (borrow requests, password requests, account actions) via Brevo SMTP. If SMTP is not configured, OTP codes are printed to the server console for local development.
Tech Stack
Python, Flask 3
SQLite (local) or PostgreSQL via psycopg2 (production)
bcrypt for password hashing
Supabase client (optional connectivity checks)
Brevo SMTP for email
Gunicorn for production, deployed on Render


Project Structure
.
├── app.py                          # Flask app: routes, auth, approvals, reports
├── main.py                         # Local entry point and CLI flags
├── db_compat.py                    # SQLite/Postgres compatibility layer
├── db_schema.py                    # Shared PostgreSQL schema
├── migrate_sqlite_to_postgresql.py # One-off SQLite -> Postgres data migration
├── mailer.py                       # Brevo SMTP email (OTPs, admin notifications)
├── logger.py                       # Logging setup (writes to app_logging/)
├── controller/                     # HardwareController (inventory logic)
├── models/                         # Database models / initialization
├── views/                          # View layer
├── web/                            # Templates (web/templates) and static assets
├── app_logging/                    # Log output (log files are git-ignored)
├── hardware_inventory.db           # Local SQLite database
├── render.yaml                     # Render deployment config
├── requirements.txt
└── .env.example                    # Template for environment variables

Getting Started

Prerequisites
Python 3.10 or newer
(Optional) A Supabase/PostgreSQL database
(Optional) A Brevo account for sending email
Installation
bash
git clone <your-repo-url>
cd <your-repo-folder>

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
Configuration

Copy the example file and fill in your values:

bash
cp .env.example .env
Variable	Required	Description
SECRET_KEY	Yes (production)	Flask session secret. Use a long random string.
DATABASE_URL	No	PostgreSQL connection string. If unset, the app uses the local SQLite file.
SUPABASE_URL	No	Supabase project URL (used for connectivity checks).
SUPABASE_ANON_KEY	No	Supabase publishable/anon key.
BREVO_SMTP_LOGIN	No	Brevo SMTP login.
BREVO_SMTP_KEY	No	Brevo SMTP key.
MAIL_FROM	No	Sender, e.g. EquipTrack <verified-sender@yourdomain.com>.
ADMIN_NOTIFY_EMAIL	No	Extra address that receives admin notifications. Defaults to the MAIL_FROM address.
BREVO_SMTP_HOST / BREVO_SMTP_PORT	No	Override the Brevo host/port (defaults: smtp-relay.brevo.com / 2525).

Never commit your real .env. It is already listed in .gitignore.

Run the app
bash
python main.py

The app starts at http://127.0.0.1:5000 and opens in your browser. The database is created and prepared on startup.

CLI options
bash
python main.py --test-supabase                      # Check Supabase connectivity
python main.py --test-supabase --test-table <name>  # Also query a table
python main.py --migrate-postgres                   # Copy SQLite data to PostgreSQL
Using PostgreSQL / Supabase
Set DATABASE_URL in .env.
Run the migration to create the schema and copy your existing SQLite data:
bash
   python main.py --migrate-postgres

The script creates the tables (if missing), inserts the rows without overwriting existing ones, and re-syncs the ID sequences. 3. Start the app as usual. It will use PostgreSQL whenever DATABASE_URL is set.

Deployment (Render)

The repository includes a render.yaml blueprint:

Build: pip install -r requirements.txt
Start: gunicorn --bind 0.0.0.0:$PORT app:app
Health check: /health

Set DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, BREVO_SMTP_LOGIN, BREVO_SMTP_KEY, and MAIL_FROM in the Render dashboard. SECRET_KEY is generated automatically. Brevo is used on port 2525 because Render blocks outbound SMTP on port 587.

Roles
Role	Can do
USER	Browse the catalog, request to borrow and return equipment, view their own borrowing, request a password change.
ADMIN	Everything a user can do, plus manage equipment, approve or reject borrow, return, and password requests, reset or unlock accounts, view reports and the audit log.
Security Notes
Passwords are hashed with bcrypt; accounts lock after 3 failed attempts and must be unlocked via password reset.
Change SECRET_KEY before deploying. The built-in fallback is for development only.
Keep .env and any database credentials out of version control.
