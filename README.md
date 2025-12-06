# Retail Management System - Checkpoint 4

**Author:** Alisa  
**Course:** Software Architecture & Design  
**Repository:** https://github.com/alisavictory7/Retail-Management-System---Checkpoint-4

---

## 📝 Project Description

A full-stack retail management system implementing enterprise-grade quality attributes and architectural patterns. This system handles complete retail operations including user management, product catalog, shopping cart, payments, order tracking, returns & refunds (RMA), and administrative dashboards with real-time monitoring.

Checkpoint 4 builds on the deployable, observable, and reliable foundation from CP3 by adding three lightweight features using architectural patterns documented in ADRs, along with a redesigned admin experience.

---

## 👥 Team Members

| Name | Role |
|------|------|
| **Alisa** | Developer & Architect |

---

## ✅ Checkpoint 4 Features

### New Features Summary

| Feature | Description | Pattern | Route/Component |
|---------|-------------|---------|-----------------|
| **2.1 Order History Filtering** | Filter orders by status, date range, and keyword search | Layered Service Abstraction | `/order-history`, `HistoryService` |
| **2.2 Low Stock Alerts** | Real-time alerts when inventory falls below threshold | Publish-Subscribe | `/admin/dashboard`, `LowStockAlertService` |
| **2.3 RMA Notifications** | In-app notifications for return status changes | Publish-Subscribe | `/api/notifications`, `NotificationService` |
| **Quality Scenario Monitoring** | Interactive live testing for A.1 & P.1 scenarios | Observability | `/admin/quality-monitoring` |
| **Unified Admin Dashboard** | Portal-based dashboard with quick access cards | Modular UI | `/admin/dashboard` |
| **Manage Store** | Combined products, stock alerts, and flash sales | Tabbed Interface | `/admin/manage-store` |
| **Flash Sales** | Time-limited promotions with discount highlighting | Service Layer | `/admin/flash-sales` |

### Architectural Highlights

- **Layered Service Pattern (Feature 2.1):** `HistoryService` encapsulates all filtering logic, decoupling controllers from database queries
- **Pub-Sub Pattern (Features 2.2 & 2.3):** Services publish events that trigger alerts and notifications without tight coupling
- **Configuration-Driven:** `LOW_STOCK_THRESHOLD` and `ORDER_HISTORY_PAGE_SIZE` in `Config` allow runtime tuning
- **Portal-Based Admin:** Unified dashboard with intuitive navigation to User Admin, Manage Store, and Returns Portal

## ✅ Checkpoint 3 Foundation

- **Returns & Refunds (RMA):** Full customer + admin workflow with policy checks, partial approvals, evidence uploads, and refund orchestration via `ReturnsService` + `RefundService`.
- **Containerized Deployment:** `deploy/dockercompose.yml`, production-ready `Dockerfile`, and entrypoint scripts bring up PostgreSQL, seeds, migrations, and Gunicorn with one command.
- **Observability & SLO Evidence:** Structured logs, `/health`, `/admin/metrics`, and `/admin/dashboard` expose KPIs, Quality Scenario widgets (A.1 & P.1), and refund success telemetry required for runtime verification.
- **Quality Automation:** Additional pytest suites (`tests/test_returns_service.py`, `tests/test_returns_api.py`, `tests/test_business_metrics.py`, etc.) cover the new domain logic plus metrics accuracy.
- **Runbook-Driven Demo:** `docs/Runbook.md` describes the Docker → Dashboard → Returns demo script used for grading, including how to force failures for availability scenarios.
- **Automated Load Harness:** `scripts/performance_scenario_runner.py` floods `/checkout` with configurable bursts so you can reproduce Performance Scenario P.1 on-demand (paired with `THROTTLING_MAX_RPS` in `.env`).

## 🚀 Project Description

This Retail Management System is a full-stack web application designed to handle the core operations of a retail business. The system provides:

### Key Features
- **User Management**: Registration, login, and session management with security measures
- **Product Catalog**: Product management with pricing, inventory, and detailed attributes
- **Shopping Cart**: Dynamic cart with real-time calculations including discounts, shipping fees, and import duties
- **Payment Processing**: Support for both cash and card payments with circuit breaker protection
- **Order Management**: Complete sales tracking with detailed receipts and audit logging
- **Order History (CP4)**: Filter and search past orders by status, date range, and keyword
- **Inventory Management**: Real-time stock updates with concurrency control and conflict resolution
- **Low Stock Alerts (CP4)**: Admin dashboard displays products below configurable threshold
- **Returns & Refunds**: Rich RMA workflow (customer + admin) with multi-item validation and up to 20 uploaded evidence photos per request
- **RMA Notifications (CP4)**: In-app notifications when return status changes (Pub-Sub pattern)
- **Flash Sales**: High-performance flash sale system with throttling and queuing
- **Partner (VAR) Catalog Ingest (CP2)**: Full implementation of partner catalog integration with CSV/JSON feeds, validation, and scheduled sync
- **Quality Tactics**: 14+ enterprise-grade quality tactics implemented and tested

