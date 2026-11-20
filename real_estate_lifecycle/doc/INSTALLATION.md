# Installation Guide

## 1. Requirements

| Item | Requirement |
|---|---|
| Odoo | 18.0 **Enterprise** (verified on build 18.0-20260421, docker image `odoo:18.0`) |
| PostgreSQL | 12+ (verified on the `postgres:latest` container) |
| Odoo modules (installed automatically) | `account`, `analytic`, `account_asset` (Enterprise: it pulls `account_accountant`/`account_reports`), `purchase`, `maintenance`, `crm`, `portal`, `mail` |
| Python | `xlsxwriter` (shipped with the Odoo image) |
| PDF | `wkhtmltopdf` (shipped with the Odoo image) |

The module does not modify Odoo core or any other custom module.

## 2. Install

The repository docker setup mounts `/home/odoo/odoo18/addons` at `/mnt/extra-addons`, which is already in `addons_path`.

1. Copy or keep the folder `real_estate_lifecycle` in the addons path.
2. Update the apps list (Apps › Update Apps List) and install **Real Estate Lifecycle & Performance Management**, **or** from the command line:

```bash
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d <database> -i real_estate_lifecycle --stop-after-init --http-port 8099
docker restart odoo18-odoo-1   # so the running server loads the new Python code
```

`--http-port 8099` avoids clashing with the running server when you install from the CLI.

> Install on a copy of a production database first. Installing pulls in `account_asset`, `crm`, `purchase` and `maintenance` if they are not installed yet.

### Large databases
The journal-item dimensions (`re_property_id`, `re_building_id`, `re_lease_id`) are created as columns *before* the ORM sees them, so installing on a database with millions of journal items does not trigger a recomputation of every historical line. Historical lines stay unallocated; new and modified lines are allocated from their analytic distribution.

## 3. Upgrade

```bash
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d <database> -u real_estate_lifecycle --stop-after-init --http-port 8099
docker restart odoo18-odoo-1
```

Configuration data (property types, lease types, approval rules, controls, products, sequences, crons) is `noupdate`, so your changes survive upgrades.

## 4. Demo database

```bash
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d re_lpm_demo -i real_estate_lifecycle --stop-after-init --http-port 8099
```

The demo contains three properties (apartments, a trade centre and subdivided land), tenants, three active leases (one quarterly commercial lease with turnover rent and an approved escalation), equipment, a maintenance plan, an overdue work order, contractors (one non-compliant), utilities, a CRM prospect, an investment appraisal and two water complaints forming a shared building issue. The control engine already reports realistic exceptions: an occupied unit without a lease, unbilled leases, an unsigned lease, an outstanding deposit and expiring insurance. Run **Finance › Run Billing** to generate the invoices.

## 5. Automated tests

```bash
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d re_lpm_test -i real_estate_lifecycle \
   --test-enable --test-tags /real_estate_lifecycle --stop-after-init --http-port 8099 --log-level=test
```

Expected result: `0 failed, 0 error(s) of 36 tests`. The log line `duplicate key value violates unique constraint "re_billing_schedule_obligation_uniq"` is expected: one test deliberately tries to insert a duplicate billing obligation.

## 6. Scheduled actions installed

| Cron | Frequency | Purpose |
|---|---|---|
| Lease lifecycle, expiry alerts and escalations | daily | active→expiring→expired, alerts at configured days, escalation reminders |
| Rental billing run | daily | idempotent invoice generation (draft or posted per setting) |
| Revenue assurance & control checks | daily | exception detection / auto-resolution |
| Collection cases and promises | daily | open collection cases, track promises to pay |
| Preventive maintenance scheduler | daily | create preventive work orders, overdue reminders |
| Vendor contract expiry | daily | expire contracts, reminders 60 days ahead |
