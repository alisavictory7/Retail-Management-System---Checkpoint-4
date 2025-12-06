# Retail Management System - Checkpoint 4 Demo Video Script
## 15-Minute Comprehensive Walkthrough

**Total Duration:** 15 minutes  
**Target Audience:** Software Architecture course instructors and evaluators  
**Goal:** Demonstrate all CP4 features, architectural decisions, and system capabilities

---

## [0:00 - 0:30] Introduction & System Overview

**[Screen: Terminal showing Docker Compose startup]**

"Welcome to the Retail Management System Checkpoint 4 demonstration. I'm [Your Name], and today I'll walk you through our three new lightweight features, updated documentation, and architectural decisions.

This is a full-stack retail management system built with Flask and PostgreSQL, containerized with Docker Compose. The system handles complete retail operations including user management, product catalog, shopping cart, payments, order tracking, returns and refunds, and administrative dashboards.

Checkpoint 4 adds three lightweight features that demonstrate architectural patterns: Order History Filtering & Search, Low Stock Alerts, and Return/Refund Notifications. All three use established architectural patterns documented in our ADRs.

Let me start by showing you the system running."

**[Action: Show Docker Compose startup]**

"As you can see, we're using Docker Compose to run both the web application and PostgreSQL database. The system automatically initializes the database schema, seeds sample data, and starts the Flask application with Gunicorn. This ensures a consistent, reproducible environment."

---

## [0:30 - 1:30] System Running - Docker Compose Setup

**[Screen: Terminal with docker compose command]**

"Let me show you the Docker Compose configuration. We have two services: a web container running Flask with Gunicorn, and a database container running PostgreSQL 15. The web container automatically waits for the database to be ready before starting, ensuring proper initialization order."

**[Action: Navigate to deploy/dockercompose.yml or show docker ps]**

"The system is now running on http://localhost:5000. Let me log in as the super admin to demonstrate the features."

