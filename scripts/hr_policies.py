"""Synthetic internal HR policies for a fictional company, Northwind Analytics.

These are written for this project and saved as .docx so the corpus covers Word files.
"""

COMPANY = "Northwind Analytics Pvt. Ltd."

POLICIES = {
    "Leave and Holiday Policy": {
        "Scope": (
            f"This policy applies to all full-time employees of {COMPANY} in India. "
            "Interns and contractors follow the leave terms in their individual agreements."
        ),
        "Annual Leave": (
            "Full-time employees earn 24 days of paid annual leave per calendar year, "
            "credited at 2 days per month. Up to 10 unused annual leave days may be carried "
            "forward to the next year; any balance above 10 days lapses on 31 December. "
            "Annual leave requests of more than 3 consecutive days must be submitted in the "
            "HR portal at least 14 days in advance."
        ),
        "Sick Leave": (
            "Employees receive 12 days of paid sick leave per year. Sick leave does not carry "
            "forward. A medical certificate is required for sick leave longer than 2 "
            "consecutive working days."
        ),
        "Parental Leave": (
            "Birthing parents receive 26 weeks of paid maternity leave. Non-birthing parents "
            "receive 4 weeks of paid paternity leave, which must be taken within 6 months of "
            "the birth or adoption. Adoptive parents of a child under 3 months receive 12 "
            "weeks of paid leave."
        ),
        "Public Holidays": (
            "The company observes 12 public holidays each year. The list is published by HR "
            "every December. Employees who work on a public holiday at a manager's request "
            "receive one compensatory day off, to be used within 60 days."
        ),
    },
    "Remote and Hybrid Work Policy": {
        "Eligibility": (
            "Employees who have completed their 90-day probation period may work remotely, "
            "subject to manager approval. New joiners work from the office during probation."
        ),
        "Hybrid Schedule": (
            "The standard hybrid schedule is 3 days in the office and 2 days remote each week. "
            "Tuesday and Thursday are mandatory office days for all teams. Fully remote "
            "arrangements require approval from the department head and HR."
        ),
        "Home Office Allowance": (
            "Eligible employees receive a one-time home office allowance of INR 15,000 for "
            "furniture and equipment, plus a monthly internet reimbursement of up to INR 1,000. "
            "Claims must be filed with receipts in the expense system."
        ),
        "Security Requirements": (
            "Remote work must use a company-managed laptop and the corporate VPN. Working from "
            "public Wi-Fi without the VPN is prohibited. Lost or stolen devices must be reported "
            "to the IT helpdesk within 4 hours."
        ),
    },
    "Travel and Expense Policy": {
        "Approval": (
            "All business travel must be pre-approved by the employee's manager in the travel "
            "portal. International travel also requires approval from the department head."
        ),
        "Flights": (
            "Employees book economy class for all domestic flights. Business class is allowed "
            "only for international flights longer than 8 hours, with director approval."
        ),
        "Hotels and Meals": (
            "The hotel limit is INR 7,000 per night in metro cities and INR 4,500 per night in "
            "other cities. The daily meal allowance is INR 1,500 for domestic travel and "
            "USD 60 for international travel. Alcohol is not reimbursable."
        ),
        "Claims": (
            "Expense claims must be submitted within 30 days of the end of the trip, with "
            "itemised receipts for any single expense above INR 500. Claims submitted after 90 "
            "days are not reimbursed."
        ),
    },
    "Code of Conduct and Anti-Harassment Policy": {
        "Principles": (
            "Employees must act with integrity, treat colleagues with respect, and avoid "
            "conflicts of interest. Gifts from vendors worth more than INR 2,500 must be "
            "declared to the compliance team and may not be accepted without approval."
        ),
        "Anti-Harassment": (
            "The company has zero tolerance for harassment. In line with the POSH Act, an "
            "Internal Committee (IC) handles complaints of sexual harassment. Complaints should "
            "be filed within 3 months of the incident. The IC completes its inquiry within 90 "
            "days."
        ),
        "Reporting Concerns": (
            "Concerns can be raised with a manager, HR, or the confidential ethics hotline. "
            "Retaliation against anyone who reports a concern in good faith is a disciplinary "
            "offence."
        ),
    },
    "Performance Review and Compensation Policy": {
        "Review Cycle": (
            "Performance reviews happen twice a year, in April and October. Each review includes "
            "a self-assessment, a manager assessment, and a calibration meeting."
        ),
        "Ratings": (
            "Employees are rated on a 5-point scale: 1 (Below Expectations) to 5 (Exceptional). "
            "A rating of 2 or lower in two consecutive cycles leads to a 60-day performance "
            "improvement plan (PIP)."
        ),
        "Salary Revisions": (
            "Annual salary revisions take effect on 1 July and are based on the April review. "
            "Promotions can be proposed in either cycle and take effect from the first day of "
            "the following month."
        ),
        "Bonus": (
            "The annual performance bonus target is 10% of base salary for individual "
            "contributors and 15% for managers. The payout ranges from 0% to 150% of target, "
            "depending on company results and the individual rating."
        ),
    },
}
