# Database

The membership dashboard uses PostgreSQL as its database.

The database is normalised so that descriptive information is stored in its own tables and related through foreign keys rather than duplicated in the `members` table.

## Tables

### `members`

Stores the core membership record.

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `id` | bigint | No | Primary key |
| `membership_number` | text | No | Unique membership number |
| `first_name` | text | No | Member's first name |
| `surname` | text | No | Member's surname |
| `tower_id` | bigint | No | References `towers.id` |
| `membership_class_id` | bigint | Yes | References `membership_classes.id` |
| `membership_status_id` | bigint | Yes | References `membership_statuses.id` |
| `full_member_type_id` | bigint | Yes | References `full_member_types.id` |
| `date_of_birth` | date | Yes | Member's date of birth |

### `towers`

Stores the tower/church associated with a member.

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `id` | bigint | No | Primary key |
| `tower_name` | varchar | No | Name of the tower |
| `district_id` | bigint | No | References `districts.id` |
| `active` | boolean | Yes | Whether the tower record is active |
| `created_at` | timestamp | Yes | Record creation timestamp |

### `districts`

Stores district definitions.

| Column | Type | Nullable | Description |
|---|---|---:|---|
| `id` | bigint | No | Primary key |
| `code` | varchar | No | District code |
| `name` | varchar | No | District name |
| `active` | boolean | Yes | Whether the district is active |

### `membership_classes`

Stores membership class definitions.

| ID | Code | Name |
|---:|---|---|
| 1 | `FULL` | Full member |
| 2 | `ASSOCIATE` | Associate member |
| 3 | `NRLM` | Non-resident life member |

### `membership_statuses`

Stores membership status definitions.

| ID | Code | Name |
|---:|---|---|
| 1 | `ACTIVE` | Active |
| 2 | `LEFT` | Left |
| 3 | `DECEASED` | Deceased |

### `full_member_types`

Stores full-member type definitions.

| ID | Code | Name |
|---:|---|---|
| 1 | `STANDARD` | Standard |
| 2 | `FTE` | Full-time education |
| 3 | `AGE_70_79` | Age 70-79 |
| 4 | `AGE_80_PLUS` | Age 80+ |
| 5 | `HLM` | Honorary life member |

## Relationships

The main relationships are:

```text
members
  │
  ├── tower_id ──────────────► towers.id
  │                              │
  │                              └── district_id ──► districts.id
  │
  ├── membership_class_id ───► membership_classes.id
  │
  ├── membership_status_id ──► membership_statuses.id
  │
  └── full_member_type_id ───► full_member_types.id
```

## District derivation

District is deliberately **not stored on `members`**.

A member's district is derived through the tower relationship:

```text
member.tower_id
    ↓
towers.id
    ↓
towers.district_id
    ↓
districts.id
```

This avoids storing the same district information in multiple places and prevents duplicated or inconsistent data.

## Lookup-table `active` fields

The `active` field on lookup tables indicates whether that lookup definition is currently available for use.

It does **not** mean that the corresponding member is currently active.

For example, `membership_statuses` contains `DECEASED` with `active = true`. This means that "Deceased" is a valid status that can be assigned to a member; it does not mean that deceased members are active.

## Design principle

The database stores identifiers and relationships. Human-readable descriptions should normally be obtained through the related lookup tables.

The API may return both identifiers and descriptive values where this makes the API more useful to the frontend, without duplicating those values in the database.