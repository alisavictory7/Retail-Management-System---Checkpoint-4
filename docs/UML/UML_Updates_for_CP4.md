# UML Diagram Updates for Checkpoint 4

This document summarizes all UML diagram updates made to reflect the three new lightweight features implemented in Checkpoint 4.

## Overview of CP4 Features

| Feature | Description | Pattern Used |
|---------|-------------|--------------|
| **2.1** Order History Filtering & Search | Filter orders by status, date range, and keyword | Layered Service Abstraction |
| **2.2** Low Stock Alerts | Admin dashboard alerts for products below threshold | Publish-Subscribe |
| **2.3** RMA Status Notifications | In-app notifications for return status changes | Publish-Subscribe |

---

## 4+1 Architectural Views Updated

### 1. Use-Case View (`use-case-diagram.puml`)

**Changes:**
- Added new **"Order History (CP4)"** rectangle with:
  - `View Order History` - Main entry point for customers
  - `Filter by Status/Date` - Optional filter use case
  - `Search Orders by Keyword` - Optional search use case
  
- Added new **"Notifications (CP4)"** rectangle with:
  - `Receive RMA Status Notification` - Triggered by status changes
  - `View Notification Panel` - Customer views notifications
  - `Mark Notifications Read` - Customer marks as read

- Added `View Low Stock Alerts (CP4)` to Admin & Observability

- Added relationships:
  - `UC_Authorize`, `UC_Inspection`, `UC_Refund` all `<<trigger>>` notifications
  - `UC_Dashboard <<includes>> UC_LowStockAlerts`

---

### 2. Logical View (`class-diagram.puml`)

**New Package: "CP4 Feature Services"**

```
┌────────────────────────────────────────────────────┐
│              CP4 Feature Services                  │
├────────────────────────────────────────────────────┤
│  HistoryService                                    │
│    + get_order_history(user_id, filters)           │
│    + get_returns_history(user_id, filters)         │
│    + parse_date(date_string)                       │
│    + format_order_for_display(sale)                │
├────────────────────────────────────────────────────┤
│  LowStockAlertService                              │
│    + check_stock_level(product)                    │
│    + get_alert_summary()                           │
│    + get_low_stock_products()                      │
│    + publish_low_stock_event(product)              │
├────────────────────────────────────────────────────┤
│  NotificationService                               │
│    + create_notification(user_id, type, msg)       │
│    + get_notifications(user_id, filters)           │
│    + get_unread_count(user_id)                     │
│    + mark_as_read(user_id, notif_id)               │
│    + mark_all_as_read(user_id)                     │
├────────────────────────────────────────────────────┤
│  Notification (Data Class)                         │
│    + id: str                                       │
│    + user_id: int                                  │
│    + notification_type: str                        │
│    + title: str                                    │
│    + message: str                                  │
│    + reference_id: int                             │
│    + is_read: bool                                 │
│    + created_at: datetime                          │
└────────────────────────────────────────────────────┘
```

**New Relationships:**
- `HistoryService ..> Sale : queries`
- `HistoryService ..> ReturnRequest : queries`
- `LowStockAlertService ..> Product : monitors_stock`
- `NotificationService ..> Notification : manages`
- `User ||--o{ Notification : receives`
- `ReturnsService ..> NotificationService : publishes_status_change`
- `ObservabilityDashboard --> LowStockAlertService : displays_alerts`

---

### 3. Process View (`sequence-diagram-rma-notifications.puml`)

**New Sequence Diagram** showing the RMA notification flow:

1. **Authorization Flow:**
   - Admin authorizes RMA via `/admin/returns/<id>/authorize`
   - `ReturnsService` detects status change (PENDING → AUTHORIZED)
   - `ReturnsService` calls `NotificationService.publish_rma_status_change()`
   - `NotificationService` creates notification and stores in memory

2. **Customer Notification View:**
   - Customer navigates to any page
   - `inject_nav_context()` calls `NotificationService.get_unread_count()`
   - Badge displays unread count
   - Customer clicks bell icon → `GET /api/notifications`
   - Panel displays notification list

3. **Mark as Read Flow:**
   - Customer clicks notification
   - `POST /api/notifications/<id>/read`
   - Badge count decrements

**Key Pattern Highlighted:**
```
Pub-Sub Pattern Benefits:
- ReturnsService decoupled from notification logic
- Easy to add email/SMS channels later
- Single event triggers multiple subscribers
```

---

### 4. Deployment View (`deployment-diagram.puml`)

**New Component Added:**

