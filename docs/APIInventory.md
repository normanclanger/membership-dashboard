# Membership Dashboard — API Inventory and Lambda Mapping

**Created:** 31 August 2026
**Purpose:** Document the Membership Dashboard API surface, the Lambda function responsible for each API route, the access type of each endpoint, and its relationship to the Hugo application and database.

---

# 1. Overview

The Membership Dashboard uses a serverless API architecture.

The browser communicates with the API through HTTP endpoints. In production, API Gateway invokes AWS Lambda functions, which communicate with the Supabase PostgreSQL database.

For local disaster-recovery testing, the same Lambda Python code can be executed locally by the Flask DR proxy against the restored `membership_backup` database.

The overall production architecture is:

```text
Hugo
  │
  │ HTTPS
  ▼
AWS API Gateway
  │
  │ Route
  ▼
AWS Lambda
  │
  │ SQL
  ▼
Supabase PostgreSQL
```

The local DR architecture is:

```text
Hugo
  │
  │ HTTP
  ▼
Flask DR proxy
  │
  │ Route → Lambda mapping
  ▼
Local Lambda Python code
  │
  │ SQL
  ▼
membership_backup
```

The API inventory is therefore important to both the production application and the local DR environment.

---

# 2. Complete API inventory

The following table is the current authoritative API inventory for the Membership Dashboard.

It records:

* API number;
* HTTP method;
* route;
* Lambda function;
* access type;
* Hugo dependency.

The **Hugo dependency** column is particularly useful when making changes to the front end, while the Lambda column is important for both production deployment and the local DR proxy.

|  # | Method | Route                                        | Lambda                   | Access | Hugo dependency                                         |
| -: | ------ | -------------------------------------------- | ------------------------ | ------ | ------------------------------------------------------- |
|  1 | GET    | `/api/payment-imports`                       | `payments-api-import`    | READ   | `payment-imports.js` / import UI                        |
|  2 | POST   | `/api/payment-imports`                       | `payments-api-import`    | WRITE  | `payment-imports.js`, `payment-import.js`               |
|  3 | GET    | `/api/payment-imports/{import_id}`           | `payments-api-import`    | READ   | `payment-imports.js`, `payment-import.js`               |
|  4 | POST   | `/api/payment-imports/{import_id}/complete`  | `payments-api-import`    | WRITE  | `payment-import.js`                                     |
|  5 | GET    | `/api/payment-imports/{import_id}/summary`   | `payments-api-import`    | READ   | `payment-import-summary.js`                             |
|  6 | GET    | `/api/payment-imports/items`                 | `payments-api-import`    | READ   | `payment-import-test/_single.html` / import UI          |
|  7 | POST   | `/api/payment-imports/{import_id}/lines`     | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
|  8 | PATCH  | `/api/payment-import-lines/{line_id}`        | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
|  9 | POST   | `/api/payment-import-lines/{line_id}/commit` | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
| 10 | POST   | `/api/payment-import-lines/{line_id}/items`  | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
| 11 | PATCH  | `/api/payment-import-items/{item_id}`        | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
| 12 | DELETE | `/api/payment-import-items/{item_id}`        | `payments-api-import`    | WRITE  | `payment-import-test/_single.html`, `payment-import.js` |
| 13 | GET    | `/api/reports/payments/list`                 | `payment-reports`        | READ   | `reports-payments.js`                                   |
| 14 | GET    | `/api/reports/payments/summary`              | `payment-reports`        | READ   | `reports-dashboard.js`                                  |
| 15 | POST   | `/api/members`                               | `membership-api-members` | WRITE  | `create-member.js`                                      |
| 16 | GET    | `/api/members`                               | `membership-api-members` | READ   | `members/single.html`                                   |
| 17 | GET    | `/api/members/{id}`                          | `membership-api-members` | READ   | `member/single.html`                                    |
| 18 | PATCH  | `/api/members/{id}`                          | `membership-api-members` | WRITE  | `patch-member.js` / member UI                           |
| 19 | GET    | `/api/members/{id}/payment-history`          | `membership-api-members` | READ   | `payment-history-test/single.html`, payment-import UI   |
| 20 | GET    | `/api/payments`                              | `payments-api-payments`  | READ   | Not yet established                                     |
| 21 | POST   | `/api/payments`                              | `payments-api-payments`  | WRITE  | Not yet established                                     |
| 22 | GET    | `/api/membership-classes`                    | `member-lookups`         | READ   | Likely member forms                                     |
| 23 | GET    | `/api/membership-statuses`                   | `member-lookups`         | READ   | Likely member forms                                     |
| 24 | GET    | `/api/full-member-types`                     | `member-lookups`         | READ   | Likely member forms                                     |
| 25 | GET    | `/api/towers`                                | `member-lookups`         | READ   | Member list / member forms                              |

