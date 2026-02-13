"""
Centralized configuration module for EZ Expense application.

This module provides a single source of truth for configuration values
that need to be shared across different components of the application.
"""

import os

from dotenv import load_dotenv

from utils import find_available_port

# Load environment variables
load_dotenv(override=True)

# Debug and development settings
IMPORT_EXPENSE_MOCK = os.getenv("IMPORT_EXPENSE_MOCK", "False").lower() == "true"
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
DEBUG_LOG_TARGET = os.getenv("DEBUG_LOG_TARGET", "ez-expense.log").strip('"')
DEBUG_LOG_TARGET_FRONT_END = os.getenv("DEBUG_LOG_TARGET_FRONT_END", "ez-expense-fe.log").strip('"')

# Azure OpenAI
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", None)
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
INVOICE_DETAILS_EXTRACTOR_MODEL_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

# Local model settings
LOCAL_MODEL_DIR = os.getenv("EZ_EXPENSE_MODEL_DIR", os.path.expanduser("~/.ez-expense/models"))

# Date format configuration
DATE_FORMAT = os.getenv("DATE_FORMAT", "MM/DD/YYYY").upper()

# Port configurations
BROWSER = os.getenv("EZ_EXPENSE_BROWSER", "edge")

# Get preferred ports from environment
_PREFERRED_BROWSER_PORT = int(os.getenv("EZ_EXPENSE_BROWSER_PORT", 9222))
_PREFERRED_FRONTEND_PORT = int(os.getenv("EZ_EXPENSE_FRONTEND_PORT", 5001))

# Assign actual ports (will use preferred if available, or find alternatives)
BROWSER_PORT = find_available_port(_PREFERRED_BROWSER_PORT)
FRONTEND_PORT = find_available_port(_PREFERRED_FRONTEND_PORT)

# Log port assignments if they changed
if BROWSER_PORT != _PREFERRED_BROWSER_PORT:
    print(
        f"⚠️  Browser port {_PREFERRED_BROWSER_PORT} was occupied, using port {BROWSER_PORT} instead"
    )
if FRONTEND_PORT != _PREFERRED_FRONTEND_PORT:
    print(
        f"⚠️  Frontend port {_PREFERRED_FRONTEND_PORT} was occupied, using port {FRONTEND_PORT} instead"
    )

# Application URLs
EXPENSE_APP_URL = "myexpense.operations.dynamics.com"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

# Flask configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB max file size
ALLOWED_EXTENSIONS = {"csv", "pdf", "png", "jpg", "jpeg", "gif"}

EXPENSE_CATEGORIES = [
    "Admin Services - Misc.",
    "Airfare",
    "Airline Fees",
    "Broadband - Home",
    "Car | Fuel & Maintenance",
    "Car | Mileage",
    "Car Rental",
    "Catering",
    "Computer Services",
    "Courier/Shipping/Freight",
    "Dues",
    "Empl Benefits-Sport/Social/Gym",
    "Employee Benefits - Misc",
    "Employee Gifts <£50",
    "Employee Morale",
    "Entertainment - external",
    "Event Incidentals",
    "FX Diff & Bank Fees",
    "Gift | external",
    "Government Official",
    "Ground Transportation",
    "Hardware (Supplies General)",
    "Hardware Dev (Prod Dev-Other)",
    "Hotel",
    "Infrastructure & Ops Support",
    "Internet/Online Fees - Travel",
    "Lab Reference Material",
    "Lab Supplies",
    "Meals | Employee Morale",
    "Meals | Employee Travel",
    "Membership & Dues (Advertising",
    "Mobile/Cellular Phone",
    "Office Equipment/Hardware",
    "Office Supplies",
    "Other Product Development",
    "Parking",
    "Passport/Visa Fees",
    "Postage",
    "Prof Learning (EE dev & train)",
    "Professional Subscriptions",
    "Recruiting",
    "Relocation Expenses",
    "Seminar/Course Fees",
    "T&E Other",
    "Telecommunications-Other",
    "Telephone/Fax",
    "Tips/Gratuities",
    "Tolls/Road Charges",
    "Tuition/Training Reimbursement",
    "Volunteer Event Items - Non US",
    "Volunteer Event Items - US",
]

# Map of common currency symbols to their ISO codes (used by local LLM postprocessing)
CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "¥": "JPY",
    "₹": "INR",
    "₩": "KRW",
    "₽": "RUB",
    "₺": "TRY",
    "R$": "BRL",
    "CHF": "CHF",
    "kr": "SEK",
    "zł": "PLN",
}

CURRENCY_CODES = [
    "AFN",
    "ALL",
    "AMD",
    "AOA",
    "ARS",
    "AUD",
    "AWG",
    "AZN",
    "DZD",
    "BAM",
    "BBD",
    "BDT",
    "BGN",
    "BHD",
    "BIF",
    "BMD",
    "BND",
    "BOB",
    "BRL",
    "BSD",
    "BTC",
    "BTN",
    "BWP",
    "BYR",
    "BZD",
    "GBP",
    "CAD",
    "CDF",
    "CLF",
    "CLP",
    "CNY",
    "COP",
    "CRC",
    "CUC",
    "CUP",
    "CVE",
    "CZK",
    "HRK",
    "KHR",
    "KMF",
    "KYD",
    "XAF",
    "XOF",
    "XPF",
    "DJF",
    "DKK",
    "DOP",
    "EGP",
    "ERN",
    "ETB",
    "EUR",
    "XCD",
    "FJD",
    "FKP",
    "GEL",
    "GGP",
    "GHS",
    "GIP",
    "GMD",
    "GNF",
    "GTQ",
    "GYD",
    "XAU",
    "HKD",
    "HNL",
    "HTG",
    "HUF",
    "IDR",
    "ILS",
    "INR",
    "IQD",
    "IRR",
    "ISK",
    "JEP",
    "JMD",
    "JOD",
    "JPY",
    "KES",
    "KGS",
    "KWD",
    "KZT",
    "LAK",
    "LBP",
    "LRD",
    "LSL",
    "LTL",
    "LVL",
    "LYD",
    "IMP",
    "MAD",
    "MDL",
    "MGA",
    "MKD",
    "MMK",
    "MNT",
    "MOP",
    "MRO",
    "MUR",
    "MVR",
    "MWK",
    "MXN",
    "MYR",
    "MZN",
    "ANG",
    "BYN",
    "KPW",
    "NAD",
    "NGN",
    "NIO",
    "NOK",
    "NPR",
    "NZD",
    "TWD",
    "OMR",
    "PAB",
    "PEN",
    "PGK",
    "PHP",
    "PKR",
    "PLN",
    "PYG",
    "QAR",
    "RON",
    "RUB",
    "RWF",
    "CHF",
    "KRW",
    "LKR",
    "RSD",
    "SAR",
    "SBD",
    "SCR",
    "SDG",
    "SEK",
    "SGD",
    "SHP",
    "SLL",
    "SOS",
    "SRD",
    "STD",
    "SVC",
    "SYP",
    "SZL",
    "WST",
    "XAG",
    "XDR",
    "ZAR",
    "THB",
    "TJS",
    "TMT",
    "TND",
    "TOP",
    "TRY",
    "TTD",
    "TZS",
    "AED",
    "UAH",
    "UGX",
    "USD",
    "UYU",
    "UZS",
    "VEF",
    "VND",
    "VUV",
    "YER",
    "ZMK",
    "ZMW",
    "ZWL",
]
