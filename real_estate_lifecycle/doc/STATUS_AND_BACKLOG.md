# Development Status, Backlog, Limitations & Integration Requirements

Status date: 2026-11-20 · Module version 18.0.1.0.0 · Verified on Odoo 18.0 Enterprise (build 20260421).

## 1. Completed functionality (Phase 1, plus parts of Phase 2)

| # | Capability | Status |
|---|---|---|
| 1 | Property register (17 classifications, land vs built, location/GPS, title, insurance, encumbrances, valuations with approval, ownership history with %, managing company vs owner vs accounting company vs investors) | Done |
| 2 | Buildings, floors, units and plots; area units with m² conversion; land subdivision; physical occupancy vs rental status | Done |
| 3 | Tenant register (contacts + tenant profile, NIDA/BRELA ID, payment behaviour) | Done |
| 4 | Leasing pipeline on CRM (enquiry, viewing, application, screening, offer) | Done |
| 5 | Lease management: multi-unit, joint tenants, lease types, billing frequency/anchor, rent-free, deposits, clauses, notice, break, overlap prevention, signature tracking | Done |
| 6 | Lease approval, amendments (rent change, extension, concession, new charge), non-contractual escalations: configurable tiers, segregation of duties, audit log | Done |
| 7 | Lease lifecycle: Draft → Submitted → Approved → Active → Expiring → Renewed/Terminated/Expired; renewal and termination wizards; alerts at configurable days | Done |
| 8 | Rental billing engine: idempotent schedule, pro-rating, escalations, rent-free, service/parking/levy/other charges, concessions, turnover rent (greater-of / additional, breakpoint), native invoices, draft or auto-post | Done |
| 9 | Security deposits as liability; deductions; approved refund via credit note | Done |
| 10 | Payments & reconciliation: native; tenant ageing view; disputes; statements | Done |
| 11 | Collections: cases, reminders (email template), promises/instalments with kept/broken tracking, escalation, management review | Done |
| 12 | Service charges: budgets mapped to accounts, allocation, approval, billing, actual vs budget, billed/collected, year-end reconciliation documents and report | Done |
| 13 | Utilities: tariffs, meters, readings, consumption, recharge billing, trends; smart-meter intake API (idempotent) | Done (no vendor connected) |
| 14 | Equipment register (extends Maintenance), fixed-asset link, lifecycle cost and replacement analysis | Done |
| 15 | Work orders: full 9-state flow, tiered approval, emergency with post-review, supplementary budget, RFQ comparison → PO → bill, actual cost from bills, tenant confirmation and rating, evidence | Done |
| 16 | Preventive maintenance plans (calendar and run-hour usage), compliance % | Done |
| 17 | Vendor/contractor register: licences, insurance, compliance, contracts with expiry, performance metrics | Done |
| 18 | Property accounting: analytic P&L, NOI policy, capex separation, property ledger, income statement report | Done |
| 19 | Financial controls: bill vs approved budget (block/override), PO vs approved budget, credit-note approval, duplicate bills, missing/wrong allocation, unapproved spend, refunds | Done |
| 20 | Revenue-assurance engine: 27 checks, configurable, deterministic keys, auto-resolution, responsible users, activities | Done |
| 21 | Tenant CRM: tickets, building-level clustering into shared issues, announcements, satisfaction | Done |
| 22 | Tenant portal (leases, invoices/pay via Odoo, statement PDF, requests with attachments, disputes, renewals, announcements, work confirmation) and contractor portal (jobs, start/complete, evidence) | Done |
| 23 | Executive dashboard (OWL): filters, 21 KPIs with definitions, ageing, arrears, exceptions, expiries, property comparison | Done |
| 24 | Report engine: 19 management reports in PDF and Excel, plus 5 document PDFs; native list export (Excel/CSV) | Done |
| 25 | Roles, ACLs and record rules (company, property, technician, investor, portal) | Done |
| 26 | Investment appraisal (Phase 2): assumptions, cash flows, NPV, IRR, equity IRR, ROI, payback, yields, DSCR, break-even; scenarios; approval lock; authorised revisions; actual vs projected | Done |
| 27 | Demo data, 36 automated tests, documentation | Done |

## 2. What has been tested

Automated (`--test-tags /real_estate_lifecycle`): **36 tests, 0 failures, 0 errors**, on a fresh Odoo 18 Enterprise database with a test chart of accounts.

| Brief acceptance test | Covered by |
|---|---|
| 1 Property registration & navigation | `test_property_leasing.test_01` |
| 2 Tenant leasing & occupancy | `test_property_leasing.test_02` (+ renewal `test_03`, CRM `test_04`) |
| 3 Rental billing & no duplicates | `test_billing.test_01`, `test_06` |
| 4 Rental escalation | `test_billing.test_04` |
| 5 Partial payment 2,000,000 / 1,200,000 → 800,000 in ageing | `test_billing.test_05` |
| 6 Security deposit liability & authorised refund | `test_deposit_service_charge.test_01` |
| 7 Service charges: 10 tenants, 50M budget | `test_deposit_service_charge.test_02` |
| 8 Maintenance: elevator, technician, approval, expenditure, history | `test_maintenance_procurement.test_01`, `test_02` |
| 9 Revenue leakage detection & resolution | `test_revenue_assurance.test_01`, `test_02`, `test_03`, `test_06` |
| 10 Multi-company security | `test_security.test_01` |
| 11 Vendor procurement | `test_maintenance_procurement.test_03` |
| 12 Portfolio dashboard accuracy | `test_dashboard_investment.test_01` |
| 13 Access control per role | `test_security.test_02`–`test_08`, `test_portal_http` |
| 14 Accounting integrity | `test_billing.test_06`, `test_revenue_assurance.test_04`, deposit and procurement tests |

