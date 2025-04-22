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

class TravelClaim(Document):
	def validate(self):
		self.get_advance()
		self.calculate_amount()
		# validate_workflow_states(self)

	def on_submit(self):
		# self.update_travel_authorization()
		self.post_journal_entry()
		# self.post_journal_entry()

	def before_cancel(self):
		if self.journal_entry:
			journal_entry = frappe.get_doc("Journal Entry", self.journal_entry)
			if journal_entry.docstatus == 1:
				journal_entry.cancel()
				frappe.msgprint(_("Journal Entry {0} has been canceled.").format(self.journal_entry))

	def on_cancel(self):
		
		self.ignore_linked_doctypes = ("GL Entry", "Salary Slip", "Journal Entry","Payment Ledger Entry")
		# if self.journal_entry:
		journal_entries = frappe.get_all(
			"Journal Entry",
			filters={"reference_name": self.name},
			pluck="name"
		)

		for je in journal_entries:
			doc = frappe.get_doc("Journal Entry", je)
			if doc.docstatus == 1:
				doc.cancel()
				doc.db_update()  
		
		payment_ledger_entries = frappe.get_all(
			"Payment Ledger Entry",
			filters={"voucher_no": self.journal_entry},
			pluck="name"
				)

		for entry in payment_ledger_entries:
			frappe.delete_doc("Payment Ledger Entry", entry, force=1, ignore_permissions=True)

		# self.db_set("journal_entry", "")
		# self.db_set("journal_entry_status", "")
		frappe.msgprint(_("Journal Entry {0} has been deleted.").format(self.journal_entry))
		# frappe.throw(
			# 		_("You need to cancel Journal Entry {} to be able to cancel this document.").format(
			# 			get_link_to_form("Journal Entry", self.journal_entry)
			# 		),
			# 		title=_("Not Allowed"),
			# 	)

	def calculate_amount(self):
		total, advance_amount = 0.0, 0.0
		for d in self.get("items"):
			total += flt(d.amount)
		self.total_amount = flt(total)

		if self.miscellaneous_amount:
			self.total_amount += flt(self.miscellaneous_amount)

		for adv in self.get("advances"):
			advance_amount += flt(adv.advance_amount)
		self.advance_amount = flt(advance_amount)
		self.net_amount = flt(self.total_amount) - flt(self.advance_amount)
			
	def get_advance(self):
		self.set("advances", [])
		
		Advance = frappe.qb.DocType("Travel Advance")
		
		query = (
			frappe.qb.from_(Advance)
			.select(
				Advance.name.as_("reference_name"),
				Advance.paid_amount.as_("advance_amount"),
				Advance.posting_date
			)
			.where(
				(Advance.docstatus == 1)
				& (Advance.paid_amount > 0)
				& (Advance.travel_authorization == self.travel_authorization)
				& (Advance.employee == self.employee)
				& (Advance.company == self.company)
			)
		)
		
		advances = query.run(as_dict=True)
		
		if not advances:
			frappe.msgprint("No approved advances found for this request.", alert=True)
		
		self.set("advances", advances)

	def post_journal_entry(self):
		self.post_payable_entry()
		if self.net_amount > 0:
			self.post_payment_entry()
	def post_payable_entry(self):
		if self.cost_center: 
			cost_center = self.cost_center
		else:
			cost_center = frappe.db.get_value("Employee", self.employee, "cost_center")
		if not cost_center:
			frappe.throw("Setup Cost Center for employee in Employee Master")

		# expense_bank_account = frappe.db.get_value("Branch", self.branch, "expense_bank_account")
		# if not expense_bank_account:
		# 	frappe.throw("Setup Default Expense Bank Account in {}".format(frappe.get_desk_link("Branch", self.branch)))
		
		gl_account = ""	
		
		expense_account = frappe.db.get_value("Travel Type", self.travel_type, "account")
		
		# expense_account = frappe.db.get_single_value("HR Accounts Settings", gl_account)
		payable_account = frappe.db.get_value("Company", 'Green Bhutan Corporation Limited', 'default_payable_account')
		if not expense_account:
			frappe.throw("Setup Travel/Training Accounts in HR Accounts Settings")

		advance_account = frappe.db.get_value("Company", 'Green Bhutan Corporation Limited', 'travel_advance_account')
		if not advance_account:
			frappe.throw("Setup Advance to Employee (Travel) in Company")

		# Payables
		je = frappe.new_doc("Journal Entry")
		je.flags.ignore_permissions = 1
		je.title = "Travel Payable (" + self.employee_name + "  " + self.name + ")"
		je.voucher_type = "Journal Entry"
		je.naming_series = "Journal Voucher"
		je.remark = 'Claim payment against : ' + self.name
		je.posting_date = self.posting_date
		je.branch = self.branch

		je.append("accounts", {
				"account": expense_account,
				"reference_type": "Travel Claim",
				"reference_name": self.name,
				"cost_center": self.cost_center,
				"debit_in_account_currency": flt(self.total_amount),
				"debit": flt(self.total_amount),
			})

		if self.net_amount > 0:
			je.append("accounts", {
					"account": payable_account,
					"reference_type": self.doctype,
					"reference_name": self.name,
					"cost_center": self.cost_center,
					"credit_in_account_currency": flt(self.net_amount,2),
					"credit": flt(self.net_amount,2),
					"party_type": "Employee",
					"party": self.employee, 
				})
		else:
			je.append("accounts", {
					"account": advance_account,
					"reference_type": self.doctype,
					"reference_name": self.name,
					"cost_center": self.cost_center,
					"credit_in_account_currency": flt(self.total_amount),
					"credit": flt(self.total_amount),
					"party_type": "Employee",
					"party": self.employee, 
				})

		if flt(self.advance_amount) > 0 and self.net_amount > 0:
			je.append("accounts", {
				"account": advance_account,
				"party_type": "Employee",
				"party": self.employee,
				"reference_type": "Travel Claim",
				"reference_name": self.name,
				"cost_center": cost_center,
				"credit_in_account_currency": flt(self.advance_amount),
				"credit": flt(self.advance_amount),
			})

		je.insert()
		je.submit()
	def post_payment_entry(self):
		# travel_expense_account = frappe.db.get_value("Travel Type", self.travel_type, "account")
		advance_account = frappe.db.get_value("Company", self.company, "travel_advance_account")
		bank_account = frappe.db.get_value("Branch", self.branch, "expense_bank_account")
		payable_account = frappe.db.get_value("Company", 'Green Bhutan Corporation Limited', 'default_payable_account')


		if not payable_account:
			frappe.throw("Default Payable account missing in company")
			

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
			"account": payable_account,
			"debit": flt(self.total_amount),
			"debit_in_account_currency": flt(self.total_amount),
			"cost_center": self.cost_center,
			"party_check": 1,
			"party_type": "Employee",
			"party": self.employee,
			"is_advance": "Yes",
			"reference_type": "Travel Claim",
			"reference_name": self.name,
		})

		if flt(self.advance_amount) > 0:
			accounts.append({
				"account": advance_account,
				"credit": flt(self.advance_amount),
				"credit_in_account_currency": flt(self.advance_amount),
				"cost_center": self.cost_center,
				"party_check": 1,
				"party_type": "Employee",
				"party": self.employee,
			})

		accounts.append({
			"account": bank_account,
			"credit": flt(self.total_amount) - flt(self.advance_amount),
			"credit_in_account_currency": flt(self.total_amount) - flt(self.advance_amount),
			"cost_center": self.cost_center,
		})

		je = frappe.new_doc("Journal Entry")
		
		voucher_type = "Bank Entry"
		naming_series = "Bank Payment Voucher"
		
		je.update({
				"doctype": "Journal Entry",
				"voucher_type": voucher_type,
				"naming_series": naming_series,
				"title": "Travel Payment - "+self.employee,
				"user_remark": "Travek Advance - "+self.employee,
				"posting_date": nowdate(),
				"company": self.company,
				"accounts": accounts,
				"branch": self.branch
		})

		je.insert()
		# je.submit()

		if self.advance_amount:
			je.save(ignore_permissions = True)
			self.db_set("journal_entry", je.name)
			self.db_set("journal_entry_status", "Forwarded to accounts for processing payment on {0}".format(now_datetime().strftime('%Y-%m-%d %H:%M:%S')))
			frappe.msgprint(_('{} posted to accounts').format(frappe.get_desk_link(je.doctype, je.name)))

	@frappe.whitelist()
	def is_mileage_claim_allowed(self) -> dict[str, bool]:
		is_allowed = frappe.db.get_value("Mode of Travel", self.mode_of_travel, "allow_mileage_claim")
		return {
			"is_allowed": bool(is_allowed)
		}