```
┌──────────────────────────────────────────────────┐
│         web (Gunicorn + Flask)                   │
├──────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐  │
│  │         CP4 Feature Services               │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │ HistoryService (Order Filtering)     │  │  │
│  │  ├──────────────────────────────────────┤  │  │
│  │  │ LowStockAlertService (Pub-Sub)       │  │  │
│  │  ├──────────────────────────────────────┤  │  │
│  │  │ NotificationService (RMA Updates)    │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**New Connections:**
- `CustomerBrowser --> HistorySvc : /order-history`
- `CustomerBrowser --> NotificationSvc : /api/notifications`
- `AdminBrowser --> LowStockSvc : /api/admin/low-stock`
- `ReturnsModule --> NotificationSvc : publish status changes`
- `Dashboard --> LowStockSvc : display alerts`

---

### 5. Implementation View (`package-diagram.puml`)

**New Package Added:**

```
package "CP4 Feature Services" #E8F5E9 {
    [src/services/history_service.py] as HistorySvc
    [src/services/low_stock_alert_service.py] as LowStockSvc
    [src/services/notification_service.py] as NotificationSvc
}
```

**New Dependencies:**
- `Main --> HistorySvc : /order-history route`
- `Main --> LowStockSvc : /admin/dashboard`
- `Main --> NotificationSvc : context_processor + API`
- `HistorySvc --> Models : queries Sales, Returns`
- `LowStockSvc --> Models : monitors Products`
- `NotificationSvc ..> ReturnsSvc : Pub-Sub subscriber`
- `InventorySvc ..> LowStockSvc : publishes stock events`

---

## Rendering the Diagrams

All diagrams use PlantUML syntax and can be rendered using:

1. **PlantUML Online Server:** https://www.plantuml.com/plantuml/uml/
2. **VS Code Extension:** "PlantUML" by jebbs
3. **Command Line:**
   ```bash
   java -jar plantuml.jar docs/UML/*.puml
   ```

---

## Diagram Files Summary

| Diagram | File | View |
|---------|------|------|
| Use Case | `use-case-diagram.puml` | Use-Case View |
| Class | `class-diagram.puml` | Logical View |
| Sequence (RMA Notifications) | `sequence-diagram-rma-notifications.puml` | Process View |
| Sequence (Partner Ingest) | `sequence-diagram-partner-ingest.puml` | Process View (CP2) |
| Deployment | `deployment-diagram.puml` | Deployment View |
| Package | `package-diagram.puml` | Implementation View |
| Sequence (Success) | `sequence-diagram-success.puml` | Process View (CP3) |
| Sequence (Exceptions) | `sequence-diagram-exceptions.puml` | Process View (CP3) |

---

## CP2: Partner (VAR) Catalog Ingest Updates

The class diagram and use-case diagram have been updated to include the Partner (VAR) Catalog Ingest feature (CP2):

### Class Diagram Additions

**New Package: "Partner (VAR) Catalog Ingest"**

```
┌────────────────────────────────────────────────────┐
│       Partner (VAR) Catalog Ingest                 │
├────────────────────────────────────────────────────┤
│  Partner                                           │
│    + partnerID: int                                │
│    + name: str                                     │
│    + api_endpoint: str                             │
│    + sync_frequency: int                           │
│    + last_sync: datetime                           │
│    + status: str                                   │
├────────────────────────────────────────────────────┤
│  PartnerAPIKey                                     │
│    + keyID: int                                    │
│    + api_key: str                                  │
│    + expires_at: datetime                          │
│    + is_active: bool                               │
├────────────────────────────────────────────────────┤
│  PartnerProduct                                    │
│    + partnerProductID: int                         │
│    + external_product_id: str                      │
│    + sync_status: str                              │
│    + sync_data: json                               │
├────────────────────────────────────────────────────┤
│  PartnerCatalogService                             │
│    + create_partner()                              │
│    + authenticate_api_key()                        │
│    + validate_input()                              │
│    + ingest_csv_file()                             │
│    + ingest_json_file()                            │
│    + sync_partner_catalog()                        │
│    + start_scheduler()                             │
├────────────────────────────────────────────────────┤
│  CSVDataAdapter / JSONDataAdapter / XMLDataAdapter │
│    + adapt(data): Dict                             │
│    + can_handle(data): bool                        │
└────────────────────────────────────────────────────┘
```

### Use-Case Diagram Additions

- Added **"Partner (VAR) Catalog Ingest"** rectangle with:
  - `Upload CSV/JSON Feed`
  - `Manage Partners`
  - `Schedule Periodic Sync`
  - `View Catalog Statistics`

### Architectural Patterns Applied

| ADR | Pattern | Implementation |
|-----|---------|----------------|
| ADR 6 (S.1) | Authenticate Actors | API key validation in `authenticate_api_key()` |
| ADR 7 (S.2) | Validate Input | SQL injection prevention in `validate_input()` |
| ADR 8/9 (M.1) | Adapter Pattern | `CSVDataAdapter`, `JSONDataAdapter`, `XMLDataAdapter` |
| ADR 15/16 (I.2) | Publish-Subscribe | Event publishing via `MessageQueue` |