Also tested: partial periods and rent-free, quarterly billing with charges, turnover rent, shared building issues, utility recharge and smart-meter API idempotency, preventive plan idempotency, duplicate vendor bills, control overrides, investment formulas (IRR = cap rate case), revision locking, tenant and contractor portals over HTTP, compilation of the backend asset bundle (JS/SCSS), PDF and Excel rendering of 10 report types.

Manual verification on the demo database: billing run created 21 draft invoices and a second run created 0; the exception engine reported the expected leakage cases; the shared water issue was created; PDF reports rendered.

**Not executed:** a browser (UI tour) test of the OWL dashboard. There is no headless Chrome in the container, so the dashboard's client-side rendering was verified only through asset compilation and its server-side data method. Please open *Real Estate › Dashboard* once after installation.

## 3. Deferred / not implemented (roadmap backlog)

These are intentionally **not** shown as menus, so there are no empty screens.

| Phase | Item | Notes |
|---|---|---|
| 2 | Development & construction management (projects, budgets/revisions, tenders, variation orders, payment certificates, retention, snagging, handover wizard creating buildings/units/equipment) | Designed to reuse `purchase.order`, analytic plans (a "Development Projects" plan) and `account_asset`; the *Development Project Manager* role exists and currently covers capital work orders and appraisals. |
| 2 | Owner / investor **external** portal | Investors are currently internal read-only users scoped to their properties (dashboard + reports). |
| 2 | General property budgets (all income/expense lines) | Service-charge and work-order budgets exist. Enterprise `account_budget` can be used on the property analytic accounts in the meantime. |
| 2 | Property risk & compliance register (permits, fire certificates, statutory inspections) | Insurance expiry, title expiry and contractor compliance exist. |
| 2 | Plot sales with instalment schedules, buyer receivables; off-plan sales | Plot status, buyer and value fields exist. Sales would use sale orders/invoices. |
| 2 | Real-estate fund management | Not started. |
| 3 | Predictive maintenance, revenue forecasting, AI recommendations, profitability simulations, energy optimisation, digital twin, live smart-building integrations | Not started. Current outputs are rule-based (replacement analysis, exceptions). The meter API is the intake point for sensor data. |
| – | Odoo **Sign** / **Documents** integration | Signed agreements are attachments with a *Mark as Signed* control; Sign/Documents apps can be used alongside. |
| – | CPI / index-linked escalations, stepped rent schedules beyond escalations | Percentage, fixed and new-amount escalations are supported. |
| – | Holding-over (mesne profit) automatic billing | Flagged by the `expired_lease_occupied` check; billing requires a renewal or amendment. |

## 4. Known limitations
* Lease charges are expressed as **monthly** amounts (billed per frequency, pro-rated by day).
* The billing schedule horizon is 24 months ahead and is extended daily by the cron.
* KPIs and ageing are in **company currency**; leases in a foreign currency are invoiced in that currency and converted by Odoo.
* Journal items posted *before* installation are not allocated to properties (no backfill, by design, for performance). Re-saving the analytic distribution of a line allocates it.
* Allocation of collections to properties relies on reconciliation. Unallocated receipts are not attributed to a property until reconciled.
* The exception engine scans all companies with superuser rights in one daily job. For very large portfolios (tens of thousands of leases), schedule checks individually or move to queued batches.
* Approval rule thresholds are in each rule's currency, assumed equal to the company currency.
* The demo data approves leases directly (no approval workflow) to give a ready-to-use dataset.

## 5. External integrations requiring credentials or third-party configuration

Nothing below is simulated or claimed as working.

| Integration | Status | What is needed |
|---|---|---|
| **Mobile money (M-Pesa, Tigo Pesa, Airtel Money, HaloPesa)** | Not implemented | A payment provider module per aggregator (Selcom, DPO, Azampay, ClickPesa…) implementing Odoo's `payment.provider` interface, plus credentials (API key/secret, merchant ID, callback URL). Once installed, tenants pay invoices from the portal and payments are posted and reconciled natively. Idempotency must use the provider transaction reference. |
| **GePG** (government payments, e.g. land rent) | Not implemented | GePG SP code, certificates, signing keys and the bill/control-number exchange through an accredited system. Land rent is recorded on the property, but no bill is pushed. |
| **Bank integrations** | Uses Odoo | Odoo Enterprise bank synchronisation (where the bank is supported) or CAMT/MT940/CSV statement import; reconciliation is native. |
| **SMS** | Not implemented | Odoo `sms` (IAP credits) or a local gateway connector (e.g. Beem, Africa's Talking) with an API key; reminders currently use email and activities. |
| **WhatsApp** | Not implemented | Odoo Enterprise `whatsapp` app with a Meta Business account, phone number ID and approved templates. |
| **Smart meters / BMS** | Intake interface implemented and tested (`re.meter.reading.api_submit_readings` via JSON-RPC/XML-RPC; idempotent by external id; per-reading status) | Middleware for the specific vendor (polling or webhook) and an integration user with Property Manager rights. No vendor is connected. |
| **TRA / EFD / VFD e-invoicing** | Not implemented | Requires a TRA-approved VFD/EFD integration provider and credentials. |