**[Action: Open browser, navigate to http://localhost:5000, log in as super_admin / super_admin_92587]**

"Great! The system is running. Now let's explore the three CP4 features, starting with Order History Filtering & Search."

---

## [1:30 - 4:00] Feature 2.1: Order History Filtering & Search

**[Screen: Browser showing /order-history page]**

"Feature 2.1 implements Order History Filtering & Search. This feature allows users to filter their order history by status, date range, and search by keyword across product names and order IDs."

**[Action: Navigate to /order-history]**

"Here's the order history page. Notice the filter controls at the top: status dropdown, date range pickers, and a keyword search field."

**[Action: Demonstrate filtering]**

"Let me filter by 'Completed' status. [Click filter] As you can see, only completed orders are displayed. Now let me add a date range filter. [Select dates] And finally, let me search for a specific product. [Enter keyword]"

"The filtering happens client-side for immediate feedback, but also supports server-side pagination for large datasets."

**[Screen: Switch to code editor showing src/services/history_service.py]**

"Now let me show you the implementation. This feature uses the **Layers Pattern**, a modifiability tactic that separates business logic from presentation."

**[Action: Open src/services/history_service.py, highlight HistoryService class]**

"Here's the `HistoryService` class. Notice how it encapsulates all the filtering logic. The `get_order_history` method accepts filter parameters and constructs optimized database queries."

**[Action: Scroll to get_order_history method]**

"This method applies three types of filters: status filtering, date range filtering, and keyword search. The keyword search uses SQL LIKE queries across product names and order IDs."

**[Action: Highlight _apply_status_filter, _apply_date_filter, _apply_keyword_filter methods]**

"These private methods handle the complex logic for each filter type. For example, 'returned' and 'refunded' are derived statuses that require joining with ReturnRequest and Refund tables."

**[Screen: Show src/main.py route]**

"Now let's look at how the controller uses this service. [Open src/main.py, find /order-history route]"

"The controller is thin - it just parses request parameters and delegates to HistoryService. This is the Layers Pattern in action: the controller doesn't know about database schemas or query optimization."

**[Screen: Show ADR documentation]**

"This design decision is documented in ADR_CP4.md. We chose the Layers Pattern because it decouples the UI from database details, making it easy to change query logic or add new data sources without touching the controller."

---

## [4:00 - 6:30] Feature 2.2: Low Stock Alerts

**[Screen: Browser showing /admin/manage-store with Stock Alerts tab]**

"Feature 2.2 implements Low Stock Alerts. This feature monitors inventory levels and alerts administrators when products fall below a configurable threshold."

**[Action: Navigate to /admin/manage-store, click Stock Alerts tab]**

"Here's the Stock Alerts tab. You can see products with low stock displayed with their current stock levels and severity indicators. The threshold is configurable via the LOW_STOCK_THRESHOLD environment variable, defaulting to 5 units."

**[Action: Show a low stock product]**

"This product has only 3 units in stock, which is below the threshold. Notice the severity badge - it's marked as 'Warning' because it's above zero but below the threshold."

**[Screen: Switch to code editor showing src/services/low_stock_alert_service.py]**

"Now let me show you the implementation. This feature uses the **Publish-Subscribe Pattern**, an integrability tactic that decouples the inventory service from alert consumers."

**[Action: Open src/services/low_stock_alert_service.py]**

"Here's the `LowStockAlertService`. It subscribes to inventory update events. When stock changes, the inventory service publishes an event, and this service checks if the stock is below threshold."

**[Action: Scroll to notify_admins_of_low_stock method]**

"This method scans all products and identifies those below threshold. It then publishes notifications to all admin users via the notification service."

**[Action: Show publish_inventory_update_event function]**

"Here's the publisher side. When inventory is updated - for example, after a sale - this function publishes an 'inventory_updated' event. The LowStockAlertService subscribes to these events."

**[Screen: Show notification bell in navbar]**

"Admins receive these alerts through the notification bell in the navbar. [Click bell] As you can see, there's a notification about low stock products."

**[Screen: Show ADR documentation]**

"This Pub-Sub pattern is documented in ADR_CP4.md. The key benefit is loose coupling - we can add new alert consumers, like email notifications or automated reordering, without modifying the inventory service."

---

## [6:30 - 9:00] Feature 2.3: Return/Refund Notifications

**[Screen: Browser showing customer view with notification bell]**

"Feature 2.3 implements Return/Refund Notifications. This feature sends in-app notifications to customers when their RMA status changes - for example, when a return is authorized, inspected, or refunded."

**[Action: Show notification bell with badge count]**

"Here's the notification bell in the customer navbar. The badge shows the number of unread notifications."

**[Action: Click bell to show notification panel]**

"When clicked, it displays a panel with all notifications. Let me show you how these are created."

**[Screen: Switch to admin view, navigate to /admin/returns]**

"Let me switch to the admin view to demonstrate how notifications are triggered. [Navigate to /admin/returns]"

**[Action: Authorize a return request]**

"When an admin authorizes a return request, the system automatically creates a notification for the customer. [Click Authorize]"

**[Screen: Switch back to customer view, refresh page]**

"Now let's see the customer's perspective. [Refresh customer view] The notification badge has updated, and when we click the bell, we see a new notification: 'RMA Authorized - Your return #RMA-20241205-00001 has been authorized.'"

**[Action: Click notification to show modal]**

"When the customer clicks the notification, they see a modal with the full message and an action button to view the return details."

**[Screen: Switch to code editor showing src/services/returns_service.py]**

"Now let me show you the implementation. This also uses the **Publish-Subscribe Pattern**."

**[Action: Open src/services/returns_service.py, find authorize_return method]**

"Here's the `authorize_return` method in ReturnsService. After updating the status, it publishes an RMA status change event."

**[Action: Show publish_rma_status_change call]**

"This call publishes the event. The NotificationService subscribes to these events and creates notifications for the customer."

**[Action: Open src/services/notification_service.py]**

"Here's the NotificationService. It maintains an in-memory store of notifications per user. When it receives an RMA status change event, it creates a notification with a user-friendly message."

**[Action: Show create_notification method]**

"The notification includes the RMA number, status change, and a link to view the return details."

**[Screen: Show sequence diagram]**

"This flow is documented in a sequence diagram. [Open docs/UML/sequence-diagram-rma-notifications.puml] The diagram shows how the ReturnsService publishes events, the NotificationService subscribes and creates notifications, and the UI displays them to the customer."

---

## [9:00 - 11:00] Updated UML Diagrams

**[Screen: Show docs/UML/use-case-diagram.puml]**

"Now let's review the updated UML diagrams. First, the Use-Case Diagram."

**[Action: Open use-case-diagram.puml or rendered image]**

"This diagram shows all use cases, including the three new CP4 features. You can see 'View Order History', 'Filter by Status/Date', and 'Search Orders by Keyword' in the Order History section. 'View Low Stock Alerts' appears in the Admin section, and 'Receive RMA Status Notification' is in the Notifications section."

**[Screen: Show class diagram]**

"Next, the Class Diagram. [Open class-diagram.puml]"

"This shows the system's class structure. Notice the CP4 Feature Services package, which includes HistoryService, LowStockAlertService, and NotificationService. Each service has its methods and relationships documented."

**[Action: Highlight CP4 services]**

"HistoryService queries Sale and ReturnRequest. LowStockAlertService monitors Product stock levels. NotificationService manages Notification objects and receives events from ReturnsService."

**[Screen: Show sequence diagram for RMA notifications]**

"We also have a Process View sequence diagram for RMA notifications. [Open sequence-diagram-rma-notifications.puml]"

"This shows the interaction flow: Admin authorizes return → ReturnsService publishes event → NotificationService creates notification → Customer views notification. This demonstrates the Pub-Sub pattern in action."

**[Screen: Show deployment diagram]**

"Finally, the Deployment Diagram. [Open deployment-diagram.puml]"

"This shows the Docker Compose architecture. The web container includes all CP4 feature services, and the database container persists all data. The diagram shows how services communicate and where each feature is deployed."

---

## [11:00 - 13:00] New ADRs

**[Screen: Show docs/ADR/ADR_CP4.md]**

"Now let's review the Architectural Decision Records. ADR_CP4.md documents all design decisions for the three CP4 features."

**[Action: Open ADR_CP4.md]**

"ADR 1 documents design choices for the three lightweight features."

**[Action: Scroll to Feature 2.1 section]**

"For Order History, we documented three decisions: Database Indexing for performance, Data Caching for read efficiency, and Layered Service Abstraction for modifiability. Each decision includes context, the chosen approach, consequences, and alternatives considered."

**[Action: Scroll to Feature 2.2 section]**

"For Low Stock Alerts, we documented the Publish-Subscribe Pattern decision. This decouples inventory updates from alert consumers, allowing us to add new notification channels without modifying core inventory logic."

**[Action: Scroll to Feature 2.3 section]**

"For RMA Notifications, we also used Pub-Sub. This allows the ReturnsService to publish status changes without knowing how notifications are delivered - whether in-app, email, or SMS."

**[Action: Scroll to ADR 2 section]**

"ADR 2 documents repository organization improvements. We organized services into domain, infrastructure, and integration categories. We standardized ADR formats, enhanced observability integration, and made features configuration-driven."

**[Action: Highlight configuration-driven section]**

"For example, LOW_STOCK_THRESHOLD and ORDER_HISTORY_PAGE_SIZE are configurable via environment variables, allowing runtime tuning without code changes."

---

## [13:00 - 14:30] Reflection on Design Decisions

**[Screen: Show architecture overview]**

"Let me reflect on the key architectural decisions we made."

"First, **why Layers Pattern for Order History?** We chose this because order history filtering involves complex queries across multiple tables. By encapsulating this logic in HistoryService, we can optimize queries, add caching, or change data sources without touching the UI. This improves modifiability - a key quality attribute."

"Second, **why Publish-Subscribe for both Low Stock Alerts and RMA Notifications?** Pub-Sub provides extreme loose coupling. The publisher - whether InventoryService or ReturnsService - doesn't know who's listening. This means we can add new consumers - like email notifications, SMS alerts, or automated reordering - without modifying the core services. This improves integrability."

"Third, **why in-memory notifications instead of database storage?** For a lightweight feature, in-memory storage is simpler and faster. Notifications are ephemeral - users read them and move on. If we needed persistence or cross-server notifications, we'd use a database or message queue, but for CP4's scope, in-memory is appropriate."

"Fourth, **why configuration-driven thresholds?** Making LOW_STOCK_THRESHOLD configurable allows different environments to have different thresholds. In development, we might use 10 units for easier testing. In production, we might use 5. This flexibility improves modifiability without code changes."

"Finally, **why Docker Compose?** Containerization ensures consistent environments across development, testing, and deployment. It also makes it easy to demonstrate the system - just run `docker compose up` and everything works. This improves deployability and testability."

---

## [14:30 - 15:00] Conclusion & Next Steps

**[Screen: Show README.md]**

"To wrap up, let me show you the updated README. [Open README.md]"

"The README documents all three CP4 features, their routes, and how to use them. It also includes instructions for running the system with Docker Compose, testing, and accessing the admin dashboard."

**[Action: Scroll to CP4 Features section]**

"Here's the feature summary table, showing each feature, its description, the pattern used, and the route or component."

**[Action: Scroll to Quality Scenario Monitoring section]**

"We also have Interactive Quality Scenario Monitoring, which allows admins to test A.1 Availability and P.1 Performance scenarios in real-time with configurable parameters."

**[Screen: Return to browser, show dashboard]**

"Let me show you the unified admin dashboard. [Navigate to /admin/dashboard]"

"This dashboard provides quick access to all admin functions through portal cards. It displays business metrics, quality scenario status, and low stock alerts."

"Thank you for watching. The system is fully functional, all three CP4 features are implemented and tested, documentation is updated, and the repository is clean and organized. All code follows the architectural patterns documented in our ADRs."

**[End Screen: Show repository structure or README]**

"For more information, please refer to the README, ADRs, and UML diagrams in the repository. Thank you!"

---

## Key Talking Points Summary

1. **System Running:** Docker Compose setup with web and database containers
2. **Feature 2.1:** Order History with Layers Pattern, HistoryService implementation
3. **Feature 2.2:** Low Stock Alerts with Pub-Sub, LowStockAlertService implementation
4. **Feature 2.3:** RMA Notifications with Pub-Sub, NotificationService implementation
5. **UML Diagrams:** Use-Case, Class, Sequence, and Deployment diagrams updated
6. **ADRs:** Design decisions documented with context, consequences, and alternatives
7. **Reflection:** Architectural rationale for patterns and trade-offs

## Technical Terms to Explain

- **Layers Pattern:** Separates concerns into distinct layers (UI, business logic, data access) for easier modification
- **Publish-Subscribe Pattern:** Decouples event producers from consumers - publishers broadcast events, subscribers listen
- **Docker Compose:** Tool for running multi-container applications with a single command
- **ORM (Object-Relational Mapping):** Technique for accessing databases using object-oriented code instead of SQL
- **Circuit Breaker:** Pattern that prevents cascading failures by stopping requests to failing services
- **Throttling:** Rate limiting to prevent system overload

