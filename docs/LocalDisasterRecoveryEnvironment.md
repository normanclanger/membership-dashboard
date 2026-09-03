# Membership Dashboard — Local Disaster Recovery Environment

**Created:** 31 August 2026
**Purpose:** Document the local disaster-recovery environment used to run and test the Membership Dashboard against a restored local PostgreSQL database, without connecting the application to the live Supabase database.

---

## 1. Overview

The Membership Dashboard can now be run in two modes from the Raspberry Pi:

* **LOCAL / DR mode** — Hugo uses the local Flask API proxy, which executes the Lambda Python code locally against the restored `membership_backup` PostgreSQL database.
* **REMOTE / production mode** — Hugo calls the AWS API Gateway, which invokes the production AWS Lambda functions connected to Supabase.

The two modes therefore use completely separate databases.

The architecture is:

```text
LOCAL / DR

Hugo
  │
  │ HUGO_API_MODE=LOCAL
  ▼
Browser
  │
  │ http://127.0.0.1:5000
  ▼
Flask DR proxy
  │
  │ local Lambda Python
  ▼
Lambda code
  │
  │ API_MODE=LOCAL
  ▼
membership_backup
```

Production mode is:

```text
REMOTE / Production

Hugo
  │
  │ HUGO_API_MODE=REMOTE
  ▼
Browser
  │
  │ AWS API Gateway
  ▼
AWS Lambda
  │
  ▼
Supabase PostgreSQL
```

---

## 2. Local DR database

The local database is:

```text
membership_backup
```

It runs on the Raspberry Pi's local PostgreSQL installation.

The application role used by the local Lambda code is:

```text
membership_app
```

The PostgreSQL administrator role is:

```text
postgres
```

The local application connection string is stored separately from the application source in:

```text
/home/tim/.membership-dashboard/supabase.env
```

The relevant local connection variable is:

```text
DATABASE_LOCAL_URL
```

This file is deliberately kept outside the Git repository.

---

## 3. Restoring the DR database

The local database is created/restored by:

```text
~/membership-scripts/restore_membership_local.sh
```

The restore uses PostgreSQL 17 `pg_restore`.

The restore process deliberately uses:

```text
--no-owner
--no-acl
```

The restored application tables are owned by:

```text
postgres
```

and the application role:

```text
membership_app
```

is subsequently granted the permissions required by the local Lambda code.

This is necessary because the backup was created from Supabase and the local restore does not automatically reproduce the application's local role permissions.

The restore script therefore includes the required grants so that permissions are reapplied whenever the DR database is rebuilt.

---

## 4. Important database separation

The production database and local DR database are independent.

Production:

```text
DATABASE_URL
    ↓
Supabase PostgreSQL
```

Local DR:

```text
DATABASE_LOCAL_URL
    ↓
membership_backup
```

The local Lambda code continues to use the normal:

```text
DATABASE_URL
```

interface.

The DR startup environment sets `API_MODE=LOCAL`, allowing the local Lambda/database configuration to select the local database connection.

This prevents the Lambda code from needing a separate application-specific database API.

---

## 5. Hugo API mode

Hugo uses the environment variable:

```text
HUGO_API_MODE
```

This variable is consumed by the Hugo templates and determines the API base URL exposed to the browser.

In LOCAL mode:

```text
HUGO_API_MODE=LOCAL
```

the browser uses:

```text
http://127.0.0.1:5000
```

In REMOTE mode:

```text
HUGO_API_MODE=REMOTE
```

the browser uses the AWS API Gateway endpoint.

The resulting browser configuration is exposed as:

```javascript
window.API_BASE_URL
```

Active Hugo JavaScript now uses this configurable value rather than hard-coded production API URLs.

For example:

```javascript
const API_BASE = `${window.API_BASE_URL}/api`;
```

This means the same Hugo source can operate against either the local DR API or the production API.

---

## 6. API mode vs database mode

There are deliberately two environment variables because they control different layers.

### HUGO_API_MODE

Controls where the browser sends API requests:

```text
HUGO_API_MODE
    ↓
Hugo
    ↓
window.API_BASE_URL
```

### API_MODE

Controls the environment used by locally executed Lambda code:

```text
API_MODE
    ↓
local Lambda/database configuration
    ↓
database connection
```

The local DR startup script therefore sets both:

```bash
export HUGO_API_MODE=LOCAL
export API_MODE=LOCAL
```

This distinction is important.

Changing `API_MODE` to `HUGO_API_MODE` in the database code would not be appropriate because the two variables serve different purposes.

---

## 7. Flask DR API proxy

The Flask proxy is:

```text
~/membership-dashboard/flask-dr/proxy.py
```

It provides a local API endpoint:

```text
http://127.0.0.1:5000
```

Its purpose is to make the locally running Lambda functions behave like the production API from Hugo's perspective.

For example:

```text
GET /api/towers
```

is received by Flask.

The proxy:

1. identifies the HTTP method and route;
2. identifies the corresponding Lambda;
3. constructs the Lambda event;
4. executes the Lambda Python code locally;
5. captures the Lambda response;
6. returns the response to the browser.

The browser therefore does not communicate directly with PostgreSQL.

---

## 8. Read-only DR proxy

The Flask DR proxy is deliberately read-only.

Initially, only read routes were enabled.

CORS `OPTIONS` requests are handled separately because browsers issue these requests as API preflights.

For example:

```text
[DR] Incoming: OPTIONS /api/members
[DR] CORS preflight: /api/members
```

is allowed to return:

```text
204
```

The actual API request is then handled by the appropriate local Lambda.

This allows the browser's normal authenticated API behaviour to continue working while preventing the DR proxy from accidentally performing write operations.

---

## 9. Lambda routing

The proxy maps API routes to the corresponding local Lambda code.

For example:

```text
GET /api/members
        ↓
membership-api-members
```

and:

```text
GET /api/payment-imports
        ↓
payments-api-import
```

The local Lambda code is the same application code used by the production Lambda deployment.

The difference is the environment in which it is executed and the database to which it connects.

---

## 10. Payment history and reporting APIs

The member-specific payment history endpoint is part of:

```text
membership-api-members
```

and is:

```text
GET /api/members/{id}/payment-history
```

It is used when viewing the payment history associated with a particular member.

The more general payment reporting functionality is provided separately by the payment reporting Lambda.

Examples include:

```text
GET /api/reports/payments/summary
```

and:

```text
GET /api/reports/payments/list
```

These are reporting endpoints rather than member-specific payment history.

---

## 11. Local startup

The local DR startup script sets both API mode variables:

```bash
export HUGO_API_MODE=LOCAL
export API_MODE=LOCAL
```

It then starts the Flask DR proxy and Hugo in local mode.

When running, the Flask console displays information such as:

```text
==============================================
 Local disaster-recovery API proxy
==============================================
Python:    /home/tim/membership-dashboard/.venv/bin/python
API_MODE:  LOCAL
Database:  DATABASE_LOCAL_URL is set
Read-only: YES
Listening: http://127.0.0.1:5000
==============================================
```

Hugo also reports the active configuration in the browser console:

```text
API_MODE: LOCAL
API_BASE_URL: http://127.0.0.1:5000
```

---

## 12. Remote startup

A separate startup script runs Hugo against the remote production API.

It sets:

```bash
export HUGO_API_MODE=REMOTE
```

The browser then uses the AWS API Gateway endpoint.

This allows production functionality to be tested from the Raspberry Pi without changing the Hugo source code.

---

## 13. Testing LOCAL vs REMOTE

The browser Network developer tools provide a definitive way to verify which API is being used.

In LOCAL mode, an API request should show a request URL beginning with:

```text
http://127.0.0.1:5000/
```

For example:

```text
http://127.0.0.1:5000/api/reports/payments/list?calendar_year=2026
```

In REMOTE mode, the same request should show the AWS API Gateway URL:

```text
https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/
```

For example:

```text
https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api/reports/payments/list?calendar_year=2026
```

The browser Network tab therefore provides a simple way to confirm the actual destination rather than relying only on the displayed mode.

---

## 14. DR database isolation test

A deliberate difference was introduced between production and DR to prove that the two environments were genuinely using different databases.