@frappe.whitelist()
def get_travel_claim(dt, dn):
	doc = frappe.get_doc(dt, dn)

	employee_grade = frappe.db.get_value("Employee", doc.employee, "grade")
	dsa = frappe.db.get_value("Employee Grade", employee_grade, "dsa")
	if not dsa:
		frappe.throw(
			"Daily Subsistence Allowance (DSA) is not set for Employee Grade: {}. Please update it.".format(
				frappe.get_desk_link("Employee Grade", employee_grade)
			),
			title="Missing DSA Configuration"
		)

	return_day_dsa = frappe.db.get_single_value("HR Settings", "return_day_dsa")

	tc = frappe.new_doc("Travel Claim")
	tc.posting_date = frappe.utils.nowdate()
	tc.employee = doc.employee
	tc.employee_name = doc.employee_name
	tc.travel_type = doc.travel_type
	tc.purpose_of_travel = doc.purpose_of_travel
	tc.mode_of_travel = doc.mode_of_travel
	tc.branch = doc.branch
	tc.cost_center = doc.cost_center

	for d in doc.get("items"):
		item = d.as_dict()
		if d.is_last_day == 1:
			item["dsa_percent"] = return_day_dsa if return_day_dsa else 100
			item["dsa"] = flt(dsa) * flt(item["dsa_percent"])/100
		else:
			item["dsa_percent"] = 100
			item["dsa"] = dsa
		item["no_of_days"] = date_diff(d.to_date, d.from_date) + 1
		item["amount"] = flt(item["no_of_days"]) * flt(item["dsa"])
		tc.append("items", item)

	tc.travel_authorization = doc.name
	tc.currency = doc.currency
	tc.exchange_rate = doc.exchange_rate

	return tc.as_dict()
