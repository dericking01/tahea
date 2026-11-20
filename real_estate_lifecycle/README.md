# Real Estate Lifecycle & Performance Management (RE-LPM)

Odoo 18 Enterprise addon `real_estate_lifecycle`: an integrated real-estate operating environment for property owners, managers, developers and investors, initially for Tanzania / East Africa.

It connects the property register, leasing, rental billing, deposits, service charges, utilities, collections, maintenance, contractors and investment appraisal **to native Odoo Accounting, Purchase, CRM and Maintenance**. No separate accounting engine exists. Every financial transaction is a standard Odoo invoice, credit note, payment, vendor bill or purchase order, and property profitability comes from analytic accounting.

| Document | Content |
|---|---|
| [doc/INSTALLATION.md](doc/INSTALLATION.md) | Requirements, installation, upgrade, running the tests |
| [doc/CONFIGURATION.md](doc/CONFIGURATION.md) | Accounting setup, products/taxes, approval rules, controls, roles |
| [doc/USER_MANUAL.md](doc/USER_MANUAL.md) | Step-by-step operational workflows |
| [doc/FUNCTIONAL_REQUIREMENTS.md](doc/FUNCTIONAL_REQUIREMENTS.md) | Architecture, data model, business rules, KPI definitions |
| [doc/STATUS_AND_BACKLOG.md](doc/STATUS_AND_BACKLOG.md) | What is built and tested, what is deferred, limitations, integration requirements |

## Quick start

```bash
# addon lives in the custom addons path (/mnt/extra-addons in the docker setup)
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d <db> -i real_estate_lifecycle --stop-after-init
# run the acceptance test-suite on a throw-away database
docker exec odoo18-odoo-1 odoo -c /etc/odoo/odoo.conf -d re_lpm_test -i real_estate_lifecycle \
    --test-enable --test-tags /real_estate_lifecycle --stop-after-init --http-port 8099
```

Then go to **Real Estate › Configuration › Settings**, set the *Tenant Deposit Liability Account* and review the invoice products and taxes. See [CONFIGURATION](doc/CONFIGURATION.md).
