# User Manual

Menu root: **Real Estate**. Every list can be exported to Excel/CSV (select records › *Export*), and lists, pivots and graphs can be filtered and grouped. Buttons shown depend on your role.

---

## 1. Register a property
1. **Properties › Properties › New**.
2. Enter *Name*, *Code* (proposed automatically), *Property Type* (e.g. Apartment Building, Shopping Mall, Undeveloped Land), *Portfolio*, *Property Manager* and *Accounting Company*.
3. Tabs:
   * *Location*: address, ward, district, region, GPS.
   * *Physical & Value*: land size and unit (m², ft², acre, ha), building area, acquisition date and price. Add **valuations** (*Submit*, then a director approves). The latest approved valuation becomes the *Current Valuation*.
   * *Ownership*: legal owner(s), co-owners, beneficial owners and investors with % and effective dates (history is kept; legal ownership cannot exceed 100% for overlapping periods). *Authorised Staff* and *Investor / Owner Users* control who can see the property.
   * *Title & Legal*: title type and number, plot/block/survey numbers, term and expiry, land rent, **encumbrances** (mortgages, caveats).
   * *Insurance*: insurer, policy, insured value, expiry (flagged 30 days before).
4. Attach title deeds, photos and contracts in the chatter.
5. Click **Set Operational**.

An analytic account is created automatically. Smart buttons open buildings, units, leases, tenants, work orders, equipment, open exceptions and the **Property Ledger**.

### Buildings, floors, units
* **Buildings** smart button › New. Floors and units can be entered directly on the building form.
* Each **unit** has a type, area and unit of measure, *Rentable* flag (untick for common areas), *Expected Monthly Rent* (market rent), service-charge basis and meters.
* *Occupancy (physical)* (Vacant / Occupied / Owner Occupied / Unavailable) is separate from *Rental Status* (Available / Reserved / Let), which is derived from leases. Both are visible so mismatches can be detected.

### Land and plots
Create a property with a land type (*Undeveloped Land, Residential Plots, Commercial Land*). Land cannot contain buildings. Use **Subdivide into Plots** to create N plots of a given size. Plots have survey number, title, land use, status (available, reserved, allocated, sold, leased) and value, and can be leased like units.

---

## 2. Leasing pipeline (prospect → tenant)
1. **Leasing › Prospects › New**. This is a CRM opportunity flagged *Rental Prospect*. Enter the contact, property, units of interest, budget, desired move-in and term.
2. Record the **viewing** appointment and tick *Viewing Completed*.
3. **Application Received** stamps the application date and starts screening.
4. Record **screening** results (references, income, ID verification). Set *Passed* or *Passed with Conditions*.
5. **Prepare Lease Offer** creates a draft lease with the tenant, units, offered rent, term and deposit.

## 3. Prepare and approve a lease
1. **Leasing › Leases** (or from a unit/prospect). Fill in:
   * Tenant (and joint tenants or guarantors), lease type, property, building, **units** (several units allowed).
   * Start/end dates, notice period.
   * **Rent & Billing**: base monthly rent, currency, billing frequency (monthly / quarterly / semi-annual / annual), calendar or anniversary periods, days invoiced in advance, payment terms, fiscal position, rent-free period, deposit required, service-charge and utility obligations.
   * **Escalations**: add contractual escalations (percentage, fixed increase or new amount) or use *Generate 5% annual escalations*.
   * **Other contractual charges** (monthly amounts): parking, marketing levy, fixed utility charge, other fees.
   * **Turnover rent** (commercial): rate, breakpoint, and *Greater of* (minimum guaranteed rent) or *Additional* mode.
   * **Clauses**: renewal terms, termination conditions, break clause.
2. **Submit for Approval**. The approver (by default a Portfolio Manager other than you) gets an activity and clicks **Approve** or **Reject** (with a reason). Contractual escalations are approved with the lease.
3. Attach the signed agreement in the chatter and click **Mark as Signed**.
4. **Activate (Move-in)**: units become *Occupied / Let*, the deposit record is created, and the **billing schedule** is generated.

After submission, rent, dates, units and charges are locked. Change them through **Amend** (rental change, term extension, concession, new charge), which requires approval with segregation of duties. Overlapping leases on the same unit are refused unless the unit is authorised for multi-occupancy.

**Renew**: creates a new draft lease starting the day after the current end. When it is activated, the old lease becomes *Renewed*.
**Terminate**: choose the date, type and reason. Future unbilled obligations are removed. Posted invoices are **never changed**: invoices covering days after termination are listed as exceptions for credit-note review. Tick *Tenant has moved out* to vacate the units, or later use **Record Move-out**.

## 4. Generate rent invoices
* Automatic: the daily billing run creates invoices for all obligations whose invoice date has arrived.
* Manual: **Finance › Run Billing** (choose a date and optionally leases), or **Invoice Due Charges** on a lease, or select lines in **Finance › Rental Billing** › *Action › Create Invoices*.

How amounts are computed (visible in the *Calculation* column of the schedule):
* Monthly amounts are pro-rated by day for partial months (e.g. a lease starting 15 January bills 17/31 of a month).
* Escalations apply from their effective date. Rent-free periods give zero rent (and zero charges if ticked).
* Each obligation (lease × charge × period) exists once (database constraint) and is locked while invoicing. **Running billing twice never creates duplicates.**
* Invoices are native customer invoices with property/building analytic distribution, in **draft** unless *Auto-post* is enabled. Cancelling a draft invoice releases the obligation, and the next run bills it again, once.

Turnover rent: **Finance › Turnover Reports › New**, enter verified gross sales for the period, then **Verify & Calculate** (the formula and inputs are stored on the report), then **Create Invoice**.

## 5. Payments, reconciliation and arrears
* Register payments on invoices (*Pay*) or reconcile bank statements in **Accounting**, as usual. The module adds no parallel payment records.
* Advance payments and overpayments stay as unallocated credits and are flagged after the grace period (`payment_unallocated`).
* **Finance › Tenant Accounts**: ageing pivot (Current, 1-30, 31-60, 61-90, 90+, Disputed, unallocated credits) by tenant, property, building, owner, manager or company.
* **Disputes**: on the invoice (*Real Estate* tab) set *Dispute* = Disputed, or the tenant raises a billing dispute in the portal. Disputed amounts are excluded from overdue buckets and from reminders.
* **Collections**: cases open automatically after the configured days overdue (or manually). Use *Send Reminder*, record **promises to pay / arrangement instalments** (kept or broken is checked against actual receipts), *Escalate*, *Legal / Notice*, and *Record Management Review*.
* **Tenant statement**: Contact › Real Estate tab › *Print Tenant Statement*, or the tenant downloads it from the portal.

## 6. Security deposits
1. On activation a deposit record is created. **Issue Deposit Invoice**: the line is posted to the *Tenant Deposit Liability* account, not income.
2. When paid, the status becomes **Held**.
3. At the end of the lease: add **deductions** (with evidence), then **Request Refund**. A Finance Manager (not you) approves it.
4. **Create Refund Credit Note**: Dr Liability (full amount) / Cr Deduction Income / Cr Receivable (net). Register the outbound payment from the credit note, or reconcile it against outstanding rent.

## 7. Service charges
1. **Finance › Service Charges › New**: building (or whole property), period, allocation basis (area / equal / custom %).
2. Budget lines: cost categories with their **expense accounts** and amounts.
3. **Compute Allocation**: shares per unit. Vacant units keep their share, which is a landlord cost.
4. **Submit** for approval (Finance Manager), then **Apply to Leases**. A monthly service charge is added to each lease with a service-charge obligation, and billing picks it up.
5. During the year the form shows actual expenditure (posted lines on the mapped accounts allocated to the building), billed and collected amounts, and the variance.
6. **Year-end Reconciliation** creates **draft** balancing invoices or credit notes per tenant (actual share − billed). **Print Reconciliation** produces the statement.

## 8. Utilities
Register **meters** (unit/tenant, common area or main; electricity, water, generator fuel, solar, gas, waste, equipment run-hours) with a **tariff**. Enter **readings**: the previous reading, consumption and cost are computed, and the tenant is found from the lease active on the reading date. Readings for leases with *Utility Consumption Recharged* (and not prepaid) are billable: select them and run *Action › Bill Readings*. Consumption trends and building comparisons are in the graph and pivot views.

## 9. Tenant experience
* Tenants use the portal: **My Leases** (details, signed agreement, renewal request), **Invoices** (Odoo standard, online payment if a payment provider is configured), **Account Statement** (PDF), **Requests & Complaints** (maintenance, complaint, billing dispute, renewal, document, enquiry, feedback, with attachments), announcements, and confirmation and rating of completed work.
* Staff handle requests in **Leasing › Tenant Experience › Requests & Complaints**: *Create Work Order*, *Prepare Renewal*, *Resolve* or *Reject* with a resolution note.
* **Shared Building Issues**: complaints of the same category in the same building from several tenants are grouped automatically. Resolving the issue resolves and notifies all linked complaints. The *Building Complaint Analysis* pivot shows complaints by building and category.
* **Announcements**: publish to the portal and/or email all tenants of the selected properties or buildings.

## 10. Maintenance
**Equipment register** (Maintenance › Equipment Register): extends Odoo Maintenance equipment with property, building, floor, unit, category, manufacturer, serial, installation date, criticality, condition, warranty, service agreement, replacement cost, useful life and a link to the accounting fixed asset. The *Building Asset* tab shows maintenance history, lifetime and 12-month cost, failures, downtime, remaining life and the **replacement recommendation** (repair / inspect / review for replacement, with reasons). It is decision support only.

