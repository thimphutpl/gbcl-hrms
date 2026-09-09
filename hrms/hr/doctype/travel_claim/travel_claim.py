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
from hrms.hr.doctype.travel_authorization.travel_authorization import get_claimant_employee, is_privileged

# Travel Claim workflow: Employee submits -> Director verifies -> CFO approves
# (approval creates the Journal Entry). Each approver should only see claims
# currently awaiting THEIR OWN stage, not the full history of every claim.
CLAIM_APPROVAL_STAGES = {
	"Director": "Waiting for Verification",
	"CFO": "Waiting Approval",
}


def get_permission_query_conditions(user):
	user = user or frappe.session.user
	if is_privileged(user):
		return None
	roles = set(frappe.get_roles(user))
	states = {state for role, state in CLAIM_APPROVAL_STAGES.items() if role in roles}
	if states:
		clauses = " or ".join(
			"`tabTravel Claim`.workflow_state = {0}".format(frappe.db.escape(s)) for s in states
		)
		return "({0})".format(clauses)
	return None


def has_permission(doc, ptype, user):
	"""Controller permission hooks can only DENY, never grant beyond what the
	standard role/user-permission engine already allows (frappe.permissions
	.has_controller_permissions). So this only narrows an approver's broad
	DocType-level access down to claims pending THEIR OWN stage; every other
	user (including an employee opening their own claim) is left to the
	standard engine by returning None.

	The state-based narrowing only applies to READ-family ptypes. It must NOT
	gate write/submit: apply_workflow() sets workflow_state to the *next*
	state before calling doc.submit(), so by the time a write permission
	check runs here the state has already moved past the approver's pending
	stage. Frappe's own transition engine (transition.allowed in
	get_transitions) already restricts who can perform which action,
	independently and before any state mutation, so deferring (None) for
	write-type ptypes is safe."""
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

class TravelClaim(Document):
	def validate(self):
		self.validate_duplicate_claim()
		self.get_advance()
		self.calculate_miscellaneous()
		self.calculate_amount()
		# validate_workflow_states(self)

	def validate_duplicate_claim(self):
		if not (self.travel_authorization and self.employee):
			return

		existing = frappe.db.get_value(
			"Travel Claim",
			{
				"travel_authorization": self.travel_authorization,
				"employee": self.employee,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("Travel Claim {0} already exists for {1} against {2}.").format(
					get_link_to_form("Travel Claim", existing),
					frappe.bold(self.employee),
					get_link_to_form("Travel Authorization", self.travel_authorization),
				),
				title=_("Duplicate Claim"),
			)

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
	def calculate_miscellaneous(self):
		# see the matching guard/comment in Travel Authorization's
		# calculate_miscellaneous_total -- must check _action, not docstatus,
		# since docstatus is already 1 during the actual Approve/submit action
		if getattr(self, "_action", None) == "update_after_submit":
			return
		rate = flt(self.exchange_rate) or 1
		self.miscellaneous_amount = 0
		self.miscellaneous_amount_btn = 0
		for i in self.miscellaneous_item:
			i.amount_in_btn = flt(i.amount) * rate
			self.miscellaneous_amount += i.amount
			self.miscellaneous_amount_btn += i.amount_in_btn

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
		if self.travel_type=="Domestic":
			expense_account = frappe.db.get_value("Company", self.company, "domestic_travel_expense")
			if not expense_account:
				frappe.throw("Please set domestic travel expense in company")
		if self.travel_type=="International":
			expense_account = frappe.db.get_value("Company", self.company, "international_travel_expense")
			if not expense_account:
				frappe.throw("Please set domestic travel expense in company")
		
		# expense_account = frappe.db.get_single_value("HR Accounts Settings", gl_account)
		payable_account = frappe.db.get_value("Company", self.company, 'default_payable_account')
		if not expense_account:
			frappe.throw("Setup Travel/Training Accounts in HR Accounts Settings")

		advance_account = frappe.db.get_value("Company", self.company, 'travel_advance_account')
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
		je.company = self.company

		if self.miscellaneous_amount > 0:
			for i in self.miscellaneous_item:
				miscellaneous_expense_account = frappe.db.get_value("Miscellaneous", i.miscellaneous_type, "accounts")
				if not miscellaneous_expense_account:
					frappe.throw(f"No account configured for miscellaneous type '{i.miscellaneous_type}' in row #{i.idx}")
				je.append("accounts", {
				"account": miscellaneous_expense_account,
				"reference_type": "Travel Claim",
				"reference_name": self.name,
				"cost_center": self.cost_center,
				"debit_in_account_currency": flt(i.amount),
				"debit": flt(i.amount),
			})
			non_misc_amount = flt(self.total_amount) - flt(self.miscellaneous_amount)
			if non_misc_amount:
				# a claim can be entirely miscellaneous costs (itinerary rows
				# left at 0, e.g. an Office Car trip with no per-leg fare) --
				# posting this row anyway would debit and credit 0, which
				# Frappe's Journal Entry rejects as "cannot both be zero"
				je.append("accounts", {
					"account": expense_account,
					"reference_type": "Travel Claim",
					"reference_name": self.name,
					"cost_center": self.cost_center,
					"debit_in_account_currency": non_misc_amount,
					"debit": non_misc_amount,
				})

		else:
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
		# frappe.throw(frappe.as_json(je))
		je.insert()
		je.submit()
	def post_payment_entry(self):
		# travel_expense_account = frappe.db.get_value("Travel Type", self.travel_type, "account")
		advance_account = frappe.db.get_value("Company", self.company, "travel_advance_account")
		bank_account = frappe.db.get_value("Branch", self.branch, "expense_bank_account")
		payable_account = frappe.db.get_value("Company", self.company, 'default_payable_account')


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
			"debit": flt(self.total_amount) - flt(self.advance_amount),
			"debit_in_account_currency": flt(self.total_amount) - flt(self.advance_amount),
			"cost_center": self.cost_center,
			"party_check": 1,
			"party_type": "Employee",
			"party": self.employee,
			"is_advance": "Yes",
			"reference_type": "Travel Claim",
			"reference_name": self.name,
		})

		# if flt(self.advance_amount) > 0:
		# 	accounts.append({
		# 		"account": advance_account,
		# 		"credit": flt(self.advance_amount),
		# 		"credit_in_account_currency": flt(self.advance_amount),
		# 		"cost_center": self.cost_center,
		# 		"party_check": 1,
		# 		"party_type": "Employee",
		# 		"party": self.employee,
		# 	})

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

	# each traveller claims their own rows; the applicant also claims the
	# rows of non-login travellers (party type Others)
	claimant = get_claimant_employee(doc)

	existing = frappe.db.get_value(
		"Travel Claim",
		{"travel_authorization": doc.name, "employee": claimant, "docstatus": ("<", 2)},
		"name",
	)
	if existing:
		frappe.throw(
			_("Travel Claim {0} already exists for {1}.").format(
				get_link_to_form("Travel Claim", existing), frappe.bold(claimant)
			),
			title=_("Already Claimed"),
		)

	claimant_name = frappe.db.get_value("Employee", claimant, "employee_name")

	items = doc.rows_for_claimant(claimant, "items")
	if not items:
		frappe.throw(
			_("There are no travel itinerary rows for {0} in {1}.").format(frappe.bold(claimant), doc.name),
			title=_("Nothing to Claim"),
		)

	tc = frappe.new_doc("Travel Claim")
	tc.posting_date = frappe.utils.nowdate()
	tc.employee = claimant
	tc.employee_name = claimant_name
	tc.travel_type = doc.travel_type
	tc.purpose_of_travel = doc.purpose_of_travel
	tc.mode_of_travel = doc.mode_of_travel
	tc.branch = doc.branch
	tc.cost_center = doc.cost_center

	for d in items:
		# amount is filled in manually by the employee; no DSA auto-calculation
		item = d.as_dict()
		tc.append("items", item)

	for d in doc.rows_for_claimant(claimant, "travellers_detail"):
		tc.append("travellers_detail", d.as_dict())

	for d in doc.rows_for_claimant(claimant, "miscellaneous_item"):
		tc.append("miscellaneous_item", d.as_dict())

	tc.travel_authorization = doc.name
	tc.currency = doc.currency
	tc.exchange_rate = doc.exchange_rate

	return tc.as_dict()
