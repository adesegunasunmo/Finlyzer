"""
Module: resolution_playbooks.py
Purpose: Resolution playbooks for each complaint cluster type.
         Agents use these as step-by-step guides during live calls.
         IT uses them to understand the systemic fix needed.
"""

PLAYBOOKS = {
    "ATM": {
        "title": "ATM / Cash Dispense Failure",
        "icon": "🏧",
        "sla_hours": 4,
        "agent_steps": [
            "Confirm transaction date, time, amount and ATM location from customer",
            "Check core banking system — was the account debited?",
            "If debited and no cash dispensed: assure customer reversal will happen within 24–48 hours",
            "Generate reversal reference number and share with customer",
            "Log complaint with: ATM ID, transaction reference, amount, branch",
            "If ATM swallowed card: escalate to ATM Operations team immediately (SLA: 2 hours)",
            "Advise customer to use alternative channel in the meantime",
        ],
        "it_steps": [
            "Check ATM journal for the transaction",
            "Verify cash cassette status and ATM uptime logs",
            "If hardware fault: dispatch field engineer",
            "If software fault: restart ATM service remotely",
            "Confirm reversal processed in core banking",
            "Update Finlyzer incident with resolution details",
        ],
        "keywords": ["atm", "cash", "dispense", "withdraw", "card", "swallow", "machine"],
        "escalate_threshold": 3,
        "customer_message": "Your complaint has been logged. If your account was debited, a reversal will be processed within 24–48 hours. Reference: {ref}",
    },
    "TRANSFER": {
        "title": "Failed or Missing Transfer",
        "icon": "💸",
        "sla_hours": 8,
        "agent_steps": [
            "Collect: sender account, recipient account/bank, amount, date, transaction reference",
            "Check if transfer was debited from sender's account",
            "Verify beneficiary bank and account details are correct",
            "Check for network/interbank settlement delays (especially NIP/NIBSS)",
            "If debited but not received after 24 hours: raise reversal request",
            "Provide customer with complaint reference and 48-hour resolution timeline",
            "If amount exceeds ₦1M: escalate to transfers desk immediately",
        ],
        "it_steps": [
            "Query NIBSS/NIP transaction log with session ID",
            "Check if transaction is in pending/failed queue",
            "Contact receiving bank if settlement was sent but not credited",
            "Process reversal if transaction failed at beneficiary end",
            "Update transaction status in core banking",
        ],
        "keywords": ["transfer", "send", "receive", "beneficiary", "nibss", "nip", "delayed"],
        "escalate_threshold": 3,
        "customer_message": "Your transfer complaint (ref: {ref}) is under investigation. Resolution expected within 48 hours.",
    },
    "POS": {
        "title": "POS Terminal Decline / Double Charge",
        "icon": "💳",
        "sla_hours": 24,
        "agent_steps": [
            "Confirm merchant name, location, date, amount and whether receipt was issued",
            "Check if card was charged once or twice on the statement",
            "For decline: check card status, daily limit, available balance",
            "For double charge: confirm with customer this is not two separate purchases",
            "Raise chargeback/dispute for double charge — SLA 5 business days",
            "For card decline with sufficient balance: check card PIN attempts, block status",
            "Advise customer to keep merchant receipt as evidence",
        ],
        "it_steps": [
            "Query POS transaction log with terminal ID and trace number",
            "Check if settlement batch includes double entry",
            "Initiate chargeback process with card scheme if double charge confirmed",
            "Check for card block or restrictions in card management system",
        ],
        "keywords": ["pos", "card", "decline", "merchant", "debit", "double", "charge"],
        "escalate_threshold": 5,
        "customer_message": "Your POS dispute (ref: {ref}) has been lodged. Chargebacks take up to 5 business days. We will contact you.",
    },
    "MOBILE": {
        "title": "Mobile App / Internet Banking Issue",
        "icon": "📱",
        "sla_hours": 4,
        "agent_steps": [
            "Ask customer: what device, OS version, app version?",
            "Check if issue is login, transaction, or display",
            "For login failures: verify BVN, reset PIN/password via secure channel",
            "For transaction errors: check if amount was debited despite error",
            "Ask customer to try: clear cache, reinstall app, try internet banking instead",
            "If widespread: check if IT has declared a mobile banking incident",
            "Escalate to digital banking team if issue persists after basic troubleshooting",
        ],
        "it_steps": [
            "Check mobile banking server uptime and error logs",
            "Identify if issue is isolated or widespread from error frequency",
            "Check third-party API dependencies (payment gateway, OTP provider)",
            "If app bug: coordinate with vendor for hotfix",
            "Declare incident in Finlyzer if 5+ users affected",
        ],
        "keywords": ["app", "mobile", "login", "password", "internet", "banking", "online"],
        "escalate_threshold": 5,
        "customer_message": "We are aware of the issue with our mobile app. Our team is working on it. Ref: {ref}. Try internet banking at www.bank.ng as alternative.",
    },
    "USSD": {
        "title": "USSD (*737# or similar) Failure",
        "icon": "📞",
        "sla_hours": 4,
        "agent_steps": [
            "Confirm USSD code used, network provider (MTN/Airtel/Glo/9mobile), and error message",
            "Check if account was debited despite USSD timeout",
            "Advise customer to check balance before retrying to avoid double transactions",
            "If debited without completion: raise reversal request",
            "Check if network-specific USSD route is down",
            "Escalate to USSD Operations if more than 3 customers report same issue",
        ],
        "it_steps": [
            "Check USSD gateway logs for the session",
            "Verify connectivity with telco partner (MTN/Airtel/Glo/9mobile)",
            "Check for pending transactions in USSD middleware",
            "Coordinate with telco for route restoration if gateway is down",
        ],
        "keywords": ["ussd", "737", "code", "dial", "network", "timeout", "airtime"],
        "escalate_threshold": 3,
        "customer_message": "Your USSD complaint (ref: {ref}) has been logged. If debited, reversal will process within 24 hours.",
    },
    "ACCOUNT": {
        "title": "Account Block / Freeze / Restriction",
        "icon": "🔒",
        "sla_hours": 2,
        "agent_steps": [
            "Verify customer identity strictly before discussing account status",
            "Check account restriction type: compliance hold, fraud flag, or operational block",
            "If compliance hold (EFCC, regulatory): do NOT attempt to override — escalate to compliance team",
            "If operational block: check reason — post-no-debit, dormancy, or system flag",
            "Dormant account reactivation: require customer to visit branch with ID and utility bill",
            "Do not release funds over the phone — always require branch visit for account issues",
        ],
        "it_steps": [
            "Check account restriction flag in core banking",
            "Verify if restriction was system-generated or manually applied",
            "For system-generated: check trigger rule and clear if false positive",
            "Log all account restriction changes in audit trail",
        ],
        "keywords": ["block", "freeze", "locked", "restricted", "access", "dormant", "account"],
        "escalate_threshold": 2,
        "customer_message": "Your account issue (ref: {ref}) requires verification. Please visit any branch with a valid ID. Our team will assist you.",
    },
    "LOAN": {
        "title": "Loan / Credit Issue",
        "icon": "🏦",
        "sla_hours": 48,
        "agent_steps": [
            "Confirm loan type: personal loan, overdraft, mortgage, or quick loan",
            "Check loan status: disbursement pending, repayment dispute, or interest query",
            "For undisbursed approved loan: check if limit is set in core banking",
            "For wrong deduction: pull loan schedule and verify installment amount",
            "For interest dispute: escalate to loans department — do not quote rates over the phone",
            "Log all loan complaints with loan account number",
        ],
        "it_steps": [
            "Verify loan disbursement in core banking system",
            "Check loan schedule for correct installment amounts",
            "If system calculated wrong interest: escalate to loans IT team",
            "Verify repayment postings in loan ledger",
        ],
        "keywords": ["loan", "credit", "borrow", "repay", "interest", "disbursed", "overdraft"],
        "escalate_threshold": 5,
        "customer_message": "Your loan complaint (ref: {ref}) has been escalated to our loans team. Expect a call within 48 hours.",
    },
    "FRAUD": {
        "title": "Fraud / Unauthorized Transaction",
        "icon": "🚨",
        "sla_hours": 1,
        "agent_steps": [
            "IMMEDIATELY block the customer's card/account — do not wait",
            "Collect: all unauthorized transaction details, amounts, dates, merchants",
            "Ask customer: did they share OTP, PIN, or card details with anyone?",
            "Raise fraud report — this is a priority 1 escalation to fraud team",
            "Advise customer to change all banking passwords immediately",
            "Inform customer: provisional credit may be issued while investigation continues",
            "Document everything — fraud cases have legal implications",
        ],
        "it_steps": [
            "IMMEDIATELY freeze affected accounts",
            "Pull transaction logs and identify attack vector",
            "Check for SIM swap or account takeover indicators",
            "Coordinate with fraud intelligence team",
            "File CBN fraud report if amount exceeds threshold",
            "Preserve all digital evidence for investigation",
        ],
        "keywords": ["fraud", "unauthorized", "stolen", "hack", "otp", "scam", "fake"],
        "escalate_threshold": 1,
        "customer_message": "URGENT: Your account has been flagged. We have taken immediate protective action. Ref: {ref}. Our fraud team will call you within 1 hour.",
    },
}


SYSTEM_COMPONENTS = [
    {"id": "atm_network",    "name": "ATM network",       "icon": "🏧"},
    {"id": "mobile_banking", "name": "Mobile banking app", "icon": "📱"},
    {"id": "internet_banking","name": "Internet banking",  "icon": "💻"},
    {"id": "ussd",           "name": "USSD (*737#)",       "icon": "📞"},
    {"id": "pos_network",    "name": "POS terminals",      "icon": "💳"},
    {"id": "nip_nibss",      "name": "NIP/NIBSS transfers","icon": "💸"},
    {"id": "core_banking",   "name": "Core banking",       "icon": "🏦"},
    {"id": "cards",          "name": "Card management",    "icon": "💳"},
]


def match_playbook(text: str) -> str:
    """Return the best matching playbook key for a given complaint text."""
    text = text.lower()
    best_key = "ATM"
    best_score = 0
    for key, pb in PLAYBOOKS.items():
        score = sum(1 for kw in pb["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key


def get_playbook(key: str) -> dict:
    return PLAYBOOKS.get(key, PLAYBOOKS["ATM"])
