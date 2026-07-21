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
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace("$", "")
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
        "%b %d %Y",
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
def root():
    return {"status": "ok"}


@app.post("/extract")
def extract(req: InvoiceRequest):
    text = req.invoice_text

    invoice_no = search(
        [
            r"Invoice\s*(?:No|Number|#)?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
            r"Ref(?:erence)?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
            r"Invoice\s*ID\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
            r"Bill\s*No\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        ],
        text,
    )

    date = parse_date(
        search(
            [
                r"Date\s*[:\-]?\s*(.+)",
                r"Issued\s*[:\-]?\s*(.+)",
                r"Invoice\s*Date\s*[:\-]?\s*(.+)",
                r"Bill\s*Date\s*[:\-]?\s*(.+)",
            ],
            text,
        )
    )

    vendor = search(
        [
            r"Vendor\s*[:\-]?\s*(.+)",
            r"Supplier\s*[:\-]?\s*(.+)",
            r"Company\s*[:\-]?\s*(.+)",
            r"Seller\s*[:\-]?\s*(.+)",
            r"From\s*[:\-]?\s*(.+)",
            r"Client\s*[:\-]?\s*(.+)",
        ],
        text,
    )

    amount = parse_amount(
        search(
            [
                r"Subtotal.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Sub\s*Total.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Amount\s*Before\s*Tax.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Before\s*Tax.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Taxable\s*Value.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Net\s*Amount.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Base\s*Amount.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Line\s*Total.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Amount\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Value\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
            ],
            text,
        )
    )

    tax = parse_amount(
        search(
            [
                r"IGST.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"CGST.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"SGST.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"GST.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"Tax\s*[:\-]?\s*(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
                r"VAT.*?(?:₹|Rs\.?|INR|\$)?\s*([\d,]+(?:\.\d+)?)",
            ],
            text,
        )
    )

    currency = search(
        [
            r"Currency\s*[:\-]?\s*([A-Z]{3})",
        ],
        text,
    )

    if currency is None:
        if re.search(r"₹|Rs\.?|INR", text, re.IGNORECASE):
            currency = "INR"
        elif "$" in text:
            currency = "USD"
        elif "€" in text or "EUR" in text:
            currency = "EUR"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }