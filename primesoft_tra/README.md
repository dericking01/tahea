# Primesoft TRA EFD Integration — Odoo 18

## Overview
Issues Tanzania Revenue Authority (TRA) Electronic Fiscal Device (EFD) receipts from
**customer invoices**, from **Point of Sale orders**, or from both, via the
**Zalongwa WebSHOP VEFD API v11**. Odoo talks to Zalongwa, and Zalongwa submits to TRA.

This module replaces `zalongwa_tra_efd` (invoices) and `tra_vfd_pos` (POS). It is meant for
fresh installs: do not install it next to either of them.

Credit notes and POS refunds are not sent, because the API has no way to send them.

---

## Features

| Feature | Description |
|---|---|
| API Authentication | Bearer token, refreshed automatically |
| Invoice receipts | From confirmed customer invoices, manually or automatically |
| POS receipts | Sent when the order is paid, with the cashier choosing TRA Fiscal or Standard |
| QR Code | Printed on the invoice and on the POS fiscal receipt |
| Receipt List | All TRA receipts, from invoices and POS, including failed attempts |
| PDF Report | Printable TRA receipt with QR code |
| Z-Reports | Sync and view daily Z-Reports |
| Dashboard | What needs attention, totals, trend, Odoo compared with TRA |
| Company Profile | Name, address, VRN, TIN and EFD serial fetched by Test Connection |

---

## Installation
```bash
pip install qrcode[pil] requests
```
Add the module to the addons path, update the apps list and install
**Primesoft TRA EFD Integration**. It depends on Invoicing and Point of Sale.

---

## Configuration

### API settings
Go to **TRA EFD → Configuration → EFD API Settings**, enter the live **Client ID** and
**Client Secret**, then click **Test Connection**. The module installs with placeholder
credentials, so nothing can be sent until real ones are entered. Whether a receipt is live
or demo is decided by the credentials and shown on each receipt.

### Where receipts are issued
On the same form, under **Receipt Settings**:

| Setting | Effect |
|---|---|
| **Use on Invoices** | Shows the Generate TRA Receipt button on customer invoices |
| **Generate Receipts Automatically** | Issues the receipt as soon as an invoice is confirmed |
| **Use on Point of Sale** | Lets Point of Sale orders be sent to TRA |

Untick the one a company does not need: invoices only, POS only, or both.

**Tax Code for Lines Without Tax** is used for lines that carry no tax, for example when the
company is not VAT registered. Leave it empty to refuse such lines.

### Point of Sale
In each Point of Sale's settings, under **TRA Receipt**:

- **Enable TRA Receipts**: switch TRA off for one Point of Sale.
- **Allow Standard Receipt**: untick to fiscalise every sale.
- **Default Receipt Type**: the type pre-selected on the payment screen.

On each payment method, set **TRA Payment Type** (Cash, Cheque, Credit card, E-money,
Invoice). When empty it is guessed from the method type and name.

### Taxes
Set **TRA Tax Code** on each tax under **Accounting → Configuration → Taxes**. Without it,
an 18% tax is sent as Standard and a 0% tax as Zero Rated, so **exempt and special relief
0% taxes must have the code set**. A line with any other rate is refused.

### Customers
Enter the customer's **TIN** and **VRN** on the customer form, under Tax ID. Contacts use
their company's values. The TIN must be 9 digits and is sent to TRA. The VRN is stored for
reference only, because the API has no field for it.

A customer without a TIN falls back to the Tax ID when that is exactly 9 digits. Otherwise
the customer is identified by telephone. Mobile numbers are normalised to `0XXXXXXXXX`.

---

## Access

| Group | Can |
|---|---|
| Accounting: Read-only | View the menu, dashboard, receipts, Z-Reports, invoice TRA tab and customer TIN/VRN |
| Accounting: Invoicing and above | Also generate receipts, check status, refresh TRA responses and sync |
| Accounting: Administrator | Also configure the API and use Mark as Failed |
| Point of Sale: Administrator | Everything above for POS orders, including the configuration |
| Point of Sale: User | Sell and print TRA fiscal receipts in the POS |

Automatic generation runs whoever confirms the invoice or validates the POS order.

---

## Invoices

1. Confirm a customer invoice and click **Generate TRA Receipt**, or enable automatic generation.
   A dialog shows exactly what TRA will receive. Nothing is sent until **Confirm and Send
   to TRA** is clicked. Automatic generation has no such check.
2. The receipt appears in the **TRA EFD** tab of the invoice, and the QR code prints on the invoice.
3. **Failed**: the reason is shown, and the button stays available to try again.
4. **Pending**: the API did not answer, so TRA may have accepted the invoice. Retrying is blocked.
   Click **Check TRA Status**. If no receipt is found, confirm on the WebSHOP portal, then a
   manager can click **Mark as Failed** on the receipt to allow a retry.

Invoices with a successful or pending receipt cannot be reset to draft or cancelled.

## Point of Sale

1. On the payment screen the cashier chooses **TRA Fiscal** or **Standard**, and can type the
   customer's 9-digit TIN. The TIN is pre-filled from the customer when it has one.
2. When the order is validated it is sent to TRA, after the order is saved, and the fiscal
   receipt prints with the receipt number, Z number, verification code and QR code.
3. If TRA could not be reached the receipt prints with `PENDING` and the reason. A job retries
   failed orders every 15 minutes for two days. A manager can also use **Send to TRA** in the
   **TRA EFD** tab of the order.
4. If the API did not answer, the order is **Pending** and is never re-sent blindly. The same
   job, or **Check TRA Status** on the order, asks the API whether the receipt exists.

Rules to know:

- **Invoiced POS orders** get one receipt, from the POS order. Their invoice shows that
  receipt and its QR code, and cannot be sent to TRA a second time.
- **Refunds** always print the standard receipt and are not sent.
- **Discount and reward lines** are negative, which TRA does not accept. Their amount is
  spread over the items they reduce, so the receipt total matches the order total.
- The order is sent under its order reference with every character other than letters and
  digits replaced by `-`, for example `Shop-0001`.
- A POS receipt opened before the order reached the server (offline) cannot show TRA data.

### TRA response
A receipt can be issued and still be rejected by TRA afterwards. An hourly job, the
**Refresh TRA Response** button and the dashboard's **Sync with TRA** button read TRA's response.

- **Confirmed**: response code `0`.
- **Needs Action**: any other code. An invoice shows a red banner and its issuer gets a to-do;
  POS receipts appear on the dashboard. The API has no re-submit call, so nothing is re-sent
  automatically. Check with Zalongwa, then a manager can click **Mark as Failed** on the
  receipt to allow a new one.

### Dashboard
**TRA EFD → Dashboard** shows what needs attention, today's and this month's live totals, a
14-day sales trend, totals by tax code, Odoo compared with TRA (the totals of the EFD as
reported by WebSHOP), and EFD status. Cards and bars open the matching records. Demo receipts
are excluded from the totals. Set **TRA Go-Live Date** in EFD API Settings so older invoices
and POS orders are not counted as missing a receipt.

### Amounts
Amounts are sent in TZS. Foreign currency documents are converted at the document date rate.

### Z-Reports
Use **TRA EFD → Reports → Sync Z-Reports**.

---

## API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `POST /login` | Authenticate and get a Bearer token |
| `POST /generatereceipt` | Generate an EFD receipt |
| `GET /invoiceno/{n}` | Check a pending receipt and read TRA's response (Odoo sends `/` in references as `-`) |
| `GET /dashboard` | WebSHOP totals for the dashboard comparison |
| `GET /zreport` | Z-Reports |
| `GET /companyprofile` | Company info |

The API can report errors with HTTP 200, so responses are checked by content. `/invoiceno`
answers an unknown invoice with HTTP 200 and a `receiptData` whose values are all null.

---

## Codes

| Item tax code | Meaning |
|---|---|
| 1 | Standard Rate (18%) |
| 2 | Special Rate |
| 3 | Zero Rated |
| 4 | Special Relief |
| 5 | Exempted |

Payment types: `CASH`, `INVOICE`, `CHEQUE`, `CCARD`, `EMONEY`.

---

## Support
**Primesoft Technologies Limited** — https://www.primesoft.co.tz

API provider: **Zalongwa Technologies Limited**, info@zalongwa.com
