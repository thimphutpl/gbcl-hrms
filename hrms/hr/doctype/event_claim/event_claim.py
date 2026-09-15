# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form

import erpnext

from hrms.hr.utils import set_employee_name, validate_active_employee

# Event Claim workflow: Employee submits -> Director verifies -> CFO approves
# (approval creates the Journal Entry). Each approver should only see claims
# currently awaiting THEIR OWN stage, not the full history of every claim.
CLAIM_APPROVAL_STAGES = {
	"Director": "Waiting for Verification",
	"CFO": "Waiting Approval",
}
PRIVILEGED_ROLES = {"System Manager", "HR Manager", "HR User"}


def is_privileged(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_privileged(user):
		return None
	roles = set(frappe.get_roles(user))
	states = {state for role, state in CLAIM_APPROVAL_STAGES.items() if role in roles}
	if states:
		clauses = " or ".join(
			"`tabEvent Claim`.workflow_state = {0}".format(frappe.db.escape(s)) for s in states
		)
		return "({0})".format(clauses)
	return None


def has_permission(doc, ptype, user=None):
	"""See the matching comment on Travel Claim's has_permission for why the
	state-based narrowing only ever applies to READ-family ptypes."""
	user = user or frappe.session.user
	if is_privileged(user):
		return True
	if not doc or doc.is_new():
		return None
	roles = set(frappe.get_roles(user))
	states = {state for role, state in CLAIM_APPROVAL_STAGES.items() if role in roles}
	if states:
		if ptype in ("read", "print", "email", "select"):
			return doc.workflow_state in states
		return None
	return None


class EventClaim(Document):
	def validate(self):
		validate_active_employee(self.employee)
		set_employee_name(self)
		self.validate_duplicate_claim()
		self.set_currency()
		self.calculate_total_amount()
		self.set_default_accounts()
		self.set_status()

	def validate_duplicate_claim(self):
		if not (self.event_request and self.employee):
			return

		existing = frappe.db.get_value(
			"Event Claim",
			{
				"event_request": self.event_request,
				"employee": self.employee,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("Event Claim {0} already exists for {1} against {2}.").format(
					get_link_to_form("Event Claim", existing),
					frappe.bold(self.employee),
					get_link_to_form("Event Request", self.event_request),
				),
				title=_("Duplicate Claim"),
			)

	def set_currency(self):
		if not self.currency:
			self.currency = erpnext.get_company_currency(self.company)

	def calculate_total_amount(self):
		total = 0.0
		for row in self.get("cost_breakdown"):
			self.round_floats_in(row)
			total += flt(row.amount)
		self.total_amount = flt(total)
		self.round_floats_in(self, ["total_amount"])

	def set_default_accounts(self):
		"""Pre-fill accounting fields from Company defaults when left blank."""
		if not self.company:
			return

		defaults = frappe.get_cached_value(
			"Company",
			self.company,
			["default_expense_account", "default_expense_claim_payable_account", "cost_center"],
			as_dict=True,
		)
		if not self.expense_account:
			self.expense_account = defaults.get("default_expense_account")
		if not self.payable_account:
			self.payable_account = defaults.get("default_expense_claim_payable_account")
		if not self.cost_center:
			self.cost_center = defaults.get("cost_center")

	def set_status(self, update=False):
		status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
		status = status_map.get(self.docstatus, "Draft")

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def on_submit(self):
		self.post_journal_entry()

	def before_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.flags.ignore_permissions = True
				je.cancel()
				frappe.msgprint(_("Journal Entry {0} has been cancelled.").format(self.journal_entry))

	def on_cancel(self):
		self.set_status(update=True)

	def post_journal_entry(self):
		"""Post an accrual Journal Entry for the claimed event cost. This is the
		only place an Event Claim (and therefore Event) ever touches the ledger —
		the Event Request itself is authorization-only."""
		amount = flt(self.total_amount)
		if amount <= 0:
			return
		if self.journal_entry:
			return

		if not self.expense_account or not self.payable_account:
			frappe.throw(
				_("Expense Account and Payable / Accrued Account are required to post the Journal Entry.")
			)

		cost_center = self.cost_center or erpnext.get_default_cost_center(self.company)
		remark = _("Event Claim {0} against {1}").format(self.name, self.event_request)

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.posting_date
		je.user_remark = remark
		je.title = _("Event Claim ({0} — {1})").format(self.employee_name, self.name)
		self.set_je_naming_series(je)

		# Some localizations make "branch" mandatory on Journal Entry
		if je.meta.get_field("branch") and not je.get("branch"):
			je.branch = frappe.db.get_value("Employee", self.employee, "branch") or frappe.db.get_value(
				"Branch", {}, "name"
			)

		je.append(
			"accounts",
			{
				"account": self.expense_account,
				"debit_in_account_currency": amount,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": self.payable_account,
				"credit_in_account_currency": amount,
				"cost_center": cost_center,
			},
		)

		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

		self.db_set("journal_entry", je.name)
		self.db_set(
			"journal_entry_status",
			_("Posted on {0}").format(frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S")),
		)
		frappe.msgprint(
			_("Journal Entry {0} created for this Event Claim.").format(get_link_to_form("Journal Entry", je.name)),
			alert=True,
		)

	def set_je_naming_series(self, je):
		"""Handle sites that customize Journal Entry naming — see the matching
		comment previously on Event Request's own make_journal_entry for why."""
		field = je.meta.get_field("naming_series")
		if not field or je.get("naming_series"):
			return

		if frappe.db.exists("DocType", "Journal Entry Series"):
			series = frappe.db.get_value(
				"Journal Entry Series",
				{"entry_type": "Journal Entry", "enabled": 1, "journal_entry_series": "Journal Voucher"},
				"name",
			) or frappe.db.get_value(
				"Journal Entry Series", {"entry_type": "Journal Entry", "enabled": 1}, "name"
			)
			if series:
				je.naming_series = series
		elif field.options:
			je.naming_series = field.options.split("\n")[0]


@frappe.whitelist()
def get_event_claim(dt, dn):
	"""Prefill a new Event Claim from an approved Event Request, the same way
	Travel Claim's get_travel_claim maps from an approved Travel Authorization."""
	doc = frappe.get_doc(dt, dn)
	doc.check_permission("read")

	if doc.docstatus != 1:
		frappe.throw(_("{0} must be submitted before it can be claimed.").format(dn))

	existing = frappe.db.get_value(
		"Event Claim",
		{"event_request": doc.name, "employee": doc.employee, "docstatus": ("<", 2)},
		"name",
	)
	if existing:
		frappe.throw(
			_("Event Claim {0} already exists for {1}.").format(
				get_link_to_form("Event Claim", existing), frappe.bold(doc.employee)
			),
			title=_("Already Claimed"),
		)

	ec = frappe.new_doc("Event Claim")
	ec.event_request = doc.name
	ec.employee = doc.employee
	ec.employee_name = doc.employee_name
	ec.company = doc.company
	ec.department = doc.department
	ec.currency = doc.currency
	ec.cost_center = doc.cost_center
	ec.posting_date = frappe.utils.nowdate()

	for d in doc.get("cost_breakdown", []):
		row = d.as_dict()
		ec.append("cost_breakdown", row)

	return ec.as_dict()
