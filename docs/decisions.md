# Architectural Decisions

## ADR-001

District is not stored in members.

Reason:
District can always be derived through towers.

Benefits:
- No duplicate data
- Prevents inconsistencies

Date:
2026-08-07

Membership number is unique.
District is derived from tower.
Payments are a separate table.
Gift Aid is a lookup table.
Audit records are append-only.
Serverless architecture using Hugo + API Gateway + Lambda + Supabase.

2026-08-06

Added CORS configuration to API-GATEWAY, to allow different url request

08/08/26