This gives a total of:

```text
25 API endpoints
```

distributed across the application's principal Lambda functions.

---

# 3. Lambda functions

The production AWS environment currently contains approximately 25 Lambda functions.

Not every Lambda necessarily corresponds to a public API route. Some functions may exist for supporting functionality, testing or other AWS integration purposes.

The important distinction is:

```text
AWS Lambda function
        ≠
API endpoint
```

A single Lambda can handle multiple API routes.

The current API inventory demonstrates this particularly clearly for the payment-import functionality, where twelve API endpoints are handled by:

```text
payments-api-import
```

Similarly, the member Lambda handles five API endpoints:

```text
membership-api-members
```

and the lookup Lambda handles four:

```text
member-lookups
```

---

# 4. Payment import APIs

Payment importing is the largest group of API endpoints currently exposed by the application.

All twelve payment-import endpoints are handled by:

```text
payments-api-import
```

The endpoints cover the complete import workflow:

```text
Create import
     │
     ▼
Get import
     │
     ▼
Add import lines
     │
     ▼
Modify lines
     │
     ▼
Create/update import items
     │
     ▼
Commit lines
     │
     ▼
Complete import
     │
     ▼
View summary
```

The API routes are:

```text
GET    /api/payment-imports
POST   /api/payment-imports
GET    /api/payment-imports/{import_id}
POST   /api/payment-imports/{import_id}/complete
GET    /api/payment-imports/{import_id}/summary
GET    /api/payment-imports/items
POST   /api/payment-imports/{import_id}/lines
PATCH  /api/payment-import-lines/{line_id}
POST   /api/payment-import-lines/{line_id}/commit
POST   /api/payment-import-lines/{line_id}/items
PATCH  /api/payment-import-items/{item_id}
DELETE /api/payment-import-items/{item_id}
```

This grouping is important when maintaining the DR proxy because a new payment-import route normally belongs to the same Lambda.

---

# 5. Payment reporting APIs

Payment reporting is handled by:

```text
payment-reports
```

There are two reporting endpoints:

```text
GET /api/reports/payments/list
GET /api/reports/payments/summary
```

The detailed list is used by:

```text
reports-payments.js
```

while the summary is used by:

```text
reports-dashboard.js
```

The list endpoint accepts the calendar year as a query parameter, for example:

```text
GET /api/reports/payments/list?calendar_year=2026
```

---

# 6. Member APIs

Member maintenance is handled by:

```text
membership-api-members
```

There are five member-related API endpoints.

```text
POST  /api/members
GET   /api/members
GET   /api/members/{id}
PATCH /api/members/{id}
GET   /api/members/{id}/payment-history
```

The Lambda therefore handles both member maintenance and member payment-history retrieval.

The distinction between:

```text
membership number
```

and:

```text
database member ID
```

is important.

The `{id}` routes use the database member ID, not the membership number.

This became particularly relevant during DR testing when the restored database contained member IDs beginning at a different value from an earlier test assumption.

---

# 7. Payment APIs

Individual payment records are handled separately from payment imports.

The Lambda is:

```text
payments-api-payments
```

The currently identified endpoints are:

```text
GET  /api/payments
POST /api/payments
```

The Hugo dependency for these endpoints had not yet been established at the time of this inventory.

They are therefore recorded as:

```text
Not yet established
```

rather than making an assumption about which Hugo page currently uses them.

---

# 8. Member lookup APIs

Lookup/reference data is provided by:

```text
member-lookups
```

The four endpoints are:

```text
GET /api/membership-classes
GET /api/membership-statuses
GET /api/full-member-types
GET /api/towers
```

These provide reference data used by member-related forms and member displays.

The tower endpoint is particularly important because the member schema stores the tower relationship rather than duplicating the district on every member.

The tower data can therefore be used together with the districts table.

---

# 9. API route vs Lambda responsibility

The API architecture deliberately groups related operations into Lambda functions rather than requiring a separate Lambda for every endpoint.

For example:

```text
payments-api-import
    │
    ├── GET    /api/payment-imports
    ├── POST   /api/payment-imports
    ├── GET    /api/payment-imports/{import_id}
    ├── POST   /api/payment-imports/{import_id}/complete
    ├── GET    /api/payment-imports/{import_id}/summary
    ├── GET    /api/payment-imports/items
    ├── POST   /api/payment-imports/{import_id}/lines
    ├── PATCH  /api/payment-import-lines/{line_id}
    ├── POST   /api/payment-import-lines/{line_id}/commit
    ├── POST   /api/payment-import-lines/{line_id}/items
    ├── PATCH  /api/payment-import-items/{item_id}
    └── DELETE /api/payment-import-items/{item_id}
```

The member Lambda:

```text
membership-api-members
    │
    ├── POST   /api/members
    ├── GET    /api/members
    ├── GET    /api/members/{id}
    ├── PATCH  /api/members/{id}
    └── GET    /api/members/{id}/payment-history
```

The lookup Lambda:

```text
member-lookups
    │
    ├── GET /api/membership-classes
    ├── GET /api/membership-statuses
    ├── GET /api/full-member-types
    └── GET /api/towers
```

The payment Lambda:

```text
payments-api-payments
    │
    ├── GET  /api/payments
    └── POST /api/payments
```

The reporting Lambda:

```text
payment-reports
    │
    ├── GET /api/reports/payments/list
    └── GET /api/reports/payments/summary
```

This grouping keeps related database operations together.

---

# 10. API access types

The inventory identifies every endpoint as either:

```text
READ
```

or:

```text
WRITE
```

READ operations retrieve information without changing application data.

Examples include:

```text
GET /api/members
GET /api/towers
GET /api/payment-imports
GET /api/reports/payments/list
```

WRITE operations can modify the database.

Examples include:

```text
POST /api/members
PATCH /api/members/{id}
POST /api/payment-imports
PATCH /api/payment-import-lines/{line_id}
DELETE /api/payment-import-items/{item_id}
```

This distinction is particularly important for the DR environment, whose Flask proxy is deliberately read-only.

---

# 11. API inventory and the DR proxy

The API inventory is directly used by the local DR proxy.

The proxy receives an HTTP request such as:

```text
GET /api/towers
```

and identifies the Lambda responsible for that route:

```text
member-lookups
```

It then executes the corresponding Lambda Python code locally.

The same process applies to member, payment, import and reporting routes.

The API table therefore serves two purposes:

1. documenting the production API;
2. providing the route-to-Lambda information required by the local DR environment.

---

# 12. DR read-only considerations

The complete API inventory contains both READ and WRITE endpoints.

The DR proxy does not expose the complete set for modification.

The local DR environment is deliberately read-only so that testing cannot accidentally alter the restored disaster-recovery database.

This means that, although the API inventory contains routes such as:

```text
POST /api/payment-imports
PATCH /api/payment-import-lines/{line_id}
DELETE /api/payment-import-items/{item_id}
POST /api/members
PATCH /api/members/{id}
```

these should not automatically be added to the DR proxy's permitted operations.

If write functionality is ever required for DR testing, it should be explicitly considered and documented rather than enabled simply because the production endpoint exists.

---

# 13. Local vs production API routing

The API route itself does not change between environments.

For example:

```text
GET /api/payment-imports
```

is the same logical API call in both environments.

Only the destination changes.

LOCAL:

```text
Browser
  ↓
http://127.0.0.1:5000/api/payment-imports
  ↓
Flask DR proxy
  ↓
payments-api-import
  ↓
membership_backup
```

REMOTE:

```text
Browser
  ↓
https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api/payment-imports
  ↓
AWS API Gateway
  ↓
payments-api-import
  ↓
Supabase
```

This is why using a configurable `window.API_BASE_URL` in the Hugo application is preferable to embedding production URLs throughout the JavaScript.

---

# 14. Hugo dependencies

The Hugo dependency column records which active or known Hugo components use each API.

This provides a useful reverse mapping:

```text
API
 ↓
Lambda
 ↓
Hugo page/script
```

For example:

```text
/api/reports/payments/list
        ↓
payment-reports
        ↓
reports-payments.js
```

and:

```text
/api/payment-imports/{import_id}/summary
        ↓
payments-api-import
        ↓
payment-import-summary.js
```

This is useful when changing an API because it identifies the front-end code that may need to be tested.

Where the dependency had not yet been established, the inventory deliberately says:

```text
Not yet established
```

rather than making an assumption.

---

# 15. Authentication and authorization

API access is authenticated through the application's Cognito authentication mechanism.

The application uses Cognito groups to determine access.

Relevant groups include:

```text
MembershipViewer
PaymentAdmin
```

The API Lambda functions are responsible for enforcing their relevant permissions.

The DR proxy does not replace the application's Lambda authorization logic. Its primary role is to provide a local execution path for testing the API.

The DR proxy itself is deliberately read-only.

---

# 16. Database relationship

The API layer sits between the browser and the PostgreSQL database.

The production database is Supabase PostgreSQL.

The principal application tables include:

```text
districts
full_member_types
members
membership_classes
membership_statuses
payment_import_items
payment_import_lines
payment_imports
payments
towers
```

The API Lambda functions use these tables to provide the application's member, payment, lookup, import and reporting functionality.

The local DR database contains the same application schema following restoration.

---

# 17. API route discovery

The API inventory was established by examining the actual Lambda source and AWS configuration rather than assuming that an endpoint existed because a page or feature appeared to require one.

This was particularly important for the payment-import APIs, where the import workflow consists of multiple related endpoints rather than one single API.

The inventory also distinguishes:

```text
payment imports
payment import lines
payment import items
payments
payment reporting
member payment history
```

These are separate concepts and should not be treated as interchangeable API resources.

---

# 18. API testing

API endpoints can be tested independently of Hugo.

For local DR testing, requests can be sent to:

```text
http://127.0.0.1:5000
```

For production testing, requests are sent through the AWS API Gateway endpoint.

Browser developer tools can be used to confirm the actual request destination.

In LOCAL mode, the Request URL should begin with:

```text
http://127.0.0.1:5000
```

In REMOTE mode, the Request URL should begin with:

```text
https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com
```

This provides a direct confirmation of which API environment the Hugo application is using.

---

# 19. DR database isolation test

The API inventory and DR environment were tested together using payment imports.

A new payment import was created in production.

The local DR database contained no payment-import records.

After the environment configuration was corrected:

```text
LOCAL
    ↓
Flask
    ↓
payments-api-import
    ↓
membership_backup
    ↓
no import displayed
```

while:

```text
REMOTE
    ↓
AWS API Gateway
    ↓
payments-api-import
    ↓
Supabase
    ↓
new import displayed
```

This confirmed that the API route mapping, local Lambda execution and database separation were all working together correctly.

---

# 20. Adding or changing an API

When adding a new API endpoint, the following should be recorded:

1. API number, if maintaining the numbered inventory;
2. HTTP method;
3. API route;
4. Lambda function;
5. purpose;
6. READ/WRITE access;
7. request parameters/body;
8. response structure;
9. required permissions;
10. Hugo dependency;
11. database tables used;
12. local DR proxy mapping, if required.

The API inventory should be updated at the same time as the endpoint is added.

This avoids a situation where an endpoint exists in AWS but is missing from the documentation or DR route map.

---

# 21. Maintenance

The API inventory should be updated whenever any of the following occurs:

* a new API route is added;
* an API route is removed;
* a route changes HTTP method;
* a route is moved to another Lambda;
* a Lambda is renamed;
* a new Lambda becomes part of the application API;
* permissions for an endpoint change;
* the Hugo dependency changes;
* the local DR proxy gains support for a new route;
* an endpoint becomes obsolete.

The inventory should remain a description of the **actual current API**, rather than an historical list of routes that once existed.

---

# 22. Relationship to other documentation

This document should be read alongside:

### Database Backup System

Documents:

* Supabase database backup;
* PostgreSQL 17 dump/restore;
* 30-day retention;
* systemd backup service;
* systemd timer;
* local database restoration.

### Local Disaster Recovery Environment

Documents:

* `membership_backup`;
* Flask DR proxy;
* LOCAL/REMOTE Hugo modes;
* `HUGO_API_MODE`;
* `API_MODE`;
* local Lambda execution;
* DR database isolation.

The three documents therefore describe:

```text
Backup documentation
        │
        ▼
How the database is protected and restored

DR documentation
        │
        ▼
How the restored database is used locally

API inventory
        │
        ▼
How browser requests map to Lambda functions
```

---

# Final API architecture

```text
                         HUGO
                           │
                  window.API_BASE_URL
                           │
             ┌─────────────┴─────────────┐
             │                           │
          LOCAL                        REMOTE
             │                           │
             ▼                           ▼
       Flask DR proxy              AWS API Gateway
             │                           │
             └─────────────┬─────────────┘
                           │
                    API route mapping
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
 membership-api-       member-lookups    payments-api-
 members                                   payments
          │                │                 │
          │                │                 └── Payments
          │                │
          │                └── Towers/classes/status/types
          │
          └── Members/payment history

                           │
                           ▼

                    payments-api-import
                           │
                           └── Complete payment import workflow

                           │
                           ▼

                    payment-reports
                           │
                           ├── Payment summary
                           └── Payment list


LOCAL:    Lambda code → membership_backup
REMOTE:   Lambda code → Supabase
```

## Status

**API inventory: ESTABLISHED AND VERIFIED**

The following have been completed:

* Complete 25-endpoint API inventory established
* HTTP methods recorded
* API routes recorded
* Lambda responsibilities identified
* READ/WRITE access recorded
* Hugo dependencies recorded where established
* Payment-import workflow fully documented
* Member APIs documented
* Member lookup APIs documented
* Payment APIs documented
* Payment reporting APIs documented
* Route-to-Lambda mapping established
* DR proxy dependency on the mapping established
* LOCAL and REMOTE API destinations verified
* Production API confirmed working after the Hugo API configuration changes
* DR database isolation verified using deliberately different payment-import data

The API inventory should now be treated as the reference document when adding, modifying or troubleshooting API routes.
