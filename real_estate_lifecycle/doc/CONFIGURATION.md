# Configuration Guide

All settings are per company. Menu: **Real Estate › Configuration** (Real Estate Administrator role).

## 1. Accounting (do this first, with your accountant)

### 1.1 Invoice products and taxes
**Settings › Real Estate › Rental Billing › Invoice products**

The module ships service products *Rent, Service Charge, Parking Fee, Marketing Levy, Utility Recharge, Turnover Rent, Other Lease Charge, Maintenance & Repair Services, Capital Works (CAPEX)* **with no taxes**. Nothing is hardcoded:

* Set the **income account** on each rental product (e.g. Rental Income, Service-Charge Income, Utility Recoveries) and the **expense account** on the maintenance and capex products. Capex should point to an asset or WIP account so that it is excluded from NOI.
* Set the **customer taxes** according to the approved tax treatment. Different treatments (e.g. residential vs commercial rent, exempt tenants) are handled with **fiscal positions**:
  * on the *Lease Type* (default per lease type), or
  * on each lease (*Fiscal Position / Tax Treatment*), or
  * on the tenant (standard Odoo behaviour).
* You can replace any product with your own.

### 1.2 Rental journal and posting policy
* *Rental Invoice Journal*: the sales journal used for rent (default: first sales journal).
* *Auto-post Rental Invoices*: off by default, so generated invoices stay in **draft** for accountant review. Switch it on once you trust the configuration.
* *Missing Invoice Grace (days)*: delay before an unbilled obligation is flagged.

### 1.3 Security deposits
* **Tenant Deposit Liability Account** (required to invoice deposits): a *Current Liabilities* account. The module refuses to use a non-liability account.
* **Deposit Deduction Income Account**: credited with approved deductions at refund time.

### 1.4 Analytic accounting
Two analytic plans are created: **Real Estate Properties** and **Real Estate Buildings**. Each property and building gets its analytic account automatically. Every rental invoice, deposit, PO line and work-order bill carries the property (and building) distribution. Any other journal entry (salaries of on-site staff, utility bills, insurance) becomes part of the property P&L as soon as you put the property's analytic account on the line.

### 1.5 NOI policy
*Settings › Financial Controls › NOI policy*

* Revenue = posted lines on **Income** accounts (+ **Other Income** if ticked).
* Operating expenses = **Expenses** and **Cost of Revenue** accounts.
* *Accounts excluded from NOI*: add interest/financing, income tax, and any depreciation booked on expense accounts.
* Capital expenditure (Fixed / Non-current asset accounts) is always excluded and reported separately. Deposits (liability) never enter NOI.

## 2. Approval rules
**Configuration › Approval Rules**

For each document type, the active rule with the **highest minimum amount ≤ document amount** applies. If no rule matches, no approval is needed and the system logs an *auto-approved* entry. *Segregation of duties* prevents the requester from approving.

| Document | Amount used | Default rule |
|---|---|---|
| Lease approval | annual rent (company currency) | Portfolio Manager, segregated |
| Lease amendment / rental change | annual rent change | Portfolio Manager, segregated |
| Rental concession | monthly concession | Director, segregated |
| Non-contractual escalation | annual increase | Portfolio Manager, segregated |
| Deposit refund | net refund | Finance Manager, segregated |
| Tenant credit note | credit amount | Finance Manager, segregated |
| Maintenance expenditure (OPEX work orders) | proposed cost | Property Manager (self-approval allowed) |
| Capital expenditure (CAPEX work orders) | proposed cost | Director, segregated |
| Service-charge budget | total budget | Finance Manager, segregated |
| Valuation | value | Director, segregated |
| Investment acquisition | total investment | Director, segregated |

Add tiers with higher minimums, for example *Maintenance ≥ 5,000,000 → Maintenance Manager*, *≥ 20,000,000 → Director* (the demo data contains these two). Approvers are notified with an activity, and every request, approval, rejection and override is written to the immutable **Approval Audit Trail**.

## 3. Financial controls
*Settings › Financial Controls*

| Setting | Effect |
|---|---|
| Block unapproved tenant credit notes | Posting a tenant credit note requires adjustment approval (otherwise it is posted and flagged). |
| Block vendor bills above approved work-order budget + tolerance % | Non finance managers cannot post. Finance managers can, and the override is logged as an exception. |
| Require PO for contractor work | Direct contractor bills are flagged (`bill_without_po`). |
| Work-order overrun tolerance % | Completion requires supplementary approval above it. |

Purchase orders linked to a work order cannot be confirmed unless the work-order budget is approved and covers the amount (finance-manager override logged).

## 4. Revenue-assurance controls
**Configuration › Revenue Assurance Controls**: activate or deactivate each check and set its severity, grace days, amount or % threshold and default responsible user. *Run* executes a single check on demand. The daily cron runs all of them. See the user manual for the list.

## 5. Leasing
* **Lease Types**: default billing frequency, notice period, deposit months, fiscal position.
* **Lease alert days**: e.g. `120,90,60,30`. An activity is scheduled for the leasing officer at each threshold.
* **Expiring window**: days before end when an active lease shows as *Expiring*.

## 6. Users and roles
Assign roles in **Settings › Users › Real Estate**:

| Role | Scope |
|---|---|
| Real Estate Administrator | everything + configuration |
| Group Property Director | all companies' properties allowed to the user; all approvals |
| Portfolio Manager | all properties of the allowed companies; approves leases/amendments |
| Property Manager | **only** properties where they are *Property Manager* or in *Authorised Staff* (or manage the portfolio) |
| Leasing Officer | same property scope; prospects, tenants, draft leases |
| Accountant / Finance Manager | billing, deposits, collections, financial reports (company-wide); FM approves refunds and may override controls |
| Maintenance Manager / Technician | all maintenance / **only assigned work orders** and related property & equipment |
| Procurement Officer | vendors, quotations, POs |
| Investment Manager / Development PM | investment appraisals (+ capital works) |
| Property Owner / Investor | read-only, only properties where they are listed as *Investor / Owner User* (dashboard and reports included) |
| Tenant (portal user) | own leases, invoices, statement, requests |
| External Contractor (portal user) | jobs assigned to their company |

Access is enforced with ACLs and record rules (company + property level), not just by hiding menus. Give portal access from the tenant/contractor contact (*Action › Grant portal access*).

## 7. Other master data
Property Types (17 classifications incl. land types), Area Units (m², ft², acre, ha), Asset Categories (useful life, replacement-review threshold), Maintenance Categories (target days, priority), Request Categories (which complaints are clustered per building), Contractor Service Categories, Utility Tariffs.

**Shared building issues**: *Settings › Tenant Experience*. When N different tenants report the same category in the same building within D days, a shared issue is created and linked.

**Collections**: open a case after *N* days overdue above a minimum amount.

## 8. Localisation notes (Tanzania / East Africa)
* Currency: properties and accounting follow the company currency (TZS where the company uses TZS). Leases can be invoiced in another currency (e.g. USD commercial leases). Exchange rates come from Odoo's currency rates; none are hardcoded.
* Timezone: set users to `Africa/Dar_es_Salaam` (user preferences). Dates use the user's timezone.
* Land title fields cover Granted Right of Occupancy, CCRO, Residential Licence and Letter of Offer, with term (33/66/99 years) and annual land rent. Tenant IDs include NIDA and BRELA. Contractor licences include CRB, EWURA, ERB, OSHA and tax clearance.
* Taxes: use your localisation / accountant-approved taxes (Odoo has no Tanzanian fiscal localisation module; configure taxes and fiscal positions manually).
