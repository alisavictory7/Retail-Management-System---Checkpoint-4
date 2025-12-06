# Running Super Admin and Regular Customer Simultaneously

This guide explains how to run both a super admin and regular customer session at the same time using Docker.

## Prerequisites

- Docker and Docker Compose installed
- The application is set up and running

## Quick Start

### Step 1: Start Docker Containers

From the project root directory, run:

```bash
docker compose -f deploy/dockercompose.yml up --build
```

Or to run in the background (detached mode):

```bash
docker compose -f deploy/dockercompose.yml up --build -d
```

Wait for the containers to start. You'll see:
- Database container (`db-1`) starting
- Web container (`web-1`) starting and connecting to the database

### Step 2: Access the Application

The application will be available at:
- **URL**: `http://localhost:5000`

## Running Multiple User Sessions

### Method 1: Multiple Browser Windows (Recommended)

1. **Open First Browser Window** (e.g., Chrome)
   - Navigate to `http://localhost:5000`
   - Click "Sign In"
   - Login as **super_admin**:
     - Username: `super_admin`
     - Password: `super_admin_92587`
   - This window is now your **Super Admin** session

2. **Open Second Browser Window** (e.g., Chrome Incognito or Firefox)
   - Navigate to `http://localhost:5000`
   - Click "Sign In"
   - Login as a **regular customer**:
     - If you have a customer account, use those credentials
     - Or click "Register" to create a new customer account
   - This window is now your **Customer** session

### Method 2: Different Browsers

- **Chrome**: Log in as super_admin
- **Firefox** or **Edge**: Log in as regular customer

### Method 3: Browser Profiles

- **Chrome Profile 1**: Super Admin
- **Chrome Profile 2**: Regular Customer

## Default User Accounts

### Super Admin
- **Username**: `super_admin`
- **Password**: `super_admin_92587`
- **Access**: Full admin dashboard, manage store, returns admin, user admin

### Regular Customer
- You can register a new account, or check the database for existing customer accounts
- **Access**: Store, order history, returns (customer view)

## Testing Scenarios

### Scenario 1: Admin Creates Product, Customer Buys It
1. **Super Admin Window**: 
   - Go to "Manage Store" → "Products"
   - Add a new product
2. **Customer Window**:
   - Go to "Store"
   - Add the product to cart and purchase

### Scenario 2: Customer Returns Item, Admin Processes It
1. **Customer Window**:
   - Go to "Returns"
   - Submit a return request
2. **Super Admin Window**:
   - Go to "Returns Admin"
   - Process the return request

### Scenario 3: Low Stock Alert Testing
1. **Super Admin Window**:
   - Create a product with low stock (< 5 units)
   - Check notification bell for low stock alert
2. **Customer Window**:
   - Purchase items to reduce stock further
   - Admin will see updated alerts

## Troubleshooting

### Containers Won't Start
```bash
# Check if containers are running
docker compose -f deploy/dockercompose.yml ps

# View logs
docker compose -f deploy/dockercompose.yml logs

# Restart containers
docker compose -f deploy/dockercompose.yml restart
```

### Port Already in Use
If port 5000 is already in use:
1. Stop the existing service using port 5000
2. Or modify `deploy/dockercompose.yml` to use a different port:
   ```yaml
   ports:
     - "5001:5000"  # Change 5001 to any available port
   ```

### Database Connection Issues
```bash
# Check database container
docker compose -f deploy/dockercompose.yml logs db

# Restart database
docker compose -f deploy/dockercompose.yml restart db
```

### Session Conflicts
- Each browser window/tab maintains its own session
- Cookies are stored per browser/domain
- No conflicts between different users

## Stopping the Application

```bash
# Stop containers (keeps data)
docker compose -f deploy/dockercompose.yml stop

# Stop and remove containers (keeps volumes/data)
docker compose -f deploy/dockercompose.yml down

# Stop and remove everything including data
docker compose -f deploy/dockercompose.yml down -v
```

## Notes

- Both users share the same database, so actions by one user will be visible to the other
- Real-time updates (like notifications) require page refresh
- The application supports multiple concurrent sessions without issues

