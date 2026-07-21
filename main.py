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


def search(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def parse_amount(value):
    if value is None:
        return None

    value = (
        value.replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace("USD", "")
        .strip()
    )

    try:
        return float(value)
    except:
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


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    invoice_no = search([
        r"Invoice\s*(?:No|Number|#)?\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
        r"Ref(?:erence)?\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
        r"Bill\s*No\s*[:\-]?\s*([A-Za-z0-9\-/]+)"
    ], text)

    date = parse_date(search([
        r"Date\s*[:\-]?\s*(.+)",
        r"Issued\s*[:\-]?\s*(.+)",
        r"Invoice\s*Date\s*[:\-]?\s*(.+)"
    ], text))

    vendor = search([
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Company\s*[:\-]?\s*(.+)",
        r"Client\s*[:\-]?\s*(.+)"
    ], text)

    amount = parse_amount(search([
        r"Subtotal.*?([\d,]+(?:\.\d+)?)",
        r"Sub\s*Total.*?([\d,]+(?:\.\d+)?)",
        r"Taxable\s*Value.*?([\d,]+(?:\.\d+)?)",
        r"Base\s*Amount.*?([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount.*?([\d,]+(?:\.\d+)?)"
    ], text))

    tax = parse_amount(search([
        r"GST.*?([\d,]+(?:\.\d+)?)",
        r"IGST.*?([\d,]+(?:\.\d+)?)",
        r"CGST.*?([\d,]+(?:\.\d+)?)",
        r"SGST.*?([\d,]+(?:\.\d+)?)",
        r"Tax.*?([\d,]+(?:\.\d+)?)"
    ], text))

    total = parse_amount(search([
        r"Grand\s*Total.*?([\d,]+(?:\.\d+)?)",
        r"Total\s*Due.*?([\d,]+(?:\.\d+)?)",
        r"TOTAL.*?([\d,]+(?:\.\d+)?)",
        r"Total.*?([\d,]+(?:\.\d+)?)"
    ], text))

    # Better fallback: only extract currency amounts
    if amount is None:

        money_strings = re.findall(
            r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )

        money = sorted(
            {float(x.replace(",", "")) for x in money_strings}
        )

        if total is not None and tax is not None:
            candidate = round(total - tax, 2)
            for n in money:
                if abs(n - candidate) < 0.01:
                    amount = n
                    break

        if amount is None and len(money) == 3:
            # tax, subtotal, total
            amount = money[1]

        if amount is None and len(money) == 2:
            # subtotal, total
            amount = min(money)

    currency = search([
        r"Currency\s*[:\-]?\s*([A-Z]{3})"
    ], text)

    if currency is None:
        if re.search(r"₹|Rs\.?|INR", text, re.I):
            currency = "INR"
        elif "$" in text:
            currency = "USD"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }