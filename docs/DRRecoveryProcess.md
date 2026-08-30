# Membership Dashboard — Local Disaster Recovery Development

**Created:** 30 August 2026
**Purpose:** Provide a local development and disaster-recovery environment in which the Membership Dashboard can run against a restored local PostgreSQL copy of the production Supabase database, using the same Lambda application code as the production API.

---

## 1. Overview

The Membership Dashboard normally runs against the production API:

```text
Hugo
  │
  ▼
AWS API Gateway
  │
  ▼
AWS Lambda
  │
  ▼
Supabase PostgreSQL
```

A local disaster-recovery development environment has now been created which allows the same Hugo application to operate locally without accessing the production database.

The local path is:

```text
Hugo
  │
  ▼
Flask DR API proxy
  │
  ▼
Local Lambda code
  │
  ▼
Local PostgreSQL
membership_backup
```

The local Lambda code is executed using the project's Python virtual environment.

The Flask proxy does **not** access the database itself. Its purpose is to receive API requests from Hugo, determine which Lambda handles the route, and execute that Lambda locally.

---

## 2. Project structure

The relevant project directories are:

```text
/home/tim/membership-dashboard/
│
├── docs/
│
├── flask-dr/
│   └── proxy.py
│
├── hugo/
│
├── lambda/
│   ├── member-lookups/
│   ├── membership-api-members/
│   ├── payment-reports/
│   ├── payments-api-import/
│   └── payments-api-payments/
│
└── membership-scripts/
    ├── backup_membership_db.sh
    ├── restore_membership_local.sh
    ├── start_local_dr.sh
    └── start_hugo_remote.sh
```

The `membership-scripts` directory is part of the project repository.

---

## 3. Database separation

The production database is Supabase PostgreSQL.

The local disaster-recovery database is:

```text
membership_backup
```

on the Raspberry Pi's local PostgreSQL server.

The local application must never connect directly to the production database when running in local DR mode.

The local database connection is supplied through:

```text
/home/tim/.membership-dashboard/supabase.env
```

This file is deliberately outside the Git repository.

It contains the local database connection variable:

```text
DATABASE_LOCAL_URL
```

The environment file must not be committed to Git.

---

## 4. Restoring the local database

The local database is created by:

```text
/home/tim/membership-dashboard/membership-scripts/restore_membership_local.sh
```

The script restores the most recent available Supabase backup into:

```text
membership_backup
```

using PostgreSQL 17 `pg_restore`.

The restore uses:

```text
--no-owner
--no-acl
```

so that the restored database can be used by the local PostgreSQL roles.

---

## 5. Database permissions

The restored tables are owned by:

```text
postgres
```

The application connects using:

```text
membership_app
```

The restore process therefore grants the application role the permissions required to read the restored application tables.

This is important because `pg_restore --no-acl` deliberately does not restore the original table permissions.

The local application role requires read access to the application tables, including:

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

The restore script therefore performs the required grants after restoration.

These grants must be repeated after each fresh restore because the restored tables are recreated.

---

## 6. Flask DR API proxy

The proxy is:

```text
/home/tim/membership-dashboard/flask-dr/proxy.py
```

It listens on:

```text
http://127.0.0.1:5000
```

Its purpose is to provide a local replacement for API Gateway.

For example:

```text
GET /api/members
```

is received by Flask.

The proxy determines that the route belongs to:

```text
membership-api-members
```

and executes:

```text
lambda/membership-api-members/lambda_function.py
```

using the project's Python virtual environment.

The Lambda then connects to:

```text
membership_backup
```

using:

```text
DATABASE_LOCAL_URL
```

---

## 7. Lambda route mapping

The proxy contains a route-to-Lambda mapping.

The initial implementation enables read-only API routes.

The proxy therefore acts as a local API Gateway equivalent:

```text
HTTP request
     │
     ▼
Flask proxy
     │
     ├── route lookup
     │
     ├── identify Lambda
     │
     └── execute Lambda
              │
              ▼
       local PostgreSQL
```

The Lambda code itself is not duplicated or rewritten for local development.

The same Lambda source used for production is executed locally.

---

## 8. Read-only protection

The local DR proxy is deliberately read-only.

Actual API methods other than `GET` are blocked.

This provides an additional safety measure against accidentally modifying the restored database while developing.

Browser CORS `OPTIONS` requests are permitted because they are required for browser preflight processing.

The distinction is:

```text
OPTIONS
    allowed for CORS preflight

GET
    allowed as a read operation

POST / PATCH / DELETE
    blocked by the DR proxy
```

The read-only restriction is imposed by the Flask proxy rather than by modifying the Lambda code.

---

## 9. CORS handling

Hugo runs locally on:

```text
http://localhost:1313
```

or:

```text
http://127.0.0.1:1313
```

The Flask proxy therefore provides CORS headers for the local Hugo origins.

A browser request may first generate:

```text
OPTIONS /api/members
```

The proxy responds with:

```text
204
```

and the appropriate CORS headers.

The actual request then follows:

```text
GET /api/members
```

This was successfully tested.

Example successful request sequence:

```text
[DR] Incoming: OPTIONS /api/members
[DR] CORS preflight: /api/members
OPTIONS /api/members 204

[DR] Incoming: GET /api/members
[DR] Route: GET /api/members
[DR] Lambda: membership-api-members
[DR] Response: 200
GET /api/members 200
```

---

## 10. Hugo API configuration

Hugo pages do not need separate API URLs hard-coded into each page.

The application uses:

```text
window.API_BASE_URL
```

to determine where API calls should be sent.

The API mode determines the value.

### Local mode

```text
API_MODE=LOCAL
```

causes Hugo API calls to use:

```text
http://127.0.0.1:5000
```

### Remote mode

```text
API_MODE=REMOTE
```

causes Hugo API calls to use the production API Gateway.

This allows the same Hugo application to be tested in both environments.

---

## 11. Local DR startup

The complete local environment can be started with:

```bash
~/membership-dashboard/membership-scripts/start_local_dr.sh
```

This starts:

```text
Flask DR proxy
```

and:

```text
Hugo
```

with:

```text
API_MODE=LOCAL
```

The resulting architecture is:

```text
Browser
   │
   ▼
Hugo :1313
   │
   ▼
Flask :5000
   │
   ▼
Local Lambda
   │
   ▼
membership_backup
```

---

## 12. Remote API development

Hugo can also be run locally while using the production API.

Start it with:

```bash
~/membership-dashboard/membership-scripts/start_hugo_remote.sh
```

This sets:

```text
API_MODE=REMOTE
```

and starts Hugo without Flask.

The architecture is then:

```text
Browser
   │
   ▼
Hugo :1313
   │
   ▼
AWS API Gateway
   │
   ▼
AWS Lambda
   │
   ▼
Supabase
```

This provides a useful way to distinguish application/frontend problems from local DR problems.

---

## 13. Testing performed

The following local DR path has been successfully tested:

### Lookup API

```text
GET /api/towers
```

Result:

```text
200
```

The request was successfully routed through:

```text
Flask
  → member-lookups Lambda
  → membership_backup
```

### Members API

```text
GET /api/members
```

Result:

```text
200
```

The request was successfully routed through:

```text
Flask
  → membership-api-members Lambda
  → membership_backup
```

### Member detail API

```text
GET /api/members/{id}
```

was also tested.

An initial 404 was caused by using an incorrect member ID from an imported/restored dataset. The actual restored member IDs were subsequently identified and the route worked correctly.

---

## 14. Why this approach is used

The Flask proxy is intentionally thin.

It does not reproduce API business logic.

It does not contain database queries.

It does not replace Lambda functions.

Instead:

```text
Flask = local API Gateway/proxy
Lambda = application logic
PostgreSQL = local restored database
Hugo = application frontend
```

This means that changes to the Lambda application logic can be tested locally using the same code that is deployed to AWS.

This reduces the risk that local development behaves differently from production because of a separate implementation.

---

## 15. Production safety

The local DR environment is designed to make accidental production writes difficult.

The main safeguards are:

1. The local database is a separate PostgreSQL database.
2. Local database credentials are stored outside the repository.
3. The Flask proxy is read-only.
4. POST, PATCH and DELETE requests are blocked by the proxy.
5. Production API access is selected explicitly using `API_MODE=REMOTE`.
6. The local startup script explicitly selects `API_MODE=LOCAL`.

---

## 16. Relationship with the database backup system

The database backup system is documented separately in:

```text
docs/DatabaseBackupProcess.md
```

The two systems work together:

```text
                    Supabase
                       │
                       │ daily backup
                       ▼
              membership-backups
                       │
                       │ restore
                       ▼
              membership_backup
                       │
                       ▼
                Flask DR proxy
                       │
                       ▼
                 Local Lambda
                       │
                       ▼
                    Hugo
```

The backup system protects the database.

The local DR environment provides a way to run and test the application against a restored copy of that database.

---

# Current status

**Local disaster-recovery development environment: WORKING**

Successfully verified:

* Supabase database backup
* Local database restoration
* Restored application tables
* Local application database permissions
* Local Lambda execution
* Flask API proxy
* Lambda route selection
* CORS preflight handling
* Hugo → Flask → Lambda → PostgreSQL
* Local `GET /api/towers`
* Local `GET /api/members`
* Local member detail lookup
* Hugo local API mode
* Hugo remote API mode
* Separate local and remote startup scripts
* Read-only protection on the local DR proxy

The next stage is to systematically migrate the remaining Hugo API calls to `window.API_BASE_URL` and test the application's read APIs against the restored database.
