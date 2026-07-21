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
    if text is None:
        return None

    text = text.replace(",", "")
    text = text.replace("₹", "")
    text = re.sub(r"\b(Rs\.?|INR|USD)\b", "", text, flags=re.I)

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
    for p in patterns:
        m = re.search(p, text, re.I | re.M)
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

    invoice_no = search([
        r"Invoice\s*(?:No|Number|#)?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        r"Ref\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        r"Reference\s*[:\-]?\s*([A-Za-z0-9\-\/]+)"
    ], text)

    date = parse_date(search([
        r"Date\s*[:\-]?\s*(.+)",
        r"Issued\s*[:\-]?\s*(.+)"
    ], text))

    vendor = search([
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Company\s*[:\-]?\s*(.+)"
    ], text)

    amount = extract_line_value(
        text,
        [
            "subtotal",
            "sub total",
            "taxable value",
            "base amount",
            "net amount"
        ]
    )

    tax = extract_line_value(
        text,
        [
            "gst",
            "igst",
            "cgst",
            "sgst",
            "vat",
            "tax"
        ]
    )

    total = extract_line_value(
        text,
        [
            "grand total",
            "total due",
            "total"
        ]
    )

    # Infer subtotal if missing
    if amount is None and total is not None and tax is not None:
        amount = round(total - tax, 2)

    # Currency
    currency = search([
        r"Currency\s*[:\-]?\s*([A-Z]{3})"
    ], text)

    if currency is None:
        if "₹" in text or "Rs" in text or "INR" in text:
            currency = "INR"
        elif "$" in text:
            currency = "USD"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }