# Membership Dashboard — Payment Import API Design

## 1\. Purpose

The Payment Import API provides the workflow for turning bank statement data into confirmed membership payments.

It deliberately sits separately from the existing Payments API:

* **Payments API** — permanent membership-payment ledger and direct/manual payment entry.
* **Payment Import API** — temporary workflow for importing, reconciling, investigating and committing bank statement transactions.

This separation allows a single bank statement line to be split into multiple membership payments, while allowing individual portions to remain unresolved.

\---

## 2\. Existing Payments API

The existing Payments API manages confirmed payments.

### Direct payment creation

`POST /api/payments`

This is used when a Payment Administrator deliberately records a payment directly.

It remains available independently of the import workflow.

### Payment retrieval

`GET /api/payments`

Existing filtering includes:

* `member\_id`
* `calendar\_year`

The Payments API is restricted so that payment writing is available to `PaymentAdmin` and `ApplicationAdmin`.

`MembershipAdmin` has read access but does **not** have payment write access.

\---

# 3\. Payment Import API

The new Lambda will be:

`payments-api-import`

Its API Gateway routes will be under:

`/api/payment-imports`

The import workflow is intended primarily for `PaymentAdmin` and `ApplicationAdmin`.

\---

## 4\. Database Structure

The existing database has four related tables:

```text
payment\_imports
      │
      └── payment\_import\_lines
                │
                └── payment\_import\_items
                         │
                         └── payments
```

### `payment\_imports`

Represents one complete import batch, such as a bank statement upload.

Current statuses:

* `IN\_PROGRESS`
* `PARTIALLY\_COMMITTED`
* `COMPLETE`

### `payment\_import\_lines`

Represents one original bank statement line.

Contains:

* statement reference
* payment date
* original statement amount
* statement type
* description
* action (`IMPORT` or `IGNORE`)

### `payment\_import\_items`

Represents the administrator's allocation of a statement line to a member/payment.

Contains:

* member
* subscription amount
* gift amount
* calendar year
* status
* exception reason

Current statuses:

* `PENDING`
* `READY`
* `COMMITTED`
* `EXCEPTION`
* `RESOLVED\_EXTERNALLY`

Amounts may be positive or negative, allowing refunds.

### `payments`

Contains only confirmed membership payments.

Each committed payment retains its `import\_item\_id`, allowing the payment to be traced back through the import workflow to the original bank statement line.

\---

# 5\. API Operations

## 5.1 Create an import

`POST /api/payment-imports`

Creates a new `payment\_imports` record.

Example response:

```json
{
  "import": {
    "id": 17,
    "status": "IN\_PROGRESS"
  }
}
```

The Lambda records the authenticated user's Cognito identity in `created\_by`.

**Permissions:** `PaymentAdmin`, `ApplicationAdmin`

\---

## 5.2 Add statement lines

`POST /api/payment-imports/{import\_id}/lines`

Adds the parsed bank statement lines to the import.

Example:

```json
{
  "lines": \[
    {
      "statement\_reference": "C464",
      "payment\_date": "2026-08-03",
      "statement\_amount": 100.00,
      "statement\_type": "Counter Credit",
      "description": "TIMOTHY HART Peal fees - T I NR BG",
      "action": "IMPORT"
    }
  ]
}
```

`action` must be either:

* `IMPORT`
* `IGNORE`

\---

## 5.3 Retrieve an import

`GET /api/payment-imports/{import\_id}`

Returns the complete working state of an import, including:

* import status
* statement lines
* allocations
* member information
* allocated totals
* remaining amounts
* exception status

Derived values such as the remaining statement amount should be calculated rather than stored.

For example:

```text
Statement amount       £100.00
Allocated               £76.00
Remaining               £24.00
```

\---

## 5.4 Change a statement-line action

`PATCH /api/payment-import-lines/{line\_id}`

Used to change between:

* `IMPORT`
* `IGNORE`

This allows irrelevant bank statement lines to be excluded from the payment process.

\---

## 5.5 Add an allocation

`POST /api/payment-import-lines/{line\_id}/items`

Creates an allocation against a statement line.

