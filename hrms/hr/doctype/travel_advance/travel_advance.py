# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe.utils import (
	add_days,
	ceil,
	cint,
	cstr,
	date_diff,
	floor,
	flt,
	formatdate,
	get_first_day,
	get_last_day,
	get_link_to_form,
	getdate,
	money_in_words,
	rounded,
	nowdate,
	now_datetime
)
from erpnext.custom_workflow import validate_workflow_states, notify_workflow_states

class TravelAdvance(Document):
	def validate(self):
		self.validate_advance_amount()
		validate_workflow_states(self)

	def validate_advance_amount(self):
		if flt(self.advance_amount) > flt(flt(self.estimated_amount) * 0.9):
			frappe.throw("Advance Amount cannot be greater than 90% of Total Estimated Amount")

	def on_submit(self):
		self.post_journal_entry()

	def post_journal_entry(self):
		advance_account = frappe.db.get_value("Company", self.company, "travel_advance_account")
		bank_account = frappe.db.get_value("Branch", self.branch, "expense_bank_account")

		if not advance_account:
			frappe.throw(
				"Travel Advance Account is not set for {}. Please configure it in the Company.".format(
					frappe.get_desk_link("Company", self.company)
				),
				title="Missing Travel Advance Account"
			)

		if not bank_account:
			frappe.throw(
				"Default Expense Bank Account is not set for {}. Please configure it in the Branch.".format(
					frappe.get_desk_link("Branch", self.branch)
				),
				title="Missing Expense Bank Account"
			)

		# Posting Journal Entry
		accounts = []
		accounts.append({
			"account": advance_account,
			"debit": flt(self.advance_amount),
			"debit_in_account_currency": flt(self.advance_amount),
			"cost_center": self.cost_center,
			"party_check": 1,
			"party_type": "Employee",
			"party": self.employee,
			"is_advance": "Yes",
			"reference_type": "Travel Advance",
			"reference_name": self.name,
		})

		accounts.append({
			"account": bank_account,
			"credit": flt(self.advance_amount),
			"credit_in_account_currency": flt(self.advance_amount),
			"cost_center": self.cost_center,
		})

		je = frappe.new_doc("Journal Entry")
		
		voucher_type = "Bank Entry"
		naming_series = "Bank Payment Voucher"
		
		je.update({
				"doctype": "Journal Entry",
				"voucher_type": voucher_type,
				"naming_series": naming_series,
				"title": "Travel Advance - "+self.employee,
				"user_remark": "Travek Advance - "+self.employee,
				"posting_date": nowdate(),
				"company": self.company,
				"accounts": accounts,
				"branch": self.branch
		})

		if self.advance_amount:
			je.save(ignore_permissions = True)
			self.db_set("journal_entry", je.name)
			self.db_set("journal_entry_status", "Forwarded to accounts for processing payment on {0}".format(now_datetime().strftime('%Y-%m-%d %H:%M:%S')))
			frappe.msgprint(_('{} posted to accounts').format(frappe.get_desk_link(je.doctype,je.name)))


@frappe.whitelist()
def make_travel_advance(dt, dn):
	"""
	Creates a Travel Advance document linked to the given Travel Authorization.
	"""
	doc = frappe.get_doc(dt, dn)
	if doc.items:
		from_date = doc.items[0].from_date
		to_date = doc.items[-1].from_date if len(doc.items) > 1 else from_date

	employee_grade = frappe.db.get_value("Employee", doc.employee, "grade")
	dsa = frappe.db.get_value("Employee Grade", employee_grade, "dsa")

	no_of_days = date_diff(to_date, from_date) + 1

	adv = frappe.new_doc("Travel Advance")
	adv.employee = doc.employee
	adv.employee_name = doc.employee_name
	adv.branch = doc.branch
	adv.cost_center = doc.cost_center
	adv.currency = doc.currency
	adv.exchange_rate = doc.exchange_rate
	adv.from_date = from_date
	adv.to_date = to_date

	adv.estimated_amount = flt(dsa) * flt(no_of_days)

	adv.travel_authorization = doc.name

	return adv.as_dict()