A new payment import was created in production.

The production environment therefore contained a new record in:

```text
payment_imports
```

The local DR database was checked directly using the PostgreSQL administrator account:

```bash
sudo -u postgres psql -d membership_backup
```

The table contained:

```text
0 rows
```

This confirmed that the new production import did not exist in the restored DR database.

Initially, however, the local API returned the production import.

Investigation showed that the browser-side mode switching was working, but the local Lambda code was still using the production database configuration because the database code expected:

```text
API_MODE
```

while Hugo had been changed to use:

```text
HUGO_API_MODE
```

The DR startup script was subsequently changed to set both:

```bash
export HUGO_API_MODE=LOCAL
export API_MODE=LOCAL
```

After this change:

* LOCAL Hugo displayed the empty DR payment-import list.
* REMOTE Hugo displayed the newly created production import.
* Flask continued to route the local API request to `payments-api-import`.
* The local Lambda accessed `membership_backup`.

This provided an end-to-end confirmation of database isolation.

---

## 15. Why the isolation test is important

Simply displaying:

```text
API_MODE: LOCAL
```

does not prove that the application is using the DR database.

Similarly, receiving:

```text
HTTP 200
```

does not prove that the correct database was queried.

The deliberately different payment-import data provided a much stronger test.

The final verified path was:

```text
LOCAL

Hugo
  ↓
127.0.0.1:5000
  ↓
payments-api-import
  ↓
membership_backup
  ↓
0 payment imports
```

while:

```text
REMOTE

Hugo
  ↓
AWS API Gateway
  ↓
payments-api-import
  ↓
Supabase
  ↓
new payment import
```

This confirms that LOCAL and REMOTE modes are genuinely isolated.

---

## 16. Active Hugo API configuration

The active Hugo source no longer contains hard-coded references to the production API Gateway URL.

A recursive search of the active source was performed while excluding:

* generated `public/` files;
* old files;
* test files.

The search returned no active hard-coded production API references.

Active JavaScript now obtains the API base from:

```text
window.API_BASE_URL
```

This allows the same source tree to be used for both LOCAL and REMOTE operation.

---

## 17. Generated Hugo files

The `public/` directory is generated by Hugo and should not be edited manually.

After changes to Hugo templates or static JavaScript, rebuild with:

```bash
hugo
```

The generated files in:

```text
public/
```

will then contain the current source configuration.

The old and test files containing historical hard-coded API URLs have deliberately been left unchanged because they are not part of the active application.

---

## 18. Git and production verification

The API-mode changes were committed to GitHub after testing.

The production deployment was then checked and confirmed to continue working.

The final production verification demonstrated that changing the active Hugo source to use a configurable API base did not break the production API path.

---

# Final configuration

```text
                         HUGO SOURCE
                              │
                 ┌────────────┴────────────┐
                 │                         │
          HUGO_API_MODE=LOCAL       HUGO_API_MODE=REMOTE
                 │                         │
                 ▼                         ▼
          127.0.0.1:5000             AWS API Gateway
                 │                         │
                 ▼                         ▼
          Flask DR proxy             AWS Lambda
                 │                         │
          local Lambda code              │
                 │                         │
          API_MODE=LOCAL                 │
                 │                         │
                 ▼                         ▼
       membership_backup              Supabase
```

## Status

**Local DR API environment: COMPLETE AND TESTED**

The following have been verified:

* Local PostgreSQL `membership_backup` database
* Required `membership_app` database permissions
* Restore-script permission grants
* Flask DR API proxy
* Local Lambda execution
* Read-only DR API behaviour
* CORS preflight handling
* `HUGO_API_MODE` switching
* `API_MODE` database selection
* Active Hugo JavaScript using configurable API URLs
* LOCAL API requests going to `127.0.0.1:5000`
* REMOTE API requests going to AWS API Gateway
* Production API continuing to work
* Deliberate production-vs-DR payment-import isolation test
* GitHub commit of the completed changes

The LOCAL environment can therefore be used as a practical disaster-recovery/test environment without the application accidentally reading from or modifying the live Supabase database.
