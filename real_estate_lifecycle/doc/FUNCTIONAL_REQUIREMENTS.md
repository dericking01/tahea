# Functional Requirements & Architecture

## 1. Purpose
Help real-estate businesses answer five questions at any time:
1. What do we own or manage? (property register, ownership, equipment)
2. What should each property earn, and what are we collecting? (rent roll, billing schedule, economic occupancy, collections, ageing)
3. What does each property cost to operate and maintain? (analytic P&L, NOI, maintenance and capex)
4. Which problems need management attention? (revenue-assurance and control exceptions, overdue work, expiries, arrears)
5. Which actions improve long-term performance? (property comparison, replacement analysis, investment actual vs projected)

## 2. Design principles
* **One accounting engine.** All money flows through native `account.move` (customer invoices, credit notes, vendor bills), `account.payment`, reconciliation and `purchase.order`. Business records only *link* to accounting documents, and posted entries are never modified by operational workflows.
* **Analytic accounting is the property dimension.** Property and building analytic accounts are created automatically. `account.move.line.re_property_id` / `re_building_id` are derived from the analytic distribution, so any journal entry with the property's analytic account is included in the property P&L.
* **Reuse.** Contacts (tenants, owners, contractors), CRM (leasing pipeline), Purchase (RFQ/PO), Maintenance (equipment), Accounting (fixed asset link), Portal, Mail (chatter, activities, tracking).
* **Controls by design.** Approval framework with tiers and segregation of duties, an immutable audit log, posting controls, and daily exception detection with auto-resolution.
* **Idempotent automation.** Billing, preventive maintenance and service-charge application can run any number of times.

## 3. Data model (main objects)

```
re.portfolio ──< re.property >── re.property.ownership (owner, role, %, dates)
                    │  ├── re.property.valuation (approved history)
                    │  ├── re.land.encumbrance
                    │  ├── account.analytic.account (Properties plan)
                    │  ├──< re.building ──< re.floor
                    │  │        └── account.analytic.account (Buildings plan)
                    │  └──< re.unit (space or plot; occupancy vs rental status)
                    │
re.lease (tenant, units M2M, terms, approval) ──< re.lease.charge
   ├──< re.lease.escalation (approval)          ├──< re.lease.amendment (approval)
   ├──< re.billing.schedule (lease × obligation × period, UNIQUE) ──> account.move(.line)
   ├──< re.security.deposit ──< re.deposit.deduction ──> invoice / refund credit note
   └──< re.turnover.report ──> account.move
re.service.charge.budget ──< budget.line (accounts) ──< allocation (unit, lease, share)
re.meter ──< re.meter.reading ──> account.move.line
re.collection.case ──< re.collection.promise
re.tenant.ticket >── re.building.issue ; re.announcement
maintenance.equipment (+RE fields, account.asset link) ──< re.work.order ──< purchase.order ──> vendor bills
re.maintenance.plan ──< re.work.order
res.partner (+tenant / contractor fields) ──< re.vendor.license ; re.vendor.contract
re.approval.rule ; re.approval.log ; re.control.check ; re.exception
re.tenant.ageing (SQL view on receivable journal items)
re.investment ──< re.investment.cashflow
re.analytics (KPI service), re.report.wizard (report engine)
```

## 4. Key business rules
| Area | Rule |
|---|---|
| Hierarchy | Unit floor ⊂ building ⊂ property. Land holds plots only and no buildings. |
| Occupancy | Physical occupancy (manual, set on move-in/out) is distinct from rental status (derived from leases). Non-rentable and *Unavailable* units are excluded from occupancy KPIs. |
| Overlap | A unit cannot be in two submitted/approved/active leases with overlapping dates unless authorised for multi-occupancy. |
| Lease locking | After submission, commercial terms change only through approved amendments. Approved escalations and invoiced billing lines cannot be edited or deleted. |
| Billing | Periods are deterministic (calendar or anniversary). Monthly rates are pro-rated by day. Escalations are compounded by effective date. Rent-free periods are zero. Pending lines are recomputed when terms change, and invoiced lines are kept as history. |
| Deposits | Invoiced to a liability account. Refunded via approved credit note (liability released, deductions to income). |
| Service charge | Allocation by area, equal share or custom %, with vacant shares borne by the landlord. Actual = posted lines on mapped accounts for the building/property in the period. Reconciliation produces draft documents. |
| Maintenance spend | Budget approval before PO confirmation. Bills above approved + tolerance are blocked (FM override logged). Completion above the approved amount requires supplementary approval. Emergencies need post-review. |
| Approvals | Highest matching tier. With segregation, requester ≠ approver. All actions are logged and logs are immutable. |
| Exceptions | Deterministic key per finding, so no duplicates. Auto-resolved when the condition disappears, and re-opened if it reappears. |

## 5. KPI definitions
| KPI | Definition |
|---|---|
| Physical occupancy | Occupied rentable units ÷ available rentable units (excluding non-rentable and *Unavailable* units) |
| Area-weighted occupancy | Occupied rentable m² ÷ available rentable m² |
| Economic occupancy | Effective rent revenue (posted rent, turnover rent and concessions net of credit notes, dated in period) ÷ gross potential rent (Σ expected monthly rent of available rentable units × months in period) |
| Rental income invoiced | Posted rental-related invoice lines (all charge types except deposits), untaxed, net of credit notes, dated in period |
| Collected & allocated | Reconciliation amounts in the period between tenant payments and rental invoices of the selected properties (includes arrears) |
| Total collections | All tenant receipts posted in the period, allocated or not |
| Collection efficiency | For rental invoices due in the period: paid ÷ due |
| Outstanding | Open receivable of rental invoices today, with disputed amounts shown separately |
| NOI | Revenue on Income accounts − opex on Expense and Cost of Revenue accounts, analytically allocated, dated in period. Excludes configured accounts (financing, tax, depreciation), capex (asset accounts) and deposits (liability). |
| Gross / net yield | Annualised invoiced rent / NOI ÷ property value (latest approved valuation, else purchase price) |
| Maintenance expenditure | Posted vendor bills linked to work orders, untaxed |
| Capex variance | Actual − approved budget of CAPEX work orders requested in the period |
| Collection ageing | Days past due of each open receivable item: Current, 1-30, 31-60, 61-90, 90+, Disputed |

## 6. Investment appraisal formulas
See the docstring of `models/re_investment.py`: GPR, EGI, OPEX, NOI, cash flow, exit value = NOI(N+1) ÷ exit cap × (1 − selling costs), NPV, IRR (bisection), equity IRR (after level-annuity debt service and loan repayment at exit), payback (excluding sale), ROI, yields, DSCR, break-even occupancy = (opex + debt service) ÷ GPR.

## 7. Security model
* Groups: 13 internal roles plus portal tenants and contractors (see CONFIGURATION §6).
* ACL matrix: `security/ir.model.access.csv` (generated from a role × model matrix).
* Record rules (`security/re_rules.xml`):
  * multi-company rules on every company-bearing model;
  * property scope for Leasing Officer / Property Manager (manager, authorised staff, or portfolio manager);
  * technician scope (assigned work orders and related property/equipment);
  * investor scope (read-only, investor users on the property);
  * company-wide "all records" rules for Accountant, Maintenance Manager, Procurement and Investment roles;
  * portal rules (own leases, tickets and requests; contractor-assigned work orders; published announcements).
* Dashboard and reports search properties **as the user**, so rules apply, then aggregate accounting data only for those properties.
* Portal controllers read as the portal user (rules apply) and write through validated actions.