Example:

```json
{
  "member\_id": 123,
  "subscription\_amount": 24.00,
  "gift\_amount": 5.00,
  "calendar\_year": 2026
}
```

The API validates the member and amounts.

The allocation does **not** have to balance the entire statement line immediately. This allows the administrator to work on a statement progressively.

\---

## 5.6 Amend an allocation

`PATCH /api/payment-import-items/{item\_id}`

Allows the administrator to change:

* member
* subscription amount
* gift amount
* calendar year
* exception status/reason

The Lambda performs the necessary validation.

The browser must not be able to arbitrarily mark an allocation `READY` when the underlying figures do not reconcile.





\# Payment Import API — 5.6 Amend an Allocation



\## Endpoint



`PATCH /api/payment-import-items/{item\_id}`



This endpoint amends an \*\*existing payment import allocation item\*\*. It never creates a replacement item.



One bank allocation therefore remains represented by the same `payment\_import\_item` throughout its lifecycle.



\---



\## Status Rules



\### PENDING



A `PENDING` item may be amended:



\- `member\_id`

\- `subscription\_amount`

\- `gift\_amount`

\- `calendar\_year`

\- `status` → `READY`

\- `status` → `EXCEPTION`



If changing to `EXCEPTION`, `exception\_reason` is required.



If changing to `READY`, the API must verify that the \*\*entire statement line is fully reconciled\*\*.



\### EXCEPTION



An `EXCEPTION` item may be amended:



\- `member\_id`

\- `subscription\_amount`

\- `gift\_amount`

\- `calendar\_year`

\- `status` → `PENDING`

\- `status` → `RESOLVED\_EXTERNALLY`



Returning an item to `PENDING` does \*\*not\*\* require the member to be supplied in the same request.



The administrator can subsequently amend the item through the normal allocation process once the membership record exists.



The existing `exception\_reason` is retained when an item returns to `PENDING`.



This supports temporary exceptions such as:



> Membership application awaiting a membership decision.



The same allocation item can therefore follow:



`PENDING → EXCEPTION → PENDING → READY → COMMITTED`



without creating a replacement item.



\### READY



A `READY` item may transition to:



\- `COMMITTED`

\- `EXCEPTION`



Before changing to `COMMITTED`, the API must re-check that the statement line is still fully reconciled.



This second reconciliation check protects against another allocation being changed after the item was marked `READY`.



\### COMMITTED



A `COMMITTED` item is final and cannot be amended.



No further status transitions or allocation changes are permitted.



\### RESOLVED\_EXTERNALLY



A `RESOLVED\_EXTERNALLY` item is final from the perspective of the payments application.



It cannot be amended.



It remains in the database for audit purposes but is excluded from the application's reconciliation total.



\---



\## Allocation Amount Rules



Whenever an allocation is amended, reconciliation is based on the \*\*net sum of all allocations for the statement line\*\*, including negative amounts.



Conceptually:



`net allocated = SUM(subscription\_amount + gift\_amount)`



`RESOLVED\_EXTERNALLY` items are excluded from this calculation.



Negative allocations are valid and must remain as separate allocation records. They are not corrections to another item.



For example:



| Allocation | Amount |

|---|---:|

| Member A | +£60.00 |

| Member B | +£40.00 |

| Refund/adjustment | -£10.00 |

| Additional allocation | +£10.00 |

| \*\*Net allocated\*\* | \*\*£100.00\*\* |



For a £100.00 statement line, this is fully reconciled.



The individual allocations must remain separate so that Phase 3 can create separate accounting entries, including credit entries for negative allocations.



\---



\## Amendments Must Replace the Existing Item's Allocation



When an existing item's amount is amended, its current allocation must not be counted in addition to its new allocation.



For example:



| Item | Current amount |

|---|---:|

| Item 1 | £60.00 |

| Item 2 | £30.00 |



If Item 2 is amended from £30.00 to £50.00, reconciliation must be calculated as:



`£60.00 + £50.00 = £110.00`



It must \*\*not\*\* be calculated as:



`£60.00 + £30.00 + £50.00 = £140.00`



