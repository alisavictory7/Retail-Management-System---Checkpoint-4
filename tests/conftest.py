# tests/conftest.py
"""
Pytest configuration and fixtures for testing all quality tactics.
This module provides shared test infrastructure and fixtures.
"""

import pytest
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database import Base, get_db
from src.models import *
from src.tactics.manager import QualityTacticsManager
from src.tactics.testability import TestEnvironment, TestabilityManager

@pytest.fixture(scope="session")
def test_db():
    """Create a test database for the entire test session"""
    # Use PostgreSQL test database (consistent with architectural decision)
    # For testing, we'll use a test-specific database
    test_db_url = os.getenv('TEST_DATABASE_URL', 'postgresql://postgres:password@localhost:5432/retail_test')
    
    try:
        engine = create_engine(test_db_url, echo=False)
        Base.metadata.create_all(engine)
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        return engine, SessionLocal
    except Exception as e:
        # If PostgreSQL is not available, fall back to SQLite for testing only
        # This is a temporary fallback for development/testing environments
        print(f"PostgreSQL not available ({e}), falling back to SQLite for testing")
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        return engine, SessionLocal

@pytest.fixture
def db_session(test_db):
    """Create a fresh database session for each test"""
    engine, SessionLocal = test_db
    session = SessionLocal()
    
    try:
        yield session
    finally:
        # Clean up test data to prevent test interference
        try:
            from src.models import (
                OrderQueue, AuditLog, SystemMetrics, TestRecord, FeatureToggle, 
                CircuitBreakerState, MessageQueue, User, Partner, PartnerAPIKey, 
                FlashSale, Sale, ReturnRequest, ReturnItem, Refund, SaleItem
            )
            # Clean up in proper dependency order (most dependent first)
            # Use synchronize_session=False for better performance
            
            # First, clean up return-related tables that reference Sale
            try:
                session.query(Refund).delete(synchronize_session=False)
                session.query(ReturnItem).delete(synchronize_session=False)
                session.query(ReturnRequest).delete(synchronize_session=False)
            except Exception:
                session.rollback()
            
            # Clean up SaleItem before Sale
            try:
                session.query(SaleItem).delete(synchronize_session=False)
            except Exception:
                session.rollback()
            
            # Now clean up the rest
            session.query(PartnerAPIKey).delete(synchronize_session=False)
            session.query(FlashSale).delete(synchronize_session=False)
            session.query(Sale).delete(synchronize_session=False)
            session.query(OrderQueue).delete(synchronize_session=False)
            session.query(AuditLog).delete(synchronize_session=False)
            session.query(SystemMetrics).delete(synchronize_session=False)
            session.query(TestRecord).delete(synchronize_session=False)
            session.query(FeatureToggle).delete(synchronize_session=False)
            session.query(CircuitBreakerState).delete(synchronize_session=False)
            session.query(MessageQueue).delete(synchronize_session=False)
            # Only delete test users/partners, not fixture ones
            session.query(User).filter(User.username.like('test_%')).delete(synchronize_session=False)
            session.query(Partner).filter(Partner.name.like('Test%')).delete(synchronize_session=False)
            session.commit()
        except Exception as e:
            print(f"Database cleanup warning: {e}")
            try:
                session.rollback()
            except:
                pass
        finally:
            session.close()

@pytest.fixture
def quality_manager(db_session):
    """Create a quality tactics manager for testing"""
    config = {
        'throttling': {'max_rps': 10, 'window_size': 1},
        'queue': {'max_size': 100},
        'concurrency': {'max_concurrent': 5, 'lock_timeout': 50},
        'monitoring': {'metrics_interval': 60},
        'usability': {}
    }
    return QualityTacticsManager(db_session, config)

@pytest.fixture
def test_environment(db_session):
    """Create a test environment for record/playback testing"""
    return TestEnvironment(db_session)

@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    import random
    user_id = random.randint(1000, 9999)
    user = User(
        username=f"testuser_{user_id}",
        email=f"test_{user_id}@example.com"
    )
    user.passwordHash = "hashed_password"
    user.role = "customer"
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def sample_products(db_session):
    """Create sample products for testing"""
    products = [
        Product(
            name="Test Product 1",
            description="Test Description 1",
            price=10.99,
            stock=100
        ),
        Product(
            name="Test Product 2", 
            description="Test Description 2",
            price=25.50,
            stock=50
        )
    ]
    for product in products:
        db_session.add(product)
    db_session.commit()
    return products

@pytest.fixture
def sample_partner(db_session):
    """Create a sample partner for testing"""
    import random
    partner_id = random.randint(1000, 9999)
    partner = Partner(
        name=f"Test Partner {partner_id}"
    )
    partner.api_endpoint = f"https://api.partner{partner_id}.com"
    partner.status = "active"
    
    db_session.add(partner)
    db_session.commit()
    
    # Add API key
    api_key = PartnerAPIKey(
        partnerID=partner.partnerID,
        api_key=f"test_api_key_{partner_id}",
        is_active=True
    )
    db_session.add(api_key)
    db_session.commit()
    
    return partner

@pytest.fixture
def sample_flash_sale(db_session, sample_products):
    """Create a sample flash sale for testing"""
    flash_sale = FlashSale(
        productID=sample_products[0].productID,
        discount_percent=20.0,
        max_quantity=10,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    db_session.add(flash_sale)
    db_session.commit()
    return flash_sale

@pytest.fixture
def mock_payment_service():
    """Mock payment service for testing"""
    class MockPaymentService:
        def __init__(self, should_fail=False, failure_rate=0.0):
            self.should_fail = should_fail
            self.failure_rate = failure_rate
            self.call_count = 0
        
        def process_payment(self, amount, payment_method, **kwargs):
            self.call_count += 1
            
            if self.should_fail:
                raise Exception("Mock payment service failure")
            
            if self.failure_rate > 0 and (self.call_count % int(1/self.failure_rate)) == 0:
                raise Exception(f"Mock payment failure (call #{self.call_count})")
            
            return {"status": "success", "transaction_id": f"TXN_{self.call_count}"}
    
    return MockPaymentService

@pytest.fixture
def sample_order_data(sample_user, sample_products):
    """Create sample order data for testing"""
    return {
        'sale_id': 1,
        'user_id': sample_user.userID,
        'items': [
            {
                'product_id': sample_products[0].productID,
                'quantity': 2,
                'unit_price': float(sample_products[0].price),
                'total_price': float(sample_products[0].price) * 2
            }
        ],
        'total_amount': float(sample_products[0].price) * 2,
        'priority': 0
    }

@pytest.fixture
def sample_partner_data():
    """Create sample partner data for testing"""
    return {
        'csv_data': 'name,price,stock\nProduct A,10.99,100\nProduct B,25.50,50',
        'json_data': '{"products": [{"name": "Product A", "price": 10.99, "stock": 100}]}',
        'xml_data': '<products><product><name>Product A</name><price>10.99</price><stock>100</stock></product></products>'
    }
