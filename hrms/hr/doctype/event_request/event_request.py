# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt

import erpnext

from hrms.hr.utils import set_employee_name, share_doc_with_approver, validate_active_employee


class EventRequest(Document):
	# Designations permitted to raise an Event Request (case-insensitive match)
	ALLOWED_REQUESTER_DESIGNATIONS = (
		"director",
		"associate director",
		"head of department",
		"hod",
	)

	def validate(self):
		validate_active_employee(self.employee)
		set_employee_name(self)
		self.warn_if_requester_not_authorized()
		self.set_currency()
		self.calculate_total_estimated_cost()
		self.set_default_accounts()
		self.set_status()

	def warn_if_requester_not_authorized(self):
		"""Advisory only — flags requesters below Head of Department level."""
		if not self.designation:
			return
		if self.designation.strip().lower() not in self.ALLOWED_REQUESTER_DESIGNATIONS:
			frappe.msgprint(
				_(
					"{0} ({1}) is not a Head of Department, Associate Director or Director. "
					"Normally only these roles raise an Event Request — please route through the HoD if needed."
				).format(frappe.bold(self.employee_name or self.employee), self.designation),
				title=_("Permission notice"),
				indicator="orange",
			)

	def on_update(self):
		if self.event_approver:
			share_doc_with_approver(self, self.event_approver)

	def on_submit(self):
		# Submitting only files the request as "pending approval" — no ledger impact.
		# The Journal Entry is posted later, when an approver calls approve().
		self.set_status(update=True)

	def on_cancel(self):
		self.cancel_journal_entry()
		self.set_status(update=True)

	def validate_approver(self):
		allowed = {"System Manager", "HR Manager", "HR User", "Expense Approver"}
		if not allowed.intersection(set(frappe.get_roles())):
			frappe.throw(_("You are not permitted to approve or reject Event Requests."))

	@frappe.whitelist()
	def approve(self):
		self.validate_approver()
		if self.docstatus != 1:
			frappe.throw(_("Submit the Event Request before approving it."))

		if self.approval_status != "Approved":
			self.db_set("approval_status", "Approved")

		# Post the Journal Entry now (once) — this is the only place it is created.
		if not self.journal_entry:
			self.make_journal_entry()

		self.set_status(update=True)

	@frappe.whitelist()
	def reject(self, reason=None):
		self.validate_approver()
		if self.docstatus != 1:
			frappe.throw(_("Submit the Event Request before rejecting it."))

		self.db_set("approval_status", "Rejected")
		self.set_status(update=True)
		if reason:
			self.add_comment("Comment", _("Rejected: {0}").format(reason))

	def set_currency(self):
		if not self.currency:
			self.currency = erpnext.get_company_currency(self.company)

	def calculate_total_estimated_cost(self):
		"""Use the itemised breakdown only when enabled, else the header estimate."""
		if not self.add_cost_breakdown:
			self.cost_breakdown = []

		breakdown_total = 0.0
		for row in self.get("cost_breakdown"):
			self.round_floats_in(row)
			breakdown_total += flt(row.amount)

		if self.add_cost_breakdown and breakdown_total:
			self.estimated_event_cost = breakdown_total
			self.total_estimated_cost = breakdown_total
		else:
			self.total_estimated_cost = flt(self.estimated_event_cost)

		self.round_floats_in(self, ["estimated_event_cost", "total_estimated_cost"])

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
		status = {"0": "Draft", "1": "Submitted", "2": "Cancelled"}[cstr(self.docstatus or 0)]

		if self.docstatus == 1:
			if self.approval_status == "Approved":
				status = "Approved"
			elif self.approval_status == "Rejected":
				status = "Rejected"

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def make_journal_entry(self):
		"""Post an accrual Journal Entry for the approved estimated event cost."""
		amount = flt(self.total_estimated_cost)
		if amount <= 0:
			return

		if self.journal_entry:
			# already posted (e.g. on re-submit of an amended doc handled separately)
			return

		if not self.expense_account or not self.payable_account:
			frappe.throw(
				_("Expense Account and Payable / Accrued Account are required to post the Journal Entry.")
			)

		cost_center = self.cost_center or erpnext.get_default_cost_center(self.company)
		remark = _("Event Request {0}: {1}").format(self.name, self.event_title or "")

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.posting_date
		je.user_remark = remark
		je.bill_no = self.approved_ref_number or self.name
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
				"project": self.project,
				"user_remark": remark,
			},
		)
		je.append(
			"accounts",
			{
				"account": self.payable_account,
				"credit_in_account_currency": amount,
				"cost_center": cost_center,
				"project": self.project,
				"user_remark": remark,
			},
		)

		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

		self.db_set("journal_entry", je.name)
		frappe.msgprint(
			_("Journal Entry {0} created for this Event Request.").format(
				frappe.utils.get_link_to_form("Journal Entry", je.name)
			),
			alert=True,
		)

	def set_je_naming_series(self, je):
		"""Handle sites that customize Journal Entry naming.

		On standard ERPNext, Journal Entry auto-picks its default series. Some
		localizations (e.g. GMC) drive naming from a "Journal Entry Series" master
		and require ``naming_series`` to be set explicitly, else naming fails.
		"""
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

	def cancel_journal_entry(self):
		if not self.journal_entry:
			return

		if not frappe.db.exists("Journal Entry", self.journal_entry):
			return

		je = frappe.get_doc("Journal Entry", self.journal_entry)
		if je.docstatus == 1:
			je.flags.ignore_permissions = True
			je.cancel()

		self.db_set("journal_entry", None)
