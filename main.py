import re
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


def parse_amount(text):
    if not text:
        return None

    text = text.replace(",", "")
    text = re.sub(r"[₹$€£]", "", text)
    text = re.sub(r"\b(Rs\.?|INR|USD|EUR|GBP)\b", "", text, flags=re.I)

    nums = re.findall(r"\d+(?:\.\d+)?", text)

    if not nums:
        return None

    return float(nums[-1])


def extract_line_value(text, keywords):
    for line in text.splitlines():
        lower = line.lower()

        if any(k in lower for k in keywords):
            value = parse_amount(line)
            if value is not None:
                return value

    return None


def search(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.I | re.M)
        if m:
            return m.group(1).strip()
    return None


def parse_date(date_str):
    if not date_str:
        return None

    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            pass

    return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    # -----------------------------
    # Invoice Number
    # -----------------------------
    invoice_no = search([
        r"Invoice\s*No\.?\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        r"Invoice\s*Number\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        r"Invoice\s*#\s*([A-Za-z0-9/-]+)",
        r"Bill\s*No\.?\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        r"Ref(?:erence)?\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        r"Inv\.?\s*[:#-]?\s*([A-Za-z0-9/-]+)",
    ], text)

    if invoice_no in ("Invoice", "No", "Number"):
        invoice_no = None

    if invoice_no is None:
        m = re.search(r"\b[A-Z]{1,6}-\d{2,}\b", text)
        if m:
            invoice_no = m.group(0)

    # -----------------------------
    # Date
    # -----------------------------
    raw_date = search([
        r"Date\s*[:\-]?\s*(.+)",
        r"Issued\s*[:\-]?\s*(.+)",
        r"Invoice\s*Date\s*[:\-]?\s*(.+)",
        r"Bill\s*Date\s*[:\-]?\s*(.+)",
    ], text)

    date = parse_date(raw_date)

    if date is None:
        m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if m:
            date = m.group(0)

    # -----------------------------
    # Vendor
    # -----------------------------
    vendor = search([
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Company\s*[:\-]?\s*(.+)",
        r"From\s*[:\-]?\s*(.+)",
    ], text)

    # -----------------------------
    # Amount
    # -----------------------------
    amount = extract_line_value(text, [
        "subtotal",
        "sub total",
        "taxable value",
        "net amount",
        "base amount",
        "amount before tax",
        "pre-tax"
    ])

    # -----------------------------
    # Tax
    # -----------------------------
    tax = extract_line_value(text, [
        "igst",
        "cgst",
        "sgst",
        "gst",
        "vat",
        "sales tax",
        "tax"
    ])

    # -----------------------------
    # Total
    # -----------------------------
    total = extract_line_value(text, [
        "grand total",
        "total due",
        "invoice total",
        "amount due",
        "total"
    ])

    # Infer subtotal if missing
    if amount is None and total is not None and tax is not None:
        amount = round(total - tax, 2)

    # Last-resort inference from money values
    if amount is None:
        values = []

        for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
            try:
                v = float(x.replace(",", ""))
                if v > 100:
                    values.append(v)
            except:
                pass

        values = sorted(set(values))

        if len(values) >= 3:
            amount = values[-2]

    # -----------------------------
    # Currency
    # -----------------------------
    currency = search([
        r"Currency\s*[:\-]?\s*([A-Z]{3})"
    ], text)

    if currency is None:
        if "₹" in text or "Rs" in text or "INR" in text:
            currency = "INR"
        elif "$" in text:
            currency = "USD"
        elif "EUR" in text or "€" in text:
            currency = "EUR"
        elif "GBP" in text or "£" in text:
            currency = "GBP"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }