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
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def parse_amount(s):
    if s is None:
        return None
    s = re.sub(r"[₹$,]", "", s)
    s = re.sub(r"\b(Rs\.?|INR|USD)\b", "", s, flags=re.I)
    s = s.strip()

    try:
        return float(s)
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

    for f in formats:
        try:
            return datetime.strptime(date_str, f).strftime("%Y-%m-%d")
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
        r"Company\s*[:\-]?\s*(.+)",
        r"Client\s*[:\-]?\s*(.+)"
    ], text)

    amount = parse_amount(search([
        r"Subtotal.*?([\d,]+\.\d+|[\d,]+)",
        r"Sub\s*Total.*?([\d,]+\.\d+|[\d,]+)",
        r"Taxable\s*Value.*?([\d,]+\.\d+|[\d,]+)",
        r"Net\s*Amount.*?([\d,]+\.\d+|[\d,]+)",
        r"Base\s*Amount.*?([\d,]+\.\d+|[\d,]+)"
    ], text))

    tax = parse_amount(search([
        r"GST.*?([\d,]+\.\d+|[\d,]+)",
        r"IGST.*?([\d,]+\.\d+|[\d,]+)",
        r"CGST.*?([\d,]+\.\d+|[\d,]+)",
        r"SGST.*?([\d,]+\.\d+|[\d,]+)",
        r"Tax.*?([\d,]+\.\d+|[\d,]+)"
    ], text))

    total = parse_amount(search([
        r"Grand\s*Total.*?([\d,]+\.\d+|[\d,]+)",
        r"Total\s*Due.*?([\d,]+\.\d+|[\d,]+)",
        r"TOTAL.*?([\d,]+\.\d+|[\d,]+)",
        r"Total.*?([\d,]+\.\d+|[\d,]+)"
    ], text))

    # Fallback inference
    if amount is None:
        nums = [
            float(x.replace(",", ""))
            for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)
        ]

        nums = sorted(set(nums))

        # Try to infer subtotal from total-tax
        if total is not None and tax is not None:
            candidate = total - tax
            for n in nums:
                if abs(n - candidate) < 0.01:
                    amount = n
                    break

        # If only three money values exist, assume:
        # smallest = tax
        # middle = subtotal
        # largest = total
        if amount is None and len(nums) == 3:
            amount = nums[1]

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