# src/services/partner_catalog_service.py
"""
Partner (VAR) Catalog Ingest Service

Implements Checkpoint 2 requirements:
- Ingest partner product feeds (CSV/JSON) via adapter/gateway
- Validate, transform, and upsert items
- Schedule periodic ingestion for partners

Architectural Patterns Applied:
- ADR 6 (S.1): Authenticate Actors - API key validation
- ADR 7 (S.2): Validate Input - Sanitization/filtering
- ADR 8 (M.1): Use Intermediary/Encapsulate - Adapter pattern
- ADR 9 (M.1): Adapter Pattern - Format transformation
- ADR 15 (I.2): Use Intermediary - Message broker integration
- ADR 16 (I.2): Publish-Subscribe - Event broadcasting
"""
import json
import csv
import io
import re
import requests
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any, Callable
from sqlalchemy.orm import Session
from src.models import Partner, PartnerProduct, PartnerAPIKey, Product, AuditLog, MessageQueue
import logging
import bleach
import hashlib
import secrets

logger = logging.getLogger(__name__)

# SQL injection patterns for validation (ADR 7: Validate Input)
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
    r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
    r"(--|#|\/\*|\*\/)",
    r"(\b(SCRIPT|JAVASCRIPT)\b)",
]


class PartnerCatalogService:
    """
    Service class for managing Partner/VAR catalog synchronization.
    
    Implements the Partner (VAR) Catalog Ingest feature with:
    1. CSV/JSON feed ingestion via adapter pattern
    2. Input validation and transformation
    3. Product upsert with conflict resolution
    4. Optional periodic scheduling
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._scheduler_thread = None
        self._scheduler_running = False
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]
    
    # ==========================================
    # PARTNER MANAGEMENT
    # ==========================================
    
    def create_partner(self, name: str, api_endpoint: str = None, api_key: str = None, 
                      sync_frequency: int = 3600) -> Tuple[bool, str, Optional[Partner]]:
        """Create a new partner with optional API key generation"""
        try:
            partner = Partner(
                name=name,
                api_endpoint=api_endpoint,
                api_key=api_key,
                sync_frequency=sync_frequency,
                last_sync=None,
                status='active'
            )
            
            self.db.add(partner)
            self.db.commit()
            self.db.refresh(partner)
            
            # Generate API key for the partner (ADR 6: Authenticate Actors)
            generated_key = self._generate_api_key(partner.partnerID)
            
            logger.info(f"Created partner {partner.partnerID}: {name}")
            self._log_audit("partner_created", "Partner", partner.partnerID, 
                           {"name": name, "sync_frequency": sync_frequency})
            
            return True, "Partner created successfully", partner
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating partner: {e}")
            return False, f"Error creating partner: {str(e)}", None
    
    def _generate_api_key(self, partner_id: int) -> str:
        """Generate a secure API key for a partner (ADR 6: Authenticate Actors)"""
        try:
            # Generate a secure random key
            raw_key = secrets.token_urlsafe(32)
            api_key = f"pk_{partner_id}_{raw_key}"
            
            # Create API key record
            key_record = PartnerAPIKey(
                partnerID=partner_id,
                api_key=api_key,
                is_active=True,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365)
            )
            
            self.db.add(key_record)
            self.db.commit()
            
            logger.info(f"Generated API key for partner {partner_id}")
            return api_key
            
        except Exception as e:
            logger.error(f"Error generating API key: {e}")
            return None
    
    def get_all_partners(self) -> List[Partner]:
        """Get all partners"""
        return self.db.query(Partner).all()
    
    def update_partner(self, partner_id: int, name: str = None, 
                      sync_frequency: int = None, status: str = None) -> Tuple[bool, str]:
        """Update partner details"""
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found"
            
            if name:
                partner.name = name
            if sync_frequency is not None:
                partner.sync_frequency = sync_frequency
            if status:
                partner.status = status
            
            self.db.commit()
            logger.info(f"Updated partner {partner_id}")
            return True, "Partner updated successfully"
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating partner: {e}")
            return False, f"Error updating partner: {str(e)}"
    
    def delete_partner(self, partner_id: int) -> Tuple[bool, str]:
        """Delete a partner and associated data"""
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found"
            
            # Delete associated API keys
            self.db.query(PartnerAPIKey).filter_by(partnerID=partner_id).delete()
            
            # Delete associated partner products
            self.db.query(PartnerProduct).filter_by(partnerID=partner_id).delete()
            
            # Delete partner
            self.db.delete(partner)
            self.db.commit()
            
            logger.info(f"Deleted partner {partner_id}")
            return True, "Partner deleted successfully"
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting partner: {e}")
            return False, f"Error deleting partner: {str(e)}"
    
    def get_partner_by_id(self, partner_id: int) -> Optional[Partner]:
        """Get partner by ID"""
        return self.db.query(Partner).filter_by(partnerID=partner_id).first()
    
    def get_active_partners(self) -> List[Partner]:
        """Get all active partners"""
        return self.db.query(Partner).filter(Partner._status == 'active').all()
    
    def get_partner_api_key(self, partner_id: int) -> Optional[str]:
        """Get active API key for a partner"""
        key_record = self.db.query(PartnerAPIKey).filter_by(
            partnerID=partner_id,
            is_active=True
        ).first()
        return key_record.api_key if key_record else None
    
    # ==========================================
    # API KEY AUTHENTICATION (ADR 6: S.1)
    # ==========================================
    
    def authenticate_api_key(self, api_key: str) -> Tuple[bool, str, Optional[int]]:
        """
        Authenticate partner using API key (ADR 6: Authenticate Actors).
        Returns: (success, message, partner_id)
        """
        try:
            if not api_key:
                self._log_auth_failure(api_key, "Empty API key")
                return False, "API key required", None
            
            key_record = self.db.query(PartnerAPIKey).filter_by(
                api_key=api_key,
                is_active=True
            ).first()
            
            if not key_record:
                self._log_auth_failure(api_key, "Invalid API key")
                return False, "Invalid API key", None
            
            # Check expiration
            if key_record.expires_at:
                expires_at = key_record.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < datetime.now(timezone.utc):
                    self._log_auth_failure(api_key, "API key expired")
                    return False, "API key expired", None
            
            # Update usage statistics
            key_record.last_used = datetime.now(timezone.utc)
            key_record.usage_count += 1
            self.db.commit()
            
            logger.info(f"Authenticated partner {key_record.partnerID}")
            return True, "Authentication successful", key_record.partnerID
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False, f"Authentication error: {str(e)}", None
    
    def _log_auth_failure(self, api_key: str, reason: str):
        """Log failed authentication attempt"""
        try:
            masked_key = api_key[:8] + "..." if api_key and len(api_key) > 8 else "***"
            self._log_audit("auth_failed", "PartnerAPIKey", None, 
                           {"masked_key": masked_key, "reason": reason}, success=False)
        except Exception as e:
            logger.error(f"Failed to log auth failure: {e}")
    
    # ==========================================
    # INPUT VALIDATION (ADR 7: S.2)
    # ==========================================
    
    def validate_input(self, data: Any) -> Tuple[bool, str]:
        """
        Validate input data for security threats (ADR 7: Validate Input).
        Prevents SQL injection and XSS attacks.
        """
        try:
            if isinstance(data, str):
                return self._validate_string(data)
            elif isinstance(data, dict):
                for key, value in data.items():
                    is_valid, error = self.validate_input(value)
                    if not is_valid:
                        return False, f"Invalid value for '{key}': {error}"
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    is_valid, error = self.validate_input(item)
                    if not is_valid:
                        return False, f"Invalid item at index {i}: {error}"
            
            return True, "Input is valid"
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    def _validate_string(self, data: str) -> Tuple[bool, str]:
        """Validate string input for SQL injection and XSS"""
        # Check for SQL injection patterns
        for pattern in self._compiled_patterns:
            if pattern.search(data):
                return False, f"Potential SQL injection detected"
        
        # Check for XSS via HTML sanitization
        sanitized = bleach.clean(data, tags=[], strip=True)
        if sanitized != data and '<' in data:
            return False, "HTML content detected"
        
        return True, "Valid"
    
    def sanitize_input(self, data: str) -> str:
        """Sanitize input data by removing dangerous content"""
        sanitized = bleach.clean(data, tags=[], strip=True)
        sanitized = sanitized.replace("'", "''")
        sanitized = sanitized.replace('"', '""')
        sanitized = sanitized.replace(';', '')
        sanitized = sanitized.replace('--', '')
        return sanitized
    
    # ==========================================
    # FILE INGESTION (ADR 8, ADR 9: M.1)
    # ==========================================
    
    def ingest_csv_file(self, partner_id: int, file_content: str) -> Tuple[bool, str, int]:
        """
        Ingest products from CSV file content (ADR 9: Adapter Pattern).
        
        Expected CSV format:
        id,name,description,price,stock,country_of_origin
        """
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found", 0
            
            # Parse CSV data using adapter pattern
            products_data = self._parse_csv(file_content)
            if not products_data:
                return False, "Failed to parse CSV data", 0
            
            # Validate all products (ADR 7: Validate Input)
            validated_products, validation_errors = self._validate_products(products_data)
            if validation_errors:
                logger.warning(f"Validation errors: {validation_errors}")
            
            if not validated_products:
                return False, f"No valid products. Errors: {validation_errors}", 0
            
            # Process and upsert products
            synced_count = self._process_partner_products(partner, validated_products)
            
            # Update sync timestamp
            partner.last_sync = datetime.now(timezone.utc)
            self.db.commit()
            
            # Publish event (ADR 16: Publish-Subscribe)
            self._publish_catalog_update(partner_id, synced_count, "csv")
            
            logger.info(f"Ingested {synced_count} products from CSV for partner {partner.name}")
            return True, f"Successfully ingested {synced_count} products", synced_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ingesting CSV: {e}")
            return False, f"Error ingesting CSV: {str(e)}", 0
    
    def ingest_json_file(self, partner_id: int, file_content: str) -> Tuple[bool, str, int]:
        """
        Ingest products from JSON file content (ADR 9: Adapter Pattern).
        
        Expected JSON format:
        [{"id": "...", "name": "...", "price": ..., "stock": ..., ...}]
        or {"products": [...]}
        """
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found", 0
            
            # Parse JSON data using adapter pattern
            products_data = self._parse_json(file_content)
            if not products_data:
                return False, "Failed to parse JSON data", 0
            
            # Validate all products (ADR 7: Validate Input)
            validated_products, validation_errors = self._validate_products(products_data)
            if validation_errors:
                logger.warning(f"Validation errors: {validation_errors}")
            
            if not validated_products:
                return False, f"No valid products. Errors: {validation_errors}", 0
            
            # Process and upsert products
            synced_count = self._process_partner_products(partner, validated_products)
            
            # Update sync timestamp
            partner.last_sync = datetime.now(timezone.utc)
            self.db.commit()
            
            # Publish event (ADR 16: Publish-Subscribe)
            self._publish_catalog_update(partner_id, synced_count, "json")
            
            logger.info(f"Ingested {synced_count} products from JSON for partner {partner.name}")
            return True, f"Successfully ingested {synced_count} products", synced_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ingesting JSON: {e}")
            return False, f"Error ingesting JSON: {str(e)}", 0
    
    def _parse_csv(self, content: str) -> List[Dict[str, Any]]:
        """Parse CSV content to list of product dictionaries (Adapter Pattern)"""
        try:
            reader = csv.DictReader(io.StringIO(content))
            products = []
            for row in reader:
                product = {
                    'id': row.get('id', row.get('external_id', '')),
                    'name': row.get('name', row.get('product_name', '')),
                    'description': row.get('description', ''),
                    'price': float(row.get('price', 0)),
                    'stock': int(row.get('stock', row.get('quantity', 0))),
                    'country_of_origin': row.get('country_of_origin', row.get('origin', 'Unknown')),
                    'shipping_weight': float(row.get('shipping_weight', row.get('weight', 0))),
                }
                products.append(product)
            return products
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            return []
    
    def _parse_json(self, content: str) -> List[Dict[str, Any]]:
        """Parse JSON content to list of product dictionaries (Adapter Pattern)"""
        try:
            data = json.loads(content)
            
            # Handle different JSON structures
            if isinstance(data, list):
                products = data
            elif isinstance(data, dict) and 'products' in data:
                products = data['products']
            elif isinstance(data, dict):
                products = [data]
            else:
                return []
            
            # Normalize product fields
            normalized = []
            for p in products:
                product = {
                    'id': str(p.get('id', p.get('external_id', p.get('sku', '')))),
                    'name': p.get('name', p.get('product_name', p.get('title', ''))),
                    'description': p.get('description', p.get('desc', '')),
                    'price': float(p.get('price', p.get('unit_price', 0))),
                    'stock': int(p.get('stock', p.get('quantity', p.get('inventory', 0)))),
                    'country_of_origin': p.get('country_of_origin', p.get('origin', 'Unknown')),
                    'shipping_weight': float(p.get('shipping_weight', p.get('weight', 0))),
                }
                normalized.append(product)
            
            return normalized
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
            return []
    
    def _validate_products(self, products: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Validate product data and filter out invalid entries (ADR 7: Validate Input)"""
        validated = []
        errors = []
        
        for i, product in enumerate(products):
            # Check required fields
            if not product.get('id'):
                errors.append(f"Product {i}: Missing ID")
                continue
            
            if not product.get('name'):
                errors.append(f"Product {i}: Missing name")
                continue
            
            # Validate input for security (ADR 7)
            is_valid, error = self.validate_input(product)
            if not is_valid:
                errors.append(f"Product {product.get('id')}: {error}")
                continue
            
            # Sanitize text fields
            product['name'] = self.sanitize_input(str(product['name']))
            product['description'] = self.sanitize_input(str(product.get('description', '')))
            
            # Validate numeric fields
            try:
                product['price'] = max(0, float(product.get('price', 0)))
                product['stock'] = max(0, int(product.get('stock', 0)))
                product['shipping_weight'] = max(0, float(product.get('shipping_weight', 0)))
            except (ValueError, TypeError) as e:
                errors.append(f"Product {product.get('id')}: Invalid numeric value - {e}")
                continue
            
            validated.append(product)
        
        return validated, errors
    
    def _publish_catalog_update(self, partner_id: int, product_count: int, format_type: str):
        """Publish catalog update event (ADR 16: Publish-Subscribe)"""
        try:
            message = MessageQueue(
                topic="partner_catalog_updates",
                message_type="catalog_ingested",
                payload=json.dumps({
                    "partner_id": partner_id,
                    "product_count": product_count,
                    "format": format_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }),
                status='pending',
                scheduled_for=datetime.now(timezone.utc)
            )
            self.db.add(message)
            self.db.commit()
            logger.info(f"Published catalog update event for partner {partner_id}")
        except Exception as e:
            logger.error(f"Failed to publish catalog update: {e}")
    
    def sync_partner_catalog(self, partner_id: int) -> Tuple[bool, str, int]:
        """Synchronize catalog from a partner via API endpoint"""
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found", 0
            
            if not partner.api_endpoint:
                return False, "Partner API endpoint not configured", 0
            
            # Fetch data from partner API
            products_data = self._fetch_partner_products(partner)
            if not products_data:
                return False, "Failed to fetch products from partner", 0
            
            # Validate products (ADR 7: Validate Input)
            validated_products, _ = self._validate_products(products_data)
            if not validated_products:
                return False, "No valid products in feed", 0
            
            # Process and sync products
            synced_count = self._process_partner_products(partner, validated_products)
            
            # Update partner sync timestamp
            partner.last_sync = datetime.now(timezone.utc)
            self.db.commit()
            
            # Publish event
            self._publish_catalog_update(partner_id, synced_count, "api")
            
            logger.info(f"Synced {synced_count} products from partner {partner.name}")
            return True, f"Successfully synced {synced_count} products", synced_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error syncing partner catalog: {e}")
            return False, f"Error syncing catalog: {str(e)}", 0
    
    def _fetch_partner_products(self, partner: Partner) -> Optional[List[Dict[str, Any]]]:
        """Fetch products from partner API"""
        try:
            headers = {
                'Authorization': f'Bearer {partner.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                partner.api_endpoint,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # Normalize to list format
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'products' in data:
                    return data['products']
                return [data]
            else:
                logger.error(f"API request failed with status {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error fetching from partner API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching partner data: {e}")
            return None
    
    def _process_partner_products(self, partner: Partner, products_data: List[Dict[str, Any]]) -> int:
        """
        Process and upsert partner products (ADR 8: Use Intermediary).
        Implements transform and upsert logic for catalog items.
        """
        synced_count = 0
        
        for product_data in products_data:
            try:
                # Extract product information
                external_id = str(product_data.get('id', ''))
                name = product_data.get('name', '')
                price = product_data.get('price', 0)
                description = product_data.get('description', '')
                stock = product_data.get('stock', 0)
                
                if not external_id or not name:
                    continue
                
                # Check if partner product already exists (upsert logic)
                partner_product = self.db.query(PartnerProduct).filter(
                    PartnerProduct.partnerID == partner.partnerID,
                    PartnerProduct.external_product_id == str(external_id)
                ).first()
                
                if partner_product:
                    # Update existing product
                    self._update_existing_product(partner_product, product_data)
                else:
                    # Create new product mapping
                    self._create_new_product_mapping(partner, external_id, product_data)
                
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error processing product {product_data.get('id', 'unknown')}: {e}")
                continue
        
        return synced_count
    
    def _update_existing_product(self, partner_product: PartnerProduct, product_data: Dict[str, Any]):
        """Update existing partner product (upsert - update path)"""
        partner_product.sync_data = json.dumps(product_data)
        partner_product.sync_status = 'synced'
        partner_product.last_synced = datetime.now(timezone.utc)
        
        # Update the actual product if mapped
        if partner_product.product:
            product = partner_product.product
            product.name = product_data.get('name', product.name)
            product.price = product_data.get('price', product.price)
            product.description = product_data.get('description', product.description)
            product.stock = product_data.get('stock', product.stock)
            if 'shipping_weight' in product_data:
                product._shipping_weight = product_data.get('shipping_weight', 0)
            if 'country_of_origin' in product_data:
                product._country_of_origin = product_data.get('country_of_origin', 'Unknown')
    
    def _create_new_product_mapping(self, partner: Partner, external_id: str, product_data: Dict[str, Any]):
        """Create new product mapping (upsert - insert path)"""
        # Create new product
        product = Product(
            name=product_data.get('name', ''),
            description=product_data.get('description', ''),
            price=product_data.get('price', 0),
            stock=product_data.get('stock', 0),
        )
        # Set protected attributes
        product._shipping_weight = product_data.get('shipping_weight', 0)
        product._discount_percent = 0
        product._country_of_origin = product_data.get('country_of_origin', 'Unknown')
        product._requires_shipping = product_data.get('requires_shipping', True)
        
        self.db.add(product)
        self.db.flush()  # Get the product ID
        
        # Create partner product mapping
        partner_product = PartnerProduct(
            partnerID=partner.partnerID,
            external_product_id=str(external_id),
            productID=product.productID,
            sync_status='synced',
            last_synced=datetime.now(timezone.utc),
            sync_data=json.dumps(product_data)
        )
        
        self.db.add(partner_product)
    
    def get_partner_products(self, partner_id: int) -> List[PartnerProduct]:
        """Get all products for a partner"""
        return self.db.query(PartnerProduct).filter(
            PartnerProduct.partnerID == partner_id
        ).all()
    
    def sync_all_partners(self) -> Dict[str, Any]:
        """Sync all active partners"""
        results = {
            'total_partners': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'total_products_synced': 0,
            'errors': []
        }
        
        partners = self.get_active_partners()
        results['total_partners'] = len(partners)
        
        for partner in partners:
            try:
                success, message, count = self.sync_partner_catalog(partner.partnerID)
                if success:
                    results['successful_syncs'] += 1
                    results['total_products_synced'] += count
                else:
                    results['failed_syncs'] += 1
                    results['errors'].append(f"{partner.name}: {message}")
            except Exception as e:
                results['failed_syncs'] += 1
                results['errors'].append(f"{partner.name}: {str(e)}")
        
        return results
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status for all partners"""
        partners = self.get_active_partners()
        status = []
        
        for partner in partners:
            partner_status = {
                'partner_id': partner.partnerID,
                'name': partner.name,
                'last_sync': partner.last_sync,
                'sync_frequency': partner.sync_frequency,
                'status': partner.status,
                'product_count': len(self.get_partner_products(partner.partnerID))
            }
            status.append(partner_status)
        
        return {'partners': status}
    
    # ==========================================
    # PERIODIC SCHEDULING
    # ==========================================
    
    def start_scheduler(self, check_interval: int = 60):
        """
        Start the periodic sync scheduler.
        
        This implements the "optional scheduled periodic ingestion" requirement.
        The scheduler checks each partner's sync_frequency and triggers
        sync when the elapsed time exceeds the configured frequency.
        
        Args:
            check_interval: How often to check for partners needing sync (seconds)
        """
        if self._scheduler_running:
            logger.warning("Scheduler is already running")
            return
        
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            args=(check_interval,),
            daemon=True
        )
        self._scheduler_thread.start()
        logger.info(f"Started partner catalog scheduler (check interval: {check_interval}s)")
    
    def stop_scheduler(self):
        """Stop the periodic sync scheduler"""
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None
        logger.info("Stopped partner catalog scheduler")
    
    def _scheduler_loop(self, check_interval: int):
        """Main scheduler loop"""
        while self._scheduler_running:
            try:
                self._check_and_sync_partners()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            # Sleep in small increments to allow for quick shutdown
            for _ in range(check_interval):
                if not self._scheduler_running:
                    break
                time.sleep(1)
    
    def _check_and_sync_partners(self):
        """Check all partners and sync those that are due"""
        try:
            partners = self.get_active_partners()
            now = datetime.now(timezone.utc)
            
            for partner in partners:
                if not partner.api_endpoint:
                    continue
                
                # Calculate if sync is due
                sync_frequency = partner.sync_frequency or 3600  # Default 1 hour
                
                if partner.last_sync:
                    last_sync = partner.last_sync
                    if last_sync.tzinfo is None:
                        last_sync = last_sync.replace(tzinfo=timezone.utc)
                    
                    time_since_sync = (now - last_sync).total_seconds()
                    
                    if time_since_sync < sync_frequency:
                        continue
                
                # Sync is due
                logger.info(f"Scheduled sync for partner {partner.name}")
                try:
                    success, message, count = self.sync_partner_catalog(partner.partnerID)
                    if success:
                        logger.info(f"Scheduled sync completed: {message}")
                    else:
                        logger.warning(f"Scheduled sync failed: {message}")
                except Exception as e:
                    logger.error(f"Error during scheduled sync for {partner.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking partners for sync: {e}")
    
    def get_next_sync_time(self, partner_id: int) -> Optional[datetime]:
        """Get the next scheduled sync time for a partner"""
        partner = self.get_partner_by_id(partner_id)
        if not partner:
            return None
        
        sync_frequency = partner.sync_frequency or 3600
        
        if partner.last_sync:
            last_sync = partner.last_sync
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            return last_sync + timedelta(seconds=sync_frequency)
        
        return datetime.now(timezone.utc)
    
    def update_sync_frequency(self, partner_id: int, frequency_seconds: int) -> Tuple[bool, str]:
        """Update the sync frequency for a partner"""
        try:
            partner = self.get_partner_by_id(partner_id)
            if not partner:
                return False, "Partner not found"
            
            if frequency_seconds < 60:
                return False, "Minimum sync frequency is 60 seconds"
            
            partner.sync_frequency = frequency_seconds
            self.db.commit()
            
            logger.info(f"Updated sync frequency for partner {partner_id} to {frequency_seconds}s")
            return True, f"Sync frequency updated to {frequency_seconds} seconds"
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating sync frequency: {e}")
            return False, f"Error updating sync frequency: {str(e)}"
    
    # ==========================================
    # AUDIT LOGGING
    # ==========================================
    
    def _log_audit(self, action: str, entity_type: str, entity_id: int = None, 
                   data: Dict[str, Any] = None, success: bool = True):
        """Log audit event for partner operations"""
        try:
            audit = AuditLog(
                event_type="partner_catalog",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                new_values=json.dumps(data) if data else None,
                success=success,
                timestamp=datetime.now(timezone.utc)
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    def get_catalog_statistics(self) -> Dict[str, Any]:
        """Get overall catalog statistics"""
        partners = self.get_all_partners()
        active_partners = [p for p in partners if p.status == 'active']
        
        total_products = self.db.query(PartnerProduct).count()
        synced_products = self.db.query(PartnerProduct).filter_by(sync_status='synced').count()
        
        return {
            'total_partners': len(partners),
            'active_partners': len(active_partners),
            'total_partner_products': total_products,
            'synced_products': synced_products,
            'scheduler_running': self._scheduler_running
        }