### Technical Architecture
- **Backend**: Flask (Python web framework) with quality tactics implementation
- **Database**: PostgreSQL with SQLAlchemy ORM and ACID compliance
- **Frontend**: HTML templates with CSS and JavaScript
- **Testing**: Comprehensive test suite with 224+ tests and 100% quality scenario compliance
- **Security**: Password hashing, input validation, API authentication, and SQL injection prevention
- **Quality Patterns**: Circuit breakers, graceful degradation, retry mechanisms, feature toggles
- **Performance**: Throttling, queuing, concurrency control, and monitoring
- **Integration**: Adapter patterns, publish-subscribe, message brokers

## 🔗 Partner (VAR) Catalog Ingest (CP2)

The Partner Catalog Ingest feature enables seamless integration with external partner/VAR (Value-Added Reseller) systems, fulfilling the Checkpoint 2 requirements:

### Features Implemented

| Requirement | Implementation | ADRs |
|-------------|----------------|------|
| **Ingest partner product feed (CSV/JSON)** | `PartnerCatalogService.ingest_csv_file()` / `ingest_json_file()` via Adapter pattern | ADR 8, ADR 9 (M.1) |
| **Validate, transform, and upsert items** | Input validation (SQL injection, XSS), data transformation, upsert logic | ADR 7 (S.2) |
| **Schedule periodic ingestion** | Background scheduler thread with configurable sync frequency per partner | - |

### How to Use

1. **Navigate to Manage Store** (`/admin/manage-store`) and select the **Partner Catalog** tab
2. **Add a Partner**: Click "Add Partner" and provide name, optional API endpoint, and sync frequency
3. **Upload Catalog File**: Drag & drop or click to upload CSV/JSON file
4. **Manual Sync**: Click "Sync Now" to trigger API-based sync (requires API endpoint)
5. **View Statistics**: See total partners, products synced, and scheduler status

### CSV Format Example
```csv
id,name,description,price,stock,country_of_origin
SKU001,Widget A,High-quality widget,29.99,100,USA
SKU002,Gadget B,Premium gadget,49.99,50,China
```

### JSON Format Example
```json
{
  "products": [
    {"id": "SKU001", "name": "Widget A", "price": 29.99, "stock": 100},
    {"id": "SKU002", "name": "Gadget B", "price": 49.99, "stock": 50}
  ]
}
```

### API Endpoint
Partners can push catalog updates directly via API:

```bash
curl -X POST http://localhost:5000/api/partner/ingest \
  -H "X-API-Key: pk_1_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"products": [{"id": "SKU001", "name": "Widget", "price": 19.99, "stock": 100}]}'
```

### Quality Scenarios Addressed

| Scenario | Tactic | Response Measure |
|----------|--------|------------------|
| **S.1**: Unauthorized API access | Authenticate Actors (ADR 6) | 100% unauthorized attempts denied |
| **S.2**: SQL injection in product data | Validate Input (ADR 7) | Zero malicious payloads reach DB |
| **M.1**: New partner format (XML) | Adapter Pattern (ADR 9) | < 20 person-hours to add new format |
| **I.2**: New reporting consumer | Publish-Subscribe (ADR 16) | Zero code changes in ingest module |

## 📊 Interactive Quality Scenario Monitoring (CP4)

The Quality Scenario Monitoring feature allows super admins and admins to interactively test and verify the A.1 (Availability) and P.1 (Performance) quality scenarios in real-time.

### Features

| Control | Description | Target Scenario |
|---------|-------------|-----------------|
| **Failure Rate Slider** | Adjust simulated payment failure rate (0-100%) | A.1 Availability |
| **Circuit Breaker Threshold** | Configure failure count before circuit opens (1-20) | A.1 Availability |
| **Recovery Timeout** | Set circuit breaker recovery time (10-300s) | A.1 Availability |
| **Simulated Load Slider** | Set request rate for load testing (10-2000 RPS) | P.1 Performance |
| **Throttle Limit** | Configure max allowed RPS (10-1000) | P.1 Performance |
| **Processing Time** | Simulate request processing delay (10-1000ms) | P.1 Performance |

### How to Use

1. **Navigate** to `/admin/quality-monitoring` or click "Live Test" in the Quality Scenarios section of the dashboard
2. **Configure Parameters** using sliders to set test conditions
3. **Enable/Disable** scenarios using the toggle switches
4. **Run Tests** by clicking the "Run Test" button for each scenario
5. **View Results** in real-time in the test results log panel
6. **Reset State** using the Reset buttons to clear circuit breaker or throttling state

### Quality Scenario Targets

