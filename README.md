# Retail Management System - Checkpoint 3

**Author:** Alisa  
**Repository:** https://github.com/alisavictory7/Retail-Management-System---Checkpoint-3

Checkpoint 3 focuses on making the system deployable, observable, and reliable, while also introducing a realistic new feature: Returns & Refunds (RMA workflow).

## 🚀 Project Description

This Retail Management System is a full-stack web application designed to handle the core operations of a retail business. The system provides:

### Key Features
- **User Management**: Registration, login, and session management with security measures
- **Product Catalog**: Product management with pricing, inventory, and detailed attributes
- **Shopping Cart**: Dynamic cart with real-time calculations including discounts, shipping fees, and import duties
- **Payment Processing**: Support for both cash and card payments with circuit breaker protection
- **Order Management**: Complete sales tracking with detailed receipts and audit logging
- **Inventory Management**: Real-time stock updates with concurrency control and conflict resolution
- **Flash Sales**: High-performance flash sale system with throttling and queuing
- **Partner Integration**: External partner catalog ingestion with authentication and validation
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
   cp env.example .env  # or copy manually on Windows
   ```
   Update the secrets (e.g., `DB_PASSWORD`, `SECRET_KEY`) before continuing.

2. **Build and start the stack**
   ```bash
   docker compose up --build
   ```
   - `db` runs PostgreSQL 15 and automatically executes `db/init.sql`, the CP3 migration, and the returns demo seed via `/docker-entrypoint-initdb.d`.
   - `web` builds the Flask app image (Python 3.12 slim) and serves it via Gunicorn on port `5000`.

3. **Verify**
   - Visit `http://localhost:5000` for the storefront.
   - Log in as user ID 1 (or create a new account) and navigate to `/returns` and `/admin/returns`.

4. **Shut down**
   ```bash
   docker compose down           # stop containers
   docker compose down -v        # stop + remove the postgres volume
   ```

> **Troubleshooting tips**
> - Use `docker compose logs -f web` to watch application logs (structured logging will be added in the observability task).
> - If you need to reseed the database, remove the `postgres_data` volume (`docker compose down -v`) and re-run `docker compose up`.

## 📈 Observability Endpoints

- `GET /health` – lightweight health probe (includes DB status).
- `GET /admin/metrics` – JSON snapshot of counters, gauges, histograms, and recent events (admin only).
- `GET /admin/dashboard` – Tailwind dashboard summarizing KPIs (returns volume, refund success rate, HTTP latency) and recent events. Requires logging in as the admin user (ID 1).
- To demo the availability scenario, temporarily set `PAYMENT_REFUND_FAILURE_PROBABILITY=1.0` in `.env` so every refund triggers the circuit breaker and the dashboard counters.

The initialization script will:
- Create all necessary tables (User, Product, Sale, Payment, SaleItem, FailedPaymentLog)
- Insert sample data including test products and users
- Set up proper foreign key relationships

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

### Quality Assurance Documentation
- **`QUALITY_SCENARIO_VALIDATION_REPORT.md`** - Detailed quality scenario validation results
- **`TESTING_SUMMARY.md`** - Comprehensive testing summary and results
- **`POSTGRESQL_CONSISTENCY_UPDATE.md`** - Database consistency and PostgreSQL usage documentation

### Technical Documentation
- **`docs/ADR/`** - Architectural Decision Records for all quality tactics
- **`docs/UML/`** - UML diagrams including class diagrams, sequence diagrams, and deployment diagrams
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
Retail-Management-System/
├── src/                           # Source code
│   ├── main.py                   # Flask application and routes
│   ├── models.py                 # Database models
│   ├── database.py               # Database configuration
│   ├── services/                 # Business services
│   │   ├── flash_sale_service.py # Flash sale business logic
│   │   └── partner_catalog_service.py # Partner catalog business logic
│   └── tactics/                  # Quality tactics implementation
│       ├── manager.py            # Central quality tactics manager
│       ├── availability.py       # Availability tactics (circuit breaker, retry, etc.)
│       ├── security.py           # Security tactics (auth, validation)
│       ├── performance.py        # Performance tactics (throttling, queuing)
│       ├── modifiability.py      # Modifiability tactics (adapters, toggles)
│       ├── integrability.py      # Integrability tactics (publish-subscribe)
│       ├── testability.py        # Testability tactics (record/playback)
│       ├── usability.py          # Usability tactics (error handling)
│       └── base.py               # Base classes for tactics
├── templates/                     # HTML templates
│   ├── index.html               # Main shopping interface
│   ├── login.html               # Login page
│   ├── register.html            # Registration page
│   └── receipt.html             # Order receipt
├── static/                       # Static assets
│   ├── css/                     # Stylesheets
│   └── js/                      # JavaScript files
├── tests/                        # Comprehensive test suites
│   ├── test_availability_tactics.py    # Availability tests
│   ├── test_security_tactics.py        # Security tests
│   ├── test_performance_tactics.py     # Performance tests
│   ├── test_modifiability_tactics.py   # Modifiability tests
│   ├── test_integrability_tactics.py   # Integrability tests
│   ├── test_testability_tactics.py     # Testability tests
│   ├── test_usability_tactics.py       # Usability tests
│   ├── test_integration.py             # Integration tests
│   ├── test_logic.py                   # Business logic tests
│   ├── test_comprehensive_demo.py      # Comprehensive scenarios
│   ├── run_all_tests.py                # Test runner
│   ├── simple_test_runner.py           # Simple test runner
│   └── conftest.py                     # Test fixtures
├── db/                           # Database files
│   └── init.sql                 # Database initialization script
├── docs/                         # Documentation
│   ├── ADR/                     # Architectural Decision Records
│   └── UML/                     # UML diagrams
├── comprehensive_quality_scenarios_test.py  # Quality scenario validation
├── Project Deliverable 2 Documentation.md  # Checkpoint 2 documentation
├── QUALITY_SCENARIO_VALIDATION_REPORT.md  # Quality scenario validation report
├── TESTING_SUMMARY.md           # Testing summary and results
├── POSTGRESQL_CONSISTENCY_UPDATE.md # Database consistency documentation
├── Checkpoint2_Revised.md       # Checkpoint 2 requirements
├── Checkpoint1.md               # Checkpoint 1 documentation
├── Project Deliverable 1.md     # Project Deliverable 1 documentation
├── requirements.txt              # Python dependencies
└── run.py                       # Application entry point
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
- **99% order acceptance** during flash sale overload
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
