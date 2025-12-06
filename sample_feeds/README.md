# Sample Partner (VAR) Catalog Feeds

This folder contains sample CSV feeds for testing the Partner Catalog Ingest feature. Each file represents a different type of Value-Added Reseller (VAR) with realistic product data.

## Available Feeds

### CSV Feeds (Full Catalogs)

| File | Partner Type | Products | Categories |
|------|--------------|----------|------------|
| `electronics_partner_feed.csv` | Consumer Electronics | 15 | Audio, Accessories, Power, Peripherals, Video, Wearables, Cables, Storage |
| `apparel_partner_feed.csv` | Clothing & Fashion | 15 | Tops, Bottoms, Outerwear, Activewear, Footwear |
| `home_goods_partner_feed.csv` | Home & Kitchen | 15 | Bedding, Kitchen, Bath, Window, Lighting, Flooring, Organization, Decor |
| `office_supplies_partner_feed.csv` | Office & Business | 15 | Paper, Writing, Organization, Supplies, Furniture, Equipment, Filing, Planning |
| `sports_outdoor_partner_feed.csv` | Sports & Outdoors | 15 | Fitness, Weights, Camping, Hydration, Accessories, Recovery, Cardio, Cycling |
| `beauty_wellness_partner_feed.csv` | Beauty & Wellness | 15 | Skincare, Haircare, Supplements, Sun Care, Aromatherapy, Tools |
| `pet_supplies_partner_feed.csv` | Pet Supplies | 15 | Food, Toys, Bedding, Feeding, Litter, Accessories, Health, Travel, Grooming |
| `toys_games_partner_feed.csv` | Toys & Games | 15 | Construction, Vehicles, Educational, Plush, Games, Arts & Crafts, Puzzles |

### JSON Feeds (API Format)

| File | Partner Type | Products | Description |
|------|--------------|----------|-------------|
| `electronics_partner_feed.json` | Consumer Electronics | 5 | Full metadata with nested product array |
| `apparel_partner_feed.json` | Clothing & Fashion | 5 | Includes seasonal collection metadata |

### Minimal Feeds (Testing)

| File | Format | Products | Description |
|------|--------|----------|-------------|
| `minimal_feed.csv` | CSV | 3 | Only required fields (id, name, price, stock) |
| `minimal_feed.json` | JSON | 3 | Simplest valid JSON structure |

## CSV Schema

### Common Fields (All Feeds)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | String | Yes | Unique product SKU/identifier |
| `name` | String | Yes | Product display name |
| `description` | String | Yes | Product description |
| `price` | Decimal | Yes | Unit price in USD |
| `stock` | Integer | Yes | Available quantity |
| `category` | String | No | Product category |
| `country_of_origin` | String | No | Manufacturing country (for import duty calculations) |
| `brand` | String | No | Product brand name |

### Category-Specific Fields

- **Electronics**: `weight_kg` (shipping weight)
- **Apparel**: `size_range`, `material`
- **Home Goods**: `dimensions`, `weight_kg`
- **Office Supplies**: `unit_count`
- **Sports/Outdoor**: `weight_kg`
- **Beauty/Wellness**: `volume_ml`
- **Pet Supplies**: `pet_type`, `weight_kg`
- **Toys/Games**: `age_range`, `pieces`

## How to Use

### Via Admin UI

1. Navigate to `/admin/manage-store`
2. Select the **Partner Catalog** tab
3. Click **Add Partner** to create a new partner
4. Select a partner and click **Upload Feed**
5. Choose one of these sample CSV files
6. The system will validate, transform, and upsert the products

### Via API

```bash
# Upload feed via API (requires partner API key)
curl -X POST http://localhost:5000/api/partner/ingest \
  -H "X-API-Key: pk_1_your_api_key" \
  -H "Content-Type: text/csv" \
  --data-binary @sample_feeds/electronics_partner_feed.csv
```

### Via Python Script

```python
from src.services.partner_catalog_service import PartnerCatalogService
from src.database import SessionLocal

db = SessionLocal()
service = PartnerCatalogService(db)

# Read and ingest CSV feed
with open('sample_feeds/electronics_partner_feed.csv', 'r') as f:
    csv_content = f.read()
    
success, result = service.ingest_csv_file(
    partner_id=1,
    csv_content=csv_content
)
print(f"Ingested {result['processed_count']} products")
```

## Testing Scenarios

### 1. Basic Ingest Test
Upload `electronics_partner_feed.csv` to verify basic CSV parsing and product creation.

### 2. Multi-Category Test
Upload `home_goods_partner_feed.csv` to test products spanning multiple categories.

### 3. Import Duty Calculation
Upload feeds with `country_of_origin` to test duty calculations:
- China, Taiwan, Vietnam → Standard import duties
- USA, Germany, France → Varies by product type
- Mongolia (cashmere), Turkey (textiles) → Specialty rates

### 4. Large Stock Variations
`office_supplies_partner_feed.csv` has stock ranging from 55 to 2100 units, useful for:
- Low stock alert testing
- Inventory management validation

### 5. Price Range Testing
`apparel_partner_feed.csv` ranges from $24.99 to $159.99, good for:
- Cart calculations
- Discount application testing

## Data Characteristics

| Metric | Value |
|--------|-------|
| Total Products (CSV) | 120 |
| Total Products (JSON) | 16 |
| Total Feeds | 12 |
| Price Range | $7.99 - $249.99 |
| Stock Range | 25 - 2,100 units |
| Countries Represented | 20+ |
| Brands Represented | 50+ |

## JSON Feed Format

JSON feeds support richer metadata and are ideal for API integrations:

```json
{
  "partner_id": "PARTNER-ID",
  "feed_version": "2.0",
  "generated_at": "2025-01-15T10:30:00Z",
  "products": [
    {
      "id": "SKU-001",
      "name": "Product Name",
      "description": "Product description",
      "price": 29.99,
      "stock": 100,
      "category": "Category",
      "country_of_origin": "Country",
      "brand": "Brand Name"
    }
  ],
  "metadata": {
    "total_products": 1,
    "currency": "USD",
    "update_frequency": "daily"
  }
}
```

The `products` array is required; all other fields are optional metadata.

## Validation Rules Applied

The Partner Catalog Ingest feature validates:

1. **Required Fields**: `id`, `name`, `price`, `stock` must be present
2. **Price Format**: Must be positive decimal
3. **Stock Format**: Must be non-negative integer
4. **SQL Injection Prevention**: Special characters in text fields are sanitized
5. **XSS Prevention**: HTML/script tags are stripped from descriptions
6. **Duplicate Handling**: Existing SKUs are updated (upsert behavior)