**Work order flow** (Maintenance › Work Orders):
1. A request is logged by staff, tenant portal, a complaint, or a preventive plan (**New Request**).
2. **Triage**: set category, priority, target date, technician or contractor.
3. For contractor work: **Request Quotations** creates one native RFQ per contractor. Enter their prices, compare them (*Quotations / POs* smart button) and **Select** one. The proposed cost is set from it.
4. **Submit Budget for Approval**. The applicable rule tier decides who approves.
5. **Confirm Selected PO** (blocked until the budget is approved). The other RFQs are cancelled.
6. **Start Work**, then *Pending Parts / Contractor* or *Resume*.
7. Vendor bill: *Create Bill* on the PO (linked to the work order and analytically allocated), or *Direct Vendor Bill* (flagged if POs are required). Bills above the approved budget are blocked (finance-manager override is logged).
8. **Complete**: the completion report is required. If actual cost exceeds the approved budget plus tolerance, use **Request Supplementary Budget** first.
9. **Request Tenant Confirmation**: the tenant confirms and rates the work in the portal, then **Close**.

*Emergency Start* lets work begin before approval. A maintenance manager (not the initiator) must accept or reject it afterwards, and unreviewed emergencies are flagged.

**Preventive maintenance**: plans by calendar interval (or run-hour meter readings) create work orders *lead days* before the due date, with no duplicates. *Compliance %* = completed on or before the scheduled date.

## 11. Vendors and contractors
**Vendors › Vendor Register**: contractor flag, service categories, BRELA registration, TIN, licences (CRB, EWURA…) with expiry, insurance, contracts. *Compliant* turns false when a licence or insurance has expired, and open work assigned to a non-compliant contractor is flagged. **Performance**: jobs assigned/completed, on-time %, average days, repeat faults, poor ratings, average rating, approved vs actual spend. **Contracts**: maintenance agreements and SLAs with expiry reminders.

Contractors with portal access see **Assigned Jobs**, can start and complete work, and can upload evidence and notes.

## 12. Revenue assurance & controls
**Finance › Revenue Assurance** lists exceptions with severity, amount at risk, responsible user and status (*New → Investigating → Resolved / Dismissed*). Checks:

*Revenue:* occupied unit without lease · billing due but not invoiced · escalation date passed without approval · duplicate rent invoice · expired lease still occupied · recharged utility not billed · service charge missing · unallocated tenant receipt · unapproved credit note / manual receivable adjustment · refund paid without approval · deposit not received · unsigned active lease · invoice after termination · billing failure · negative billing.
*Financial:* bills above approved amount · unapproved maintenance spend · contractor bill without PO · duplicate vendor bills · missing / wrong property analytic allocation · service-charge overrun · service charges not reconciled · control overrides.
*Operational:* emergency work not reviewed · non-compliant contractor · insurance expiry.

Exceptions recommend an investigation; they never change accounting entries. When the condition disappears (e.g. the lease is created), the next run **auto-resolves** the exception with an audit note. Manual resolution or dismissal requires a note. Run checks on demand from the dashboard (*Run control checks*) or **Configuration › Revenue Assurance Controls**.

## 13. Dashboard and reports
**Dashboard**: filters for period, company, portfolio, property, building, type, region and manager. KPI cards (hover a card for its definition; click to drill down): properties, rentable units, lettable area, occupied/vacant, physical / area-weighted / economic occupancy, property value, rent invoiced, collected & allocated, total receipts, collection efficiency, outstanding (and disputed), service-charge position, NOI, opex, gross/net yield, maintenance expenditure, capex variance, expiring leases, overdue work orders, open exceptions. Also an ageing summary, top arrears, top exceptions, expiring leases and the **property comparison** table (NOI per m², net yield, tenant concentration, average vacancy).

**Reporting** menus open the report wizard (choose report, period and properties, then **PDF** or **Excel**): Property Register, Ownership & Valuation, Unit Register / Occupancy & Vacancy, Rent Roll, Lease Expiry & Renewal, Rental Escalations, Rental Rate Comparison, Rental Income by Charge Type, Tenant Ageing, Collection Efficiency, Property Income Statement (NOI), Property Performance Comparison, Security Deposit Liability, Service-Charge Budget vs Actual, Work Orders & Maintenance Expenditure, Preventive Maintenance Compliance, Equipment Condition & Replacement, Contractor Performance, Investment Appraisal Comparison. Every report prints its period, scope, author and calculation definitions. Single-record PDFs: Lease Summary, Work Order Sheet, Tenant Statement, Service-Charge Reconciliation, Investment Appraisal.

**Finance › Property Profitability** is a pivot of posted revenue and expense lines by property and account.

## 14. Investments
**Investments › Investment Opportunities › New**: enter costs, financing, rent, occupancy, opex, maintenance, capex reserve, growth, discount rate, holding period, exit cap rate and selling costs. The *Appraisal* tab shows the projected cash flow, NPV, project and equity IRR, ROI, payback, NOI, gross/net yield, DSCR and break-even occupancy (all labelled as projections, with formulas in the documentation).
* **Simulate Scenario** creates a copy for what-if analysis (it cannot be submitted).
* **Submit** for approval (Director). Approved assumptions are locked. **Create Authorised Revision** creates version n+1, and the approved case is kept (marked *Superseded* when the revision is approved).
* Link the **Resulting Property** and use *Actual vs Projected* (choose the year) to compare revenue, opex, maintenance, NOI, occupancy and investment cost with the projection, with material variances listed.
