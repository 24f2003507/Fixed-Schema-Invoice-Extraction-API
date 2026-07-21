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


def find(pattern, text, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_amount(value):
    if value is None:
        return None
    value = value.replace(",", "")
    try:
        return float(value)
    except:
        return None


@app.post("/extract")
def extract(req: InvoiceRequest):
    text = req.invoice_text

    invoice_no = find(r"Invoice\s*No[:\-\s]*([A-Za-z0-9\-\/]+)", text)

    vendor = find(r"Vendor[:\-\s]*(.+)", text)

    date_raw = find(r"Date[:\-\s]*(.+)", text)
    date = None
    if date_raw:
        for fmt in (
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ):
            try:
                date = datetime.strptime(date_raw.strip(), fmt).strftime("%Y-%m-%d")
                break
            except:
                pass

    amount = parse_amount(
        find(r"Subtotal[:\-\s]*Rs\.?\s*([\d,]+\.\d+)", text)
    )

    tax = parse_amount(
        find(r"(?:GST|Tax).*?Rs\.?\s*([\d,]+\.\d+)", text)
    )

    currency = "INR" if re.search(r"Rs\.?|INR|₹", text, re.I) else None

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }