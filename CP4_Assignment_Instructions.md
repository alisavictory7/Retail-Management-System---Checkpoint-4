**CS-UH 3260: Software Architecture**

**Checkpoint 4 — Final Lightweight Features & Documentation**

**Due: Check course schedule ( 5 - 12 - 2025 )**

1. Overview

This final checkpoint is a lightweight wrap-up sprint. You will implement three small
features, update documentation, clean the repository, and produce a short demo video. The
focus is on architectural completeness rather than system complexity.

2. New Lightweight Features (Implement ALL)

2.1 Order History Filtering & Search

Extend the existing Order History (or Returns History) screen to support:

- Filtering by order status (Completed, Pending, Returned, Refunded).
- A simple date-range filter.
- Basic keyword search by product name or order ID.

2.2 Low Stock Alerts

Enhance inventory logic to display low-stock alerts:

- Use a low-stock threshold (e.g., 5 units).
- Provide simple configuration (constant or environment variable).
- Display products below the threshold on the staff/admin dashboard.

2.3 Notifications for Return/Refund Status Changes

Connect the Returns & Refunds workflow to a simple notification mechanism:

- Display updated r **Return Merchandise Authorization** (RMA status) (Submitted,
Received, Inspected, Approved, Refunded).


- Use a lightweight UI notification panel or badges—no external SMS/email required.
3. Documentation Requirements

3.1 UML (4 + 1 Views)

Update diagrams to reflect the three new features:

- Use-Case View with added use cases.
- Logical View updated with new classes/components.
- Process View: one updated or new sequence diagram for one of the features.
- Deployment & Implementation Views updated if necessary.

3.2 ADRs

Add two new ADRs:

1. ADR documenting your design choices for the three lightweight features.
2. ADR documenting documentation or repository organization improvements.

3.3 README & Documentation

- Update README with instructions, feature summary, and video link.
- Update /docs with UML diagrams and ADRs.
- Add brief notes on observability from Checkpoint 3 and how logs/metrics support
debugging.
4. Repo Cleanup
- Remove unused code, files, and outdated configurations.
- Ensure the repository follows the layout from Checkpoint 1.
- Ensure Docker/Compose from CP3 still works.


- Ensure tests run; fix or mark failures with clear TODOs.
5. Required Demo Video ( 20 minutes max)

The video must demonstrate:

1. The system running (local or via Docker/Compose).
2. All three features in action:
- Order History filtering & search
- Low Stock Alerts
- Return/Refund notifications
3. Updated UML diagrams
4. New ADRs
5. Small reflection on design decisions
6. Grading (100 pts)
- Order History Filtering & Search: 20
- Low Stock Alerts: 20
- Return/Refund Notifications: 20
- Updated UML + ADRs + README: 20
- Repo cleanup & correctness: 10
- Video demo (clarity and completeness): 10