Therefore the amendment calculation should exclude the current item from the existing total and then apply its proposed new values.



\---



\## Reconciliation Requirements



An item may only become `READY` when:



`net allocated = statement amount`



The line must therefore be fully reconciled.



An item must not become `READY` when the line is under- or over-allocated.



| Statement | Net allocated | Result |

|---:|---:|---|

| £100.00 | £100.00 | Reconciled — `READY` permitted |

| £100.00 | £90.00 | Not reconciled |

| £100.00 | £110.00 | Not reconciled |



The same reconciliation test must be repeated when moving from `READY` to `COMMITTED`.



\---



\## Exception Handling



`EXCEPTION` represents an allocation that cannot currently be processed normally.



It does \*\*not\*\* necessarily mean that the allocation has permanently failed.



Examples include:



\- membership record has not yet been created;

\- membership decision is pending;

\- member identification cannot currently be completed;

\- another issue requires administrative investigation.



A temporary exception can therefore return to `PENDING` once the problem has been resolved.



A permanent exception can instead move to `RESOLVED\_EXTERNALLY` when the matter will be dealt with outside the payments application.



\---



\## Audit Principle



The API must preserve the identity of the original allocation.



Status changes and amendments operate on the same `payment\_import\_item`.



The system must not create a new item merely because an allocation moves through an exception workflow.



\*\*One bank allocation = one `payment\_import\_item` throughout its lifecycle.\*\*



A future status-history table may be added if a complete record of every status transition is required. That is separate from the allocation item itself.



\---



\## Related APIs



| Description | Method and path | Status |

|---|---|---|

| Create an import | `POST /api/payment-imports` | Implemented |

| Add statement lines | `POST /api/payment-imports/{import\_id}/lines` | Implemented |

| Retrieve an import | `GET /api/payment-imports/{import\_id}` | Implemented |

| Change statement-line action | `PATCH /api/payment-import-lines/{line\_id}` | Planned |

| Add an allocation | `POST /api/payment-import-lines/{line\_id}/items` | Implemented |

| \*\*Amend an allocation\*\* | `PATCH /api/payment-import-items/{item\_id}` | \*\*Next\*\* |

| Delete an allocation | `DELETE /api/payment-import-items/{item\_id}` | Planned |

| Commit an import | `POST /api/payment-imports/{import\_id}/commit` | Planned |

| Complete an import | `POST /api/payment-imports/{import\_id}/complete` | Planned |

| Outstanding exceptions | `GET /api/payment-imports/items?status=EXCEPTION` | Planned |



\---

## 5.7 Delete an allocation

`DELETE /api/payment-import-items/{item\_id}`

An uncommitted allocation can be removed while the import is being worked on.

A committed allocation cannot be deleted through the import API, preserving the audit trail.

\---

# 6\. Exceptions

An individual allocation can be marked:

`EXCEPTION`

Example:

```json
{
  "status": "EXCEPTION",
  "exception\_reason": "Unable to identify payer"
}
```

This does not prevent other allocations belonging to the same statement line from being committed.

For example:

```text
Statement: £100

Member A     £24     READY
Member B     £24     READY
Member C     £24     READY
Unknown      £28     EXCEPTION
```

The three identified payments can be committed while the £28 remains unresolved.

\---

# 7\. External Resolution

Some exceptions may ultimately be dealt with outside this application.

For example, an unidentified payment may be recorded in the main accounts as an anonymous donation.

The payment application should then record:

`RESOLVED\_EXTERNALLY`

with an explanation in `exception\_reason`.

Example:

```json
{
  "status": "RESOLVED\_EXTERNALLY",
  "exception\_reason": "Unable to identify payer; recorded as anonymous donation"
}
```

No membership payment is created for this item.

\---

# 8\. Commit

`POST /api/payment-import-lines/{line\_id}/commit`

This converts all eligible `READY` allocations in a line in the import into confirmed rows in the `payments` table.

### Important distinction

This is **not** the same as:

`POST /api/payments`

`POST /api/payments` records an individual direct/manual payment.

The import `commit` operation processes the completed allocations generated by the import workflow.

The commit operation will use the same underlying payment-creation business logic as the direct Payments API, but it will not make an HTTP request to the Payments API.

\---

## 8.1 Transactional behaviour

All eligible READY allocations should be processed within one database transaction.

For example:

```text
READY 1
READY 2
READY 3
...
READY 9
```

Either all nine payments are created and their import items marked `COMMITTED`, or the transaction is rolled back.

This prevents a partially successful commit.

\---

## 8.2 Partial imports

The commit operation does **not** require the entire bank statement import to be resolved.

For example:

```text
Line 1 → committed
Line 2 → committed
Line 3 → exception
Line 4 → committed
```

The import can therefore become:

`PARTIALLY\_COMMITTED`

while outstanding exceptions remain.

This is a key requirement of the payment-import workflow.

\---

# 9\. Complete an Import

`POST /api/payment-imports/{import\_id}/complete`

Marks the entire import as:

`COMPLETE`

This is deliberately separate from `commit`.

### Commit means:

> Write all currently ready payments to the permanent ledger.

### Complete means:

> The administrator has finished dealing with this entire bank statement import.

An import should only be marked complete when there are no unresolved `PENDING` or `EXCEPTION` items.

Items may be:

* `COMMITTED`
* `IGNORED`
* `RESOLVED\_EXTERNALLY`

when the import is completed.

\---

# 10\. Outstanding Exceptions

`GET /api/payment-imports/items?status=EXCEPTION`

Returns outstanding payment exceptions.

This will allow the dashboard to show something such as:

> 3 payment exceptions require investigation

A similar query can be used for pending items.

\---

# 11\. Idempotency

The commit operation must be safe if the administrator accidentally presses the Commit button more than once.

Only allocations with:

`status = READY`

are eligible for commitment.

Once successfully processed they become:

`COMMITTED`

A subsequent commit therefore cannot create the same payment again.

The existing duplicate-payment checks also remain an additional safeguard.

\---

# 12\. Permissions

|Operation|PaymentAdmin|ApplicationAdmin|MembershipAdmin|MembershipViewer|
|-|-:|-:|-:|-:|
|View payments|Yes|Yes|Yes|Yes|
|Create direct payments|Yes|Yes|No|No|
|Create imports|Yes|Yes|No|No|
|Process imports|Yes|Yes|No|No|
|Allocate payments|Yes|Yes|No|No|
|Resolve exceptions|Yes|Yes|No|No|
|Commit payments|Yes|Yes|No|No|
|Complete imports|Yes|Yes|No|No|

`MembershipAdmin` therefore retains read-only access to the confirmed payment ledger but cannot create or modify payments.

\---

# 13\. Architectural Principle

The application deliberately separates:

### Permanent ledger

```text
payments
```

from:

### Temporary/import workflow

```text
payment\_imports
payment\_import\_lines
payment\_import\_items
```

The import workflow allows administrators to investigate and reconcile bank transactions without polluting the permanent membership-payment ledger.

Only confirmed allocations become `payments`.

Exceptions that cannot be resolved within the application can be marked `RESOLVED\_EXTERNALLY` and retained for audit purposes without creating a membership payment.

\---

# 14\. Shared Payment-Creation Logic

The existing direct payment API and the import commit operation should use the same underlying payment-creation business logic.

Conceptually:

```text
POST /api/payments
        │
        ▼
create\_payment()
        │
        ▼
payments
```

and:

```text
POST /api/payment-imports/{id}/commit
        │
        ▼
create\_payment()
        │
        ▼
payments
```

The import commit additionally manages:

* import-item status
* import status
* transaction handling
* reconciliation
* batch processing

This avoids having two different implementations of payment creation.

\---

# 15\. Planned Lambda

The existing Lambda remains:

```text
payments-api-payments
```

The new import workflow will be implemented as:

```text
payments-api-import
```

The two Lambdas have clearly separated responsibilities:

**`payments-api-payments`**

Permanent payment ledger and direct payment entry.

**`payments-api-import`**

Bank statement import, reconciliation, exceptions and committing ready allocations.

This design provides a clear audit trail from a confirmed payment back to its original bank statement transaction.

