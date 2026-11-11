# Zalongwa TRA EFD Integration — Odoo 18

## Overview
Issues Tanzania Revenue Authority (TRA) Electronic Fiscal Device (EFD) receipts for
customer invoices via the **Zalongwa WebSHOP VEFD API v11**. Odoo talks to Zalongwa,
and Zalongwa submits to TRA.

POS is out of scope. Credit notes are not supported because the API has no way to send them.

---

## Features

| Feature | Description |
|---|---|
| API Authentication | Bearer token, refreshed automatically |
| TRA Receipts | From confirmed customer invoices, manually or automatically |
| QR Code | Printed on the invoice, whichever document layout is used |
| Receipt List | All TRA receipts, including failed attempts |
| PDF Report | Printable TRA receipt with QR code |
| Z-Reports | Sync and view daily Z-Reports |
| Company Profile | VRN, TIN and EFD serial fetched by Test Connection |

---

## Installation
```bash
pip install qrcode[pil] requests
```
Add the module to the addons path, update the apps list and install **Zalongwa TRA EFD Integration**.

---

## Configuration

### API settings
Go to **TRA EFD → Configuration → EFD API Settings**, enter the live **Client ID** and
**Client Secret**, then click **Test Connection**. The module installs with placeholder
credentials, so nothing can be sent until real ones are entered. Whether a receipt is live
or demo is decided by the credentials and shown on each receipt.

**Generate Receipts Automatically**: when on, a receipt is issued when a customer invoice
is confirmed. When off (default), use the button on the invoice.

### Taxes
Set **TRA Tax Code** on each tax under **Accounting → Configuration → Taxes**. Without it,
an 18% tax is sent as Standard and a 0% tax as Zero Rated, so **exempt and special relief
0% taxes must have the code set**. A line with any other rate, or no tax, is refused.

### Customers
Enter the customer's **TIN** and **VRN** on the customer form, under Tax ID. Contacts use
their company's values. The TIN must be 9 digits and is sent to TRA. The VRN is stored for
reference only, because the API has no field for it.

A customer without a TIN falls back to the Tax ID when that is exactly 9 digits. Otherwise
the customer is identified by telephone. Mobile numbers are normalised to `0XXXXXXXXX`.

---

## Access
Only Finance users see TRA EFD, matching Odoo's Invoicing/Accounting app:

| Group | Can |
|---|---|
| Accounting: Read-only | View the menu, dashboard, receipts, Z-Reports, invoice TRA tab and customer TIN/VRN |
| Accounting: Invoicing and above | Also generate receipts, check status, refresh TRA responses and sync |
| Accounting: Administrator | Also configure the API and use Mark as Failed |

Other users see nothing of TRA EFD in Odoo, but invoices they print still carry the TRA QR code.
Automatic generation runs whoever confirms the invoice.

## Usage

1. Confirm a customer invoice and click **Generate TRA Receipt**, or enable automatic generation.
   A dialog shows exactly what TRA will receive: customer name, TIN or other ID, mobile and the
   totals in TZS, with warnings such as a missing TIN. Nothing is sent until **Confirm and Send
   to TRA** is clicked. Automatic generation has no such check.
2. The receipt appears in the **TRA EFD** tab of the invoice, and the QR code prints on the invoice.
3. **Failed**: the reason is shown, and the button stays available to try again.
4. **Pending**: the API did not answer, so TRA may have accepted the invoice. Retrying is blocked.
   Click **Check TRA Status**. If no receipt is found, confirm on the WebSHOP portal, then an
   accounting manager can click **Mark as Failed** on the receipt to allow a retry.

Invoices with a successful or pending receipt cannot be reset to draft or cancelled.

### TRA response
A receipt can be issued and still be rejected by TRA afterwards. An hourly job, the
**Refresh TRA Response** button and the dashboard's **Sync with TRA** button read TRA's response.

- **Confirmed**: response code `0`.
- **Needs Action**: any other code. The invoice shows a red banner, its salesperson gets a
  to-do, and the receipt appears on the dashboard. The API has no re-submit call, so nothing is
  re-sent automatically. Check with Zalongwa, then an accounting manager can click
  **Mark as Failed** on the receipt to allow a new one.

### Dashboard
**TRA EFD → Dashboard** shows what needs attention, today's and this month's live totals, a
14-day sales trend, totals by tax code, Odoo compared with TRA (the totals of the EFD as
reported by WebSHOP), and EFD status. Cards and
bars open the matching records. Demo receipts are excluded from the totals. Set **TRA Go-Live
Date** in EFD API Settings so older invoices are not counted as missing a receipt.

### Amounts
Amounts are sent in TZS. Foreign currency invoices are converted at the invoice date rate.

### Z-Reports
Use **TRA EFD → Reports → Sync Z-Reports**.

---

## API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `POST /login` | Authenticate and get a Bearer token |
| `POST /generatereceipt` | Generate an EFD receipt |
| `GET /invoiceno/{n}` | Check a pending receipt and read TRA's response (Odoo sends `/` in invoice numbers as `-`) |
| `GET /dashboard` | WebSHOP totals for the dashboard comparison |
| `GET /zreport` | Z-Reports |
| `GET /companyprofile` | Company info |

The API can report errors with HTTP 200, so responses are checked by content. `/invoiceno`
answers an unknown invoice with HTTP 200 and a `receiptData` whose values are all null.

---

## Item Tax Codes
| Code | Meaning |
|---|---|
| 1 | Standard Rate (18%) |
| 2 | Special Rate |
| 3 | Zero Rated |
| 4 | Special Relief |
| 5 | Exempted |

---

## Support
**Zalongwa Technologies Limited**  
Tel: +255 222 630 602 | Mobile: +255 784 313200  
Email: info@zalongwa.com | Web: http://www.zalongwa.com  
P.O. Box 70893, Dar es Salaam, Tanzania