| Scenario | Metric | Target |
|----------|--------|--------|
| **A.1 Availability** | Success Rate | ≥99% |
| **A.1 Availability** | MTTR | <5 minutes |
| **P.1 Performance** | P95 Latency | ≤500ms |

### API Endpoints

```bash
# Run Availability Test
curl -X POST http://localhost:5000/admin/quality-monitoring/test/availability \
  -H "Content-Type: application/json" \
  -d '{"failure_rate": 10, "threshold": 5, "timeout": 60}'

# Run Performance Test
curl -X POST http://localhost:5000/admin/quality-monitoring/test/performance \
  -H "Content-Type: application/json" \
  -d '{"simulated_load": 500, "throttle_limit": 100, "processing_time": 50}'

# Reset Circuit Breaker
curl -X POST http://localhost:5000/admin/quality-monitoring/reset/availability

# Reset Throttling State
curl -X POST http://localhost:5000/admin/quality-monitoring/reset/performance
```

## 🔄 Returns & Refunds Workflow (CP3)

- Customers access `/returns` to submit RMAs tied to completed orders, choose reasons, quantities, and upload up to 20 evidence photos (stored under `static/uploads/returns`).
- Admins manage `/admin/returns` to authorize, track shipments, record inspections, and trigger refunds (card, store credit, cash, or original method).
- The workflow enforces policy windows (`RETURN_WINDOW_DAYS`), duplicate prevention, max quantity per line, photo limits, paid-sale validation, and positive-quantity checks (covered in `tests/test_returns_service.py`).
- `RefundService` reuses the payment circuit breaker and inventory adjustments so refunds remain consistent with earlier flash-sale tactics.
- Structured events (`refund_failed`, `returns_created`) are captured for observability and surfaced on the dashboard + metrics endpoint.

## 🎯 Quality Attributes & Tactics Implementation

This system implements **14+ quality tactics** across **7 quality attributes** as required for Checkpoint 2:

### Availability (3 tactics)
- **Circuit Breaker Pattern**: Prevents cascading failures during payment service outages
- **Graceful Degradation**: Queues orders when services are unavailable
- **Rollback & Retry**: Handles transient failures with automatic recovery

### Security (2 tactics)
- **Authenticate Actors**: API key validation for partner integrations
- **Validate Input**: SQL injection prevention and input sanitization

### Performance (4 tactics)
- **Throttling**: Rate limiting for flash sale load management
- **Queuing**: Asynchronous order processing
- **Concurrency Control**: Database locking for stock updates
- **Performance Monitoring**: Real-time system metrics collection

### Modifiability (3 tactics)
- **Adapter Pattern**: Support for multiple partner data formats (CSV, JSON, XML)
- **Feature Toggle**: Runtime feature control without deployment
- **Use Intermediary**: Decoupled partner data processing

### Integrability (3 tactics)
- **Tailor Interface**: External API integration with adapters
- **Publish-Subscribe**: Decoupled service communication
- **Message Broker**: Asynchronous message processing

### Testability (2 tactics)
- **Record/Playback**: Test reproducibility and load simulation
- **Dependency Injection**: Isolated testing with mock services

### Usability (2 tactics)
- **Error Recovery**: User-friendly error messages and recovery suggestions
- **Progress Indicator**: Long-running operation feedback

## 📋 Prerequisites

Before setting up the project, ensure you have the following installed:

- **Python 3.10+** ([Download here](https://www.python.org/downloads/))
- **PostgreSQL 12+** ([Download here](https://www.postgresql.org/download/))
- **Git** ([Download here](https://git-scm.com/downloads))

## ⚡ Quick Start

### Option A – Docker Compose (recommended)
1. Duplicate the sample environment (or update your existing `.env`) with DB + secret values.
2. Run `docker compose -f deploy/dockercompose.yml up --build`.
3. Navigate to `http://localhost:5000`, log in as `super_admin / super_admin_92587`, and explore `/returns`, `/admin/returns`, and `/admin/dashboard`.
4. Shut down with `docker compose -f deploy/dockercompose.yml down` (add `-v` to reset the seed data).

### Option B – Local virtualenv
1. Follow the setup steps below (venv, dependencies, `.env`, database init).
2. Run `python run.py`.
3. Execute `python scripts/bootstrap_super_admin.py` once to seed the admin account.
4. Use the `docs/Runbook.md` demo script to replay both SLO scenarios locally.

## 🛠️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/alisavictory7/Retail-Management-System---Checkpoint-3.git
cd Retail-Management-System---Checkpoint-3
```

### 2. Create and Activate Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the project root with your database credentials:

```env
DB_USERNAME=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=retail_system
```

## 🗄️ Database Setup

### Option 1: Using pgAdmin4 (Recommended for Windows)

Since you have pgAdmin4 open, this is the easiest method:

1. **Create Database in pgAdmin4:**
   - Right-click on "Databases" in the left panel
   - Select "Create" → "Database..."
   - Name: `retail_system` (or `retail_management`)
   - Click "Save"

2. **Initialize Database Schema:**
   ```powershell
   # Use full path to psql (replace with your PostgreSQL version if different)
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d retail_system -f db/init.sql
   ```
   - Enter your postgres password when prompted

### Option 2: Using Command Line

#### For Windows Users:

1. **If psql is not recognized, use full path:**
   ```powershell
   # Check your PostgreSQL version first
   Get-ChildItem "C:\Program Files\PostgreSQL" -ErrorAction SilentlyContinue
   
   # Use full path (adjust version number as needed)
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres
   ```

2. **Create Database:**
   ```sql
   CREATE DATABASE retail_system;
   CREATE USER retail_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE retail_system TO retail_user;
   \q
   ```

3. **Initialize Schema:**
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d retail_system -f db/init.sql
   ```

#### For macOS/Linux Users:
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE retail_system;

# Create user (optional, you can use existing user)
CREATE USER retail_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE retail_system TO retail_user;

# Exit PostgreSQL
\q

# Initialize schema
psql -U postgres -d retail_system -f db/init.sql
```

### 3. Verify Database Setup
You can verify the setup by connecting to your database and checking the tables:

**Using pgAdmin4:**
- Expand your `retail_system` database
- Expand "Schemas" → "public" → "Tables"
- You should see: User, Product, Sale, Payment, SaleItem, FailedPaymentLog

**Using Command Line:**
```powershell
# Windows
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d retail_system

# macOS/Linux
psql -U postgres -d retail_system
```

Then run:
```sql
\dt  # List all tables
SELECT * FROM "Product";  # View sample products
\q
```

## 🐳 Docker & Compose Deployment

Prefer a reproducible local stack? Run everything with Docker:

1. **Copy the environment template**
   ```bash
   # macOS/Linux
   cp env.example .env

   # Windows (Command Prompt)
   copy env.example .env
   ```
   Update the secrets (e.g., `DB_PASSWORD`, `SECRET_KEY`) before continuing.

2. **Build and start the stack**
   ```bash
   docker compose -f deploy/dockercompose.yml up --build
   ```
   - `db` runs PostgreSQL 15 and automatically executes `db/init.sql`, the CP3 migration, and the returns demo seed via `/docker-entrypoint-initdb.d`.
   - `web` builds the Flask app image (Python 3.12 slim) and serves it via Gunicorn on port `5000`.

3. **Verify**
   - Visit `http://localhost:5000` for the storefront.
   - Log in as user ID 1 (or create a new account) and navigate to `/returns` and `/admin/returns`.

4. **Shut down**
   ```bash
   docker compose -f deploy/dockercompose.yml down           # stop containers
   docker compose -f deploy/dockercompose.yml down -v        # stop + remove the postgres volume
   ```

> **Troubleshooting tips**
> - Use `docker compose -f deploy/dockercompose.yml logs -f web` to watch application logs.
> - If you need to reseed the database, remove the `postgres_data` volume (`docker compose -f deploy/dockercompose.yml down -v`) and re-run `docker compose -f deploy/dockercompose.yml up --build`.

## 👥 Accounts & Roles

- On first startup, the system auto-seeds a super admin:
  - Username: `super_admin`
  - Password: `super_admin_92587` (override via `SUPER_ADMIN_PASSWORD`)
- In Docker this bootstrap happens automatically. For local development (venv) run:
  ```bash
  python scripts/bootstrap_super_admin.py
  ```
- Visit `/admin/users` after logging in to grant or revoke admin roles for other accounts.
- To let someone self-register as an admin, share the `SUPER_ADMIN_TOKEN` (defaults to `CP3_SUPERADMIN_TOKEN_N9fA7qLzX4`). During registration they must select “Admin” and enter the token; otherwise they’ll be created as a regular customer.

## 📊 Observability & Runtime Evidence

### Observability Endpoints

| Endpoint | Purpose | Access |
|----------|---------|--------|
| `GET /health` | Readiness/liveness probe for Docker health checks | Public |
| `GET /admin/metrics` | JSON snapshot of counters, histograms, MTTR timers, events | Admin |
| `GET /admin/dashboard` | Visual dashboard with KPIs, Quality Scenarios, Low Stock Alerts | Admin |
| `GET /api/notifications` | User's notification list with unread count (CP4) | Authenticated |
| `GET /api/admin/low-stock` | Low stock alert summary JSON (CP4) | Admin |
| `GET /order-history` | Order history with filtering (CP4) | Authenticated |
| `POST /api/partner/ingest` | Partner catalog ingestion via API (CP2) | Partner API Key |
| `POST /admin/partner-catalog` | Admin partner management actions (CP2) | Admin |

### How Logs & Metrics Support Debugging

The observability stack helps developers and operators quickly diagnose issues:

**Structured Logs** (`src/observability/logging_config.py`): Every HTTP request gets a unique `request_id` (correlation ID). Log entries include timestamp, level, request_id, user_id, endpoint, duration. View logs via `docker compose -f deploy/dockercompose.yml logs -f web`. **Tip:** Grep for `request_id` to trace a single request.

**Counters** (track occurrences): `http_requests_total`, `http_errors_total`, `orders_submitted_total`, `orders_accepted_total`, `returns_created_total`. **Tip:** Compare submitted vs accepted to identify dropped orders.

**Histograms** (latency distribution): `http_request_latency_ms` with p50/p95/p99, `order_processing_latency_ms`, `payment_circuit_mttr_seconds`. **Tip:** p95 > 500ms indicates performance degradation.

**Events** (timestamped occurrences): `refund_failed`, `payment_circuit_opened`, `order_completed`, `rma_status_changed` (CP4), `low_stock_alert` (CP4). **Tip:** Events show exact timestamps for incident timeline.

### CP4 Observability Enhancements

- **Low Stock Alerts** appear in admin dashboard with product names, current stock, and threshold
- **RMA Notifications** create events monitored via `/admin/metrics`
- **Order History** queries are logged with filter parameters for debugging

- **Endpoints**
  - `GET /health`: readiness/liveness probe (used by Docker health checks).
  - `GET /admin/metrics`: JSON snapshot of counters, gauges, latency histograms (p95), MTTR timers, and structured events (`refund_failed`, `payment_circuit_opened`, etc.).
  - `GET /admin/dashboard`: Tailwind dashboard that visualizes DB health, HTTP latency, refund success, RMA KPIs, and the Quality Scenario widgets for Availability A.1 + Performance P.1. Sign in as an admin to access it.
- **Structured logs** are enabled via `src/observability/logging_config.py` and surfaced through `docker compose -f deploy/dockercompose.yml logs web`. Every request includes a correlation ID, making it easy to link dashboard widgets, metrics, and logs.
- **SLO verification workflow**
  1. Follow `docs/Runbook.md` to start the Docker stack and log in.
  2. (A.1) Temporarily set `PAYMENT_REFUND_FAILURE_PROBABILITY=1.0` in `.env`, approve the seeded `RMA-CP3-DEMO-001`, and trigger a refund. Observe the dashboard widget flip to “Fulfilled,” the MTTR histogram, and `refunds_failed_total` increment.
     - While the failure simulation is active, manual methods (cash / store credit) are disabled so the refund must go through the card/original channel to exercise the circuit breaker.
  3. (P.1) Lower the throttling window (e.g., `THROTTLING_MAX_RPS=2`, `THROTTLING_WINDOW_SECONDS=1`) and run `python scripts/performance_scenario_runner.py --runs 30 --delay 0.02 --product-id 2`. Confirm 429 throttling responses, the yellow UI banner, and `/admin/metrics` entries for elevated `http_requests_total` plus the sub-500 ms p95 latency.
- **Artifacts** (captured in `docs/QUALITY_SCENARIO_VALIDATION_REPORT.md`) include structured log samples and the metrics JSON excerpt required by the rubric.

The initialization scripts (Docker entrypoint or manual DB setup) create all necessary tables, insert sample data, and ensure relationships are wired before observability is exercised.

## 🚀 Running the Application

### 1. Start the Flask Application
```bash
python run.py
```

The application will start on `http://localhost:5000`

### 2. Access the Application
Open your web browser and navigate to:
- **Main Application**: http://localhost:5000
- **Login Page**: http://localhost:5000/login
- **Registration Page**: http://localhost:5000/register

### 3. Test User Credentials
The system comes with pre-configured test users:
- **Username**: `testuser`, **Password**: `password123`
- **Username**: `john_doe`, **Password**: `password123`
- **Username**: `jane_smith`, **Password**: `password123`

## 🧪 Testing Instructions

### Quality Scenario Testing
The project includes comprehensive test suites for quality attributes and tactics validation:

```bash
# Run comprehensive quality scenario tests (100% compliance)
python comprehensive_quality_scenarios_test.py

# Run all quality tactics tests
pytest tests/ -v

# Run specific quality attribute tests
pytest tests/test_availability_tactics.py -v
pytest tests/test_security_tactics.py -v
pytest tests/test_performance_tactics.py -v

# Run integration tests
pytest tests/test_integration.py -v

# Run comprehensive demonstration
pytest tests/test_comprehensive_demo.py -v -s

# Run detailed test suite with reporting
python tests/run_all_tests.py

# Run simple test runner for quick validation
python tests/simple_test_runner.py
```

Additional CP3-focused pytest targets:
- `pytest tests/test_returns_service.py -v`
- `pytest tests/test_returns_api.py -v`
- `pytest tests/test_business_metrics.py -v`
- `pytest tests/test_observability_metrics.py -v`

### Performance Scenario Helper

Toggle the `.env` knobs with the helper script instead of editing by hand:

```cmd
python scripts\apply_env_preset.py availability
```

Available presets:

- `availability` – high RPS, no forced failures.
- `availability-failure` – same throttle, but sets `PAYMENT_REFUND_FAILURE_PROBABILITY=1.0` to trip the payment circuit breaker for MTTR evidence.
- `performance` – low `THROTTLING_MAX_RPS` to demonstrate Manage Event Arrival / throttling.

#### Prefer one-click `.cmd` launchers?

```cmd
# Availability load (applies preset, restarts web, restocks, fires burst)
scripts\run_availability_load.cmd

# Flip to forced-failure mode and follow the on-screen browser instructions
scripts\run_availability_failure.cmd

# Performance throttling demo (applies preset, restarts web, restocks, fires burst)
scripts\run_performance_load.cmd
```

Use the automation harness to hammer `/checkout` without manually refreshing the UI:

```bash
# Lower the throttle window for demos
echo THROTTLING_MAX_RPS=2 >> .env

# From the repo root (baseline burst)
python scripts/performance_scenario_runner.py \
  --base-url http://localhost:5000 \
  --username super_admin \
  --password super_admin_92587 \
  --product-id 2 \
  --runs 30 \
  --delay 0.02

# Approximate the "1,000 order requests / second" stimulus
python scripts/performance_scenario_runner.py \
  --base-url http://localhost:5000 \
  --username super_admin \
  --password super_admin_92587 \
  --product-id 2 \
  --runs 1000 \
  --delay 0 \
  --concurrency 250
```

Watch `/admin/dashboard` → Availability A.1 + Performance P.1 cards and `/admin/metrics`:
- A.1: run the high-concurrency burst, then process the seeded refund (with `PAYMENT_REFUND_FAILURE_PROBABILITY=1.0`) to capture ≥99 % acceptance and <5 min MTTR. The widget now marks “Needs Traffic” until the counters have real data.
- P.1: run the smaller throttling burst and confirm p95 latency stays ≤ 500 ms for accepted requests.

If the script logs `HTTPConnectionPool(... read timeout=10.0)` and the dashboard still shows `0 / 0`, either lower `--concurrency` (e.g., 100) or scale Gunicorn by exporting `GUNICORN_WORKERS`, `GUNICORN_THREADS`, and `GUNICORN_TIMEOUT` before `docker compose up` (defaults are 4/4/90 in the Dockerfile). If inventory for product 2 gets low, reseed via `docker compose -f deploy/dockercompose.yml down -v` before re-running the script.


### Test Categories

#### 1. Quality Attribute Tests
Tests individual quality tactics and patterns:
- **Availability**: Circuit breaker, graceful degradation, rollback, retry, removal from service
- **Security**: Authentication, input validation, API key management
- **Performance**: Throttling, queuing, concurrency control, monitoring
- **Modifiability**: Adapter pattern, feature toggles, data format support
- **Integrability**: API adapters, message broker, publish-subscribe
- **Testability**: Record/playback, dependency injection
- **Usability**: Error handling, progress indicators

#### 2. Integration Tests (`test_integration.py`)
Tests complete workflows and system integration:
- User registration and authentication flow
- Cart management and checkout process
- Payment processing with circuit breaker protection
- Flash sale order processing with throttling
- Partner catalog ingestion with validation
- Session management and persistence
- Returns + refunds API flow (customer + admin)

#### 3. Comprehensive Quality Scenarios
Tests all 15 quality scenarios from Checkpoint2_Revised.md:
- Flash sale overload handling
- Transient failure recovery
- Partner authentication and validation
- Feature toggle runtime control
- Performance under load
- External API integration
- Test reproducibility
- User experience improvements

## 📚 Documentation

The project includes comprehensive documentation:

### Core Documentation
- **`Project Deliverable 2 Documentation.md`** - Complete Checkpoint 2 documentation with quality scenarios and ADRs
- **`Checkpoint2_Revised.md`** - Checkpoint 2 requirements and specifications
- **`Checkpoint1.md`** - Checkpoint 1 documentation and requirements
- **`Project Deliverable 1.md`** - Project Deliverable 1 documentation
- **`Checkpoint3.md`** - (New) Summary of CP3 tests, SLOs, and runtime evidence
- **`docs/Runbook.md`** - Docker → Dashboard → Returns demo walkthrough

### Quality Assurance Documentation
- **`QUALITY_SCENARIO_VALIDATION_REPORT.md`** - Detailed quality scenario validation results
- **`TESTING_SUMMARY.md`** - Comprehensive testing summary and results
- **`POSTGRESQL_CONSISTENCY_UPDATE.md`** - Database consistency and PostgreSQL usage documentation

### Technical Documentation
- **`docs/ADR/`** - Architectural Decision Records for all quality tactics, including CP4 feature decisions
- **`docs/UML/`** - UML diagrams including class diagrams, sequence diagrams, and deployment diagrams (updated for CP4)
- **`docs/VIDEO_SCRIPT.md`** - Comprehensive 15-minute demo video script covering all CP4 features
- **`tests/README.md`** - Comprehensive test suite documentation

### Quality Scenario Validation
```bash
# Run comprehensive quality scenario validation
python comprehensive_quality_scenarios_test.py

# Expected output: 100% success rate (15/15 scenarios fulfilled)
# All 7 quality attributes validated
# All response measures verified
```

## 📁 Project Structure

```
Retail-Management-System---Checkpoint-4/
├── src/                             # Application code
│   ├── main.py                      # Flask routes & app initialization
│   ├── config.py                    # Configuration settings
│   ├── database.py                  # Database connection
│   ├── models.py                    # SQLAlchemy models
│   ├── blueprints/
│   │   └── returns.py               # Customer/admin RMA routes
│   ├── observability/               # Logging + metrics engine
│   │   ├── metrics.py
│   │   ├── business_metrics.py
│   │   └── health.py
│   ├── services/                    # Domain services
│   │   ├── flash_sale_service.py    # Flash sale management
│   │   ├── history_service.py       # CP4: Order history filtering
│   │   ├── inventory_service.py     # Stock management
│   │   ├── low_stock_alert_service.py  # CP4: Low stock alerts
│   │   ├── notification_service.py  # CP4: RMA notifications
│   │   ├── partner_catalog_service.py  # CP2: Partner VAR Catalog Ingest
│   │   ├── payment_service.py
│   │   ├── refund_service.py
│   │   └── returns_service.py
│   └── tactics/                     # Quality tactics implementation
│
├── tests/                           # Unit tests
│   ├── test_returns_service.py
│   ├── test_returns_api.py
│   ├── test_business_metrics.py
│   ├── test_quality_scenario_*.py
│   └── ...
│
├── db/                              # Database schema
│   ├── init.sql                     # Initial schema + seed data
│   ├── migrations/                  # Schema migrations
│   └── seeds/                       # Demo seed data
│
├── docs/
│   ├── ADR/                         # Architectural Decision Records
│   │   ├── ADR_CP3.md
│   │   └── ADR_CP4.md
│   ├── UML/                         # UML diagrams (PlantUML)
│   │   ├── use-case-diagram.puml
│   │   ├── class-diagram.puml
│   │   ├── deployment-diagram.puml
│   │   ├── package-diagram.puml
│   │   └── sequence-diagram-*.puml
│   └── Runbook.md
│
├── templates/                       # HTML templates
│   ├── partials/navbar.html         # Unified navigation
│   ├── admin_dashboard.html         # Portal-based dashboard (CP4)
│   ├── manage_store.html            # Products + Stock + Flash Sales + Partner Catalog (CP2/CP4)
│   ├── order_history.html           # Order history with filters (CP4)
│   ├── admin_users.html             # User administration
│   ├── admin_returns.html           # Returns management
│   └── ...
│
├── static/                          # Static assets
│   ├── css/
│   ├── js/
│   └── uploads/returns/             # Evidence photos
│
├── deploy/                          # Docker Compose files
│   └── dockercompose.yml
├── docker/                          # Container helpers
│   ├── entrypoint.sh
│   └── wait_for_db.py
├── scripts/                         # Utility scripts
│
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Container build
├── .gitignore                       # Git ignore rules
└── .env                             # Environment variables (not in repo)
│   └── Runbook.md
├── Checkpoint1.md
├── Checkpoint2_Revised.md
├── Project Deliverable 2 Documentation.md
├── Checkpoint3.md
├── comprehensive_quality_scenarios_test.py
├── requirements.txt
└── run.py
```

## 🔧 Configuration

### Environment Variables
The application uses the following environment variables (configured in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_USERNAME` | PostgreSQL username | Required |
| `DB_PASSWORD` | PostgreSQL password | Required |
| `DB_HOST` | Database host | localhost |
| `DB_PORT` | Database port | 5432 |
| `DB_NAME` | Database name | retail_management |
| `THROTTLING_MAX_RPS` | Requests allowed per second before `/checkout` throttles | 100 |
| `THROTTLING_WINDOW_SECONDS` | Sliding window size used by throttling manager | 1 |
| `LOW_STOCK_THRESHOLD` | Stock level that triggers low stock alert (CP4) | 5 |
| `ORDER_HISTORY_PAGE_SIZE` | Number of orders per page in history view (CP4) | 20 |

### Application Settings
Key application settings in `src/main.py`:
- **Secret Key**: Used for session management
- **Debug Mode**: Enabled for development
- **Host**: 0.0.0.0 (accessible from all interfaces)
- **Port**: 5000

## 🛡️ Security Features

- **Password Hashing**: Uses Werkzeug's secure password hashing
- **Session Management**: Secure session handling with Flask
- **Input Validation**: Server-side validation for all user inputs with SQL injection prevention
- **API Authentication**: Partner API key validation and management
- **SQL Injection Protection**: Uses SQLAlchemy ORM for safe database queries
- **Payment Security**: Card number validation and secure payment processing
- **Audit Logging**: Comprehensive logging of all security-related events
- **Input Sanitization**: Bleach library for HTML sanitization and XSS prevention

## ✅ Quality Scenario Validation Results

The system has been thoroughly tested and validated against all quality scenarios:

### Test Results Summary
- **Total Quality Scenarios**: 15
- **Fulfilled Scenarios**: 15 ✅
- **Success Rate**: **100.0%** 🎉
- **Total Tests**: 224+ tests passing

### Quality Attribute Compliance
| Quality Attribute | Scenarios | Success Rate | Status |
|------------------|-----------|--------------|---------|
| **Availability** | 3/3 | 100% | ✅ **PERFECT** |
| **Security** | 2/2 | 100% | ✅ **PERFECT** |
| **Performance** | 2/2 | 100% | ✅ **PERFECT** |
| **Modifiability** | 2/2 | 100% | ✅ **PERFECT** |
| **Integrability** | 2/2 | 100% | ✅ **PERFECT** |
| **Testability** | 2/2 | 100% | ✅ **PERFECT** |
| **Usability** | 2/2 | 100% | ✅ **PERFECT** |

### Response Measures Verified
- **99% order acceptance** during flash sale overload (1,000 RPS stimulus)
- **< 5 minutes MTTR** for payment service recovery
- **100% unauthorized access prevention** for partner APIs
- **Zero malicious payloads** reaching the database
- **< 20 person-hours** for new partner format integration
- **< 5 seconds** feature toggle response time
- **< 500ms latency** for 95% of flash sale requests
- **< 50ms database lock wait time** for stock updates
- **< 40 person-hours** for external API integration
- **Zero code changes** for new service consumers
- **< 1 hour** workload replication for testing
- **< 5 seconds** test execution with dependency injection
- **< 90 seconds** user error recovery time
- **> 80% user satisfaction** for long-running tasks

### Runtime SLO Evidence (Checkpoint 3)

| Scenario | Target | Observed (Docker demo) | Instrumentation |
|----------|--------|------------------------|-----------------|
| **A.1 Availability** | ≥99 % orders accepted (completed or queued) & MTTR < 5 min while 1k RPS flash-sale traffic forces the payment connector to trip the circuit breaker | 99.5 % success, 2 min MTTR (`docs/QUALITY_SCENARIO_VALIDATION_REPORT.md`) | `orders_submitted_total`, `orders_accepted_total`, `payment_circuit_mttr_seconds`, `refunds_failed_total`, structured events rendered on `/admin/dashboard` |
| **P.1 Performance** | p95 `POST /checkout` latency < 500 ms under flash-sale load (Manage Event Arrival / throttling) | 350 ms p95, 200 ms avg | `order_processing_latency_ms` histogram & throttling counters, surfaced on `/admin/dashboard` and `/admin/metrics` |

Reproduce both scenarios with the steps in `docs/Runbook.md`.

## 🚨 Troubleshooting

### Common Issues

#### 'psql' is not recognized (Windows)
**Error:** `'psql' is not recognized as an internal or external command`

**Solutions:**
1. **Use full path to psql:**
   ```powershell
   # Instead of: psql -U postgres
   # Use: & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres
   ```

2. **Add PostgreSQL to PATH permanently:**
   - Press `Win + R`, type `sysdm.cpl`, press Enter
   - Go to "Advanced" tab → "Environment Variables"
   - In "System Variables", find "Path" and click "Edit"
   - Click "New" and add: `C:\Program Files\PostgreSQL\17\bin`
   - Click "OK" on all dialogs
   - Restart Command Prompt/PowerShell

3. **Use pgAdmin4 instead:**
   - Create database through pgAdmin4 GUI
   - Use full path for command line operations

#### Database Connection Errors
```bash
# Check if PostgreSQL is running
sudo service postgresql status  # Linux
brew services list | grep postgres  # macOS
# Windows: Check Services.msc for "postgresql" service

# Verify database exists
psql -U your_username -l  # Linux/macOS
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -l  # Windows
```

#### Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000  # macOS/Linux
netstat -ano | findstr :5000  # Windows

# Kill the process or change port in run.py
```

#### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Getting Help
If you encounter issues:
1. Check the console output for error messages
2. Verify all environment variables are set correctly
3. Ensure PostgreSQL is running and accessible
4. Check that all dependencies are installed correctly

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Happy Shopping! 🛒**
