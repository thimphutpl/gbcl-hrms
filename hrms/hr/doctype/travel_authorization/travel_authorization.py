# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hrms.hr.utils import validate_active_employee
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
	nowdate
)
from erpnext.custom_workflow import validate_workflow_states, notify_workflow_states

PRIVILEGED_ROLES = {"System Manager", "HR Manager", "HR User"}


def get_session_employee(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def is_privileged(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


class TravelAuthorization(Document):
	def onload(self):
		self.filter_rows_for_traveller()

	def validate(self):
		validate_active_employee(self.employee)
		self.sync_traveller_tags()
		self.validate_travel_dates()
		self.validate_travel_last_day()
		self.validate_exchange_rate()
		self.calculate_miscellaneous_total()
		self.set_status()
		# validate_workflow_states(self)

	def on_update(self):
		self.validate_duplicate_entry()

	def on_submit(self):
		self.create_travel_journal_entry()

	def on_update_after_submit(self):
		self.create_travel_journal_entry()

	def on_cancel(self):
		self.set_status(update=True)
		self.cancel_travel_journal_entry()

	def calculate_miscellaneous_total(self):
		self.total_miscellaneous_amount = sum(flt(m.amount) for m in self.get("miscellaneous_item", []))

	def create_travel_journal_entry(self):
		"""On approval, post a DRAFT Journal Entry for the miscellaneous items:
		one credit (party) line per item, balanced by a debit to the company's
		travel expense account. The party account is taken from the Company."""
		if self.workflow_state != "Approved" or self.journal_entry:
			return

		misc = [m for m in self.get("miscellaneous_item", []) if flt(m.amount)]
		if not misc:
			return

		if not self.company:
			frappe.throw(_("Company is required to create the Journal Entry."))

		payable_account = frappe.db.get_value("Company", self.company, "travel_journal_account")
		if not payable_account:
			frappe.throw(
				_("Please set <b>Travel Journal Account</b> in the Accounts tab of {0}.").format(
					frappe.get_desk_link("Company", self.company)
				),
				title=_("Missing Travel Journal Account"),
			)

		expense_field = "domestic_travel_expense" if self.travel_type == "Domestic" else "international_travel_expense"
		expense_account = frappe.db.get_value("Company", self.company, expense_field)
		if not expense_account:
			frappe.throw(
				_("Please set the {0} Travel Expense account in {1}.").format(
					self.travel_type, frappe.get_desk_link("Company", self.company)
				),
				title=_("Missing Travel Expense Account"),
			)

		cost_center = self.cost_center or frappe.db.get_value("Employee", self.employee, "cost_center")
		conversion = flt(self.exchange_rate) or 1.0
		total = sum(flt(m.amount) for m in misc) * conversion

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.naming_series = "Journal Voucher"
		je.company = self.company
		je.posting_date = nowdate()
		je.branch = self.branch
		je.user_remark = _("Travel miscellaneous against {0}").format(self.name)

		# debit: travel expense (total)
		je.append("accounts", {
			"account": expense_account,
			"cost_center": cost_center,
			"debit_in_account_currency": total,
			"debit": total,
			"reference_type": "Travel Authorization",
			"reference_name": self.name,
		})

		# credit: one party line per miscellaneous item (e.g. 700, 800)
		for m in misc:
			amount = flt(m.amount) * conversion
			line = {
				"account": payable_account,
				"cost_center": cost_center,
				"credit_in_account_currency": amount,
				"credit": amount,
				"reference_type": "Travel Authorization",
				"reference_name": self.name,
			}
			if m.party_type == "Employee" and m.party:
				line["party_type"] = "Employee"
				line["party"] = m.party
			je.append("accounts", line)

		je.flags.ignore_permissions = 1
		je.insert()  # left as a draft (docstatus 0)

		self.db_set("journal_entry", je.name)
		frappe.msgprint(
			_("Draft {0} created for travel miscellaneous.").format(
				frappe.get_desk_link("Journal Entry", je.name)
			),
			alert=True,
		)

	def cancel_travel_journal_entry(self):
		if not self.journal_entry or not frappe.db.exists("Journal Entry", self.journal_entry):
			return
		docstatus = frappe.db.get_value("Journal Entry", self.journal_entry, "docstatus")
		if docstatus == 1:
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			je.cancel()
			frappe.msgprint(_("Journal Entry {0} cancelled.").format(self.journal_entry), alert=True)
		elif docstatus == 0:
			# still a draft — remove it so it isn't left orphaned
			frappe.delete_doc("Journal Entry", self.journal_entry, ignore_permissions=True)
			frappe.msgprint(_("Draft Journal Entry {0} deleted.").format(self.journal_entry), alert=True)
		self.db_set("journal_entry", None)

	def set_status(self, update=False):
		status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
		status = status_map.get(self.docstatus, "Unknown")

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def get_employee_travellers(self):
		return [d.party for d in self.get("travellers_detail", []) if d.party_type == "Employee" and d.party]

	def has_tagged_rows(self):
		return any(d.party for d in self.get("items", []))

	def rows_for_claimant(self, employee, table="items"):
		"""Rows of `table` that belong to `employee`. The applicant also owns
		rows tagged to non-login travellers (party type Others) and, on legacy
		documents without traveller tags, the whole table."""
		rows = self.get(table, [])
		if not self.has_tagged_rows():
			return list(rows) if employee == self.employee else []

		out = []
		for d in rows:
			if d.party_type == "Employee" and d.party == employee:
				out.append(d)
			elif employee == self.employee and d.party_type == "MQDC":
				out.append(d)
		return out

	def sync_traveller_tags(self):
		"""Every itinerary/miscellaneous row must be tagged to a row in
		Travellers Detail. When no travellers are listed the rows implicitly
		belong to the applicant."""
		travellers = {}
		for d in self.get("travellers_detail", []):
			if d.party:
				travellers[(d.party_type, d.party)] = d

		for table, label in (("items", _("Travel Itinerary")), ("miscellaneous_item", _("Miscellaneous Item"))):
			for row in self.get(table, []):
				if not travellers:
					row.party_type = None
					row.party = None
					row.traveller_name = None
					continue

				if not row.party:
					frappe.throw(
						_("{0} Row #{1}: please select the Traveller this row belongs to.").format(label, row.idx),
						title=_("Missing Traveller"),
					)

				traveller = travellers.get((row.party_type, row.party))
				if not traveller:
					frappe.throw(
						_("{0} Row #{1}: Traveller {2} is not listed in Travellers Detail.").format(
							label, row.idx, frappe.bold(row.party)
						),
						title=_("Invalid Traveller"),
					)
				row.traveller_name = traveller.full_name

	def get_itinerary_groups(self):
		"""Itinerary rows grouped per traveller, preserving row order."""
		groups = {}
		for d in self.get("items", []):
			key = (d.party_type or "", d.party or "")
			groups.setdefault(key, []).append(d)
		return groups

	def filter_rows_for_traveller(self):
		"""A traveller (who is not the applicant, approver or an HR user) only
		sees their own itinerary and miscellaneous rows on the form."""
		if self.docstatus == 0 or self.is_new():
			return

		user = frappe.session.user
		if is_privileged(user) or user in (self.owner, self.approver):
			return

		employee = get_session_employee(user)
		if not employee or employee == self.employee:
			return

		if employee not in self.get_employee_travellers():
			return

		self.set("items", [d for d in self.get("items", []) if d.party_type == "Employee" and d.party == employee])
		self.set(
			"miscellaneous_item",
			[d for d in self.get("miscellaneous_item", []) if d.party_type == "Employee" and d.party == employee],
		)
		self.set(
			"travellers_detail",
			[d for d in self.get("travellers_detail", []) if d.party_type == "Employee" and d.party == employee],
		)

	def validate_travel_dates(self):
		for _key, items in self.get_itinerary_groups().items():
			self._validate_overlap_dates(items)
			for item in items:
				if cint(item.halt):
					self._validate_halt_entry(item)
				else:
					self._validate_travel_entry(item)

	def _validate_overlap_dates(self, items):
		sorted_itinerary = sorted(items, key=lambda x: x.from_date)

		for i in range(len(sorted_itinerary)):
			current_item = sorted_itinerary[i]

			if current_item.from_date and current_item.to_date:
				if current_item.from_date > current_item.to_date:
					frappe.throw(
						f"Row {current_item.idx}: From Date cannot be after To Date",
						title="Invalid Date Range"
					)

			if i < len(sorted_itinerary) - 1:
				next_item = sorted_itinerary[i + 1]

				if not (current_item.to_date and next_item.from_date):
					continue

				required_next_date = frappe.utils.add_days(current_item.to_date, 1)

				if next_item.from_date != required_next_date:
					frappe.throw(
						f"Row {next_item.idx}: From Date must be exactly 1 day after Row {current_item.idx}'s To Date. "
						f"Expected {required_next_date}, found {next_item.from_date}",
						title="Invalid Date Sequence"
					)

	def _validate_halt_entry(self, item):
		if not item.halt_at:
			frappe.throw(
				_("Row#{}: <b>Halt at</b> is mandatory.").format(item.idx),
				title="Missing Halt Information"
			)
		if not item.to_date:
			frappe.throw(
				_("Row#{0}: <b>To Date</b> is mandatory.").format(item.idx),
				title="Invalid Date"
			)
		if item.to_date < item.from_date:
			frappe.throw(
				_("Row#{0}: <b>To Date</b> cannot be earlier than <b>From Date</b>.").format(item.idx),
				title="Invalid Date"
			)

	def _validate_travel_entry(self, item):
		if not (item.travel_from and item.travel_to):
			frappe.throw(
				_("Row#{0}: <b>Travel From</b> and <b>Travel To</b> are mandatory.").format(item.idx),
				title="Missing Travel Information"
			)
		item.to_date = item.from_date  # Ensuring `to_date` is set for non-halt cases

	def validate_duplicate_entry(self):
		for (party_type, party), items in self.get_itinerary_groups().items():
			if party_type == "MQDC" or not items:
				continue

			employee = party or self.employee
			from_date = min(d.from_date for d in items)
			to_date = max((d.to_date or d.from_date) for d in items)

			overlaps = frappe.db.sql(
				"""
				SELECT t2.idx, t1.name AS authorization_name, t2.from_date, t2.to_date
				FROM `tabTravel Authorization` t1
				JOIN `tabTravel Authorization Item` t2 ON t2.parent = t1.name
				WHERE
					t1.docstatus != 2
					AND t1.workflow_state != 'Rejected'
					AND t1.name != %(name)s
					AND (
						(t2.party_type = 'Employee' AND t2.party = %(employee)s)
						OR (COALESCE(t2.party, '') = '' AND t1.employee = %(employee)s)
					)
					AND t2.from_date <= %(to_date)s
					AND t2.to_date >= %(from_date)s
				""",
				{"name": self.name, "employee": employee, "from_date": from_date, "to_date": to_date},
				as_dict=True,
			)

			if overlaps:
				t = overlaps[0]
				frappe.throw(
					_("Traveller {0}: this request overlaps with {1} ({2} to {3}).").format(
						frappe.bold(employee),
						frappe.get_desk_link("Travel Authorization", t.authorization_name),
						t.from_date,
						t.to_date
					),
					title=_("Duplicate Travel Entry")
				)

	def validate_travel_last_day(self):
		for _key, items in self.get_itinerary_groups().items():
			for item in items:
				item.is_last_day = 0
			if len(items) > 1:
				items[-1].is_last_day = 1

	def validate_exchange_rate(self):
		if not self.exchange_rate and self.travel_type != 'Domestic':
			frappe.throw(_("Exchange Rate cannot be zero."), title="Missing Exchange Rate")

	@frappe.whitelist()
	def has_travel_claim(self) -> dict[str, bool]:
		filters = {"docstatus": ("<", 2), "travel_authorization": self.name}

		employee = get_session_employee()
		if employee and (employee == self.employee or employee in self.get_employee_travellers()):
			filters["employee"] = employee

		return {
			"has_travel_claim": bool(frappe.db.exists("Travel Claim", filters))
		}


def get_claimant_employee(doc):
	"""The employee the session user may claim/take an advance for on this
	Travel Authorization. Privileged users act for the applicant."""
	employee = get_session_employee()
	if employee and (employee == doc.employee or employee in doc.get_employee_travellers()):
		return employee

	if is_privileged():
		return doc.employee

	frappe.throw(
		_("You are not listed as a traveller on {0}.").format(doc.name),
		frappe.PermissionError,
		title=_("Not a Traveller"),
	)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	if is_privileged(user):
		return None

	conditions = [
		"`tabTravel Authorization`.owner = {user}".format(user=frappe.db.escape(user)),
		"`tabTravel Authorization`.approver = {user}".format(user=frappe.db.escape(user)),
	]

	employee = get_session_employee(user)
	if employee:
		emp = frappe.db.escape(employee)
		conditions.append("`tabTravel Authorization`.employee = {emp}".format(emp=emp))
		conditions.append(
			"""`tabTravel Authorization`.name in (
				select `parent` from `tabTravellers Item`
				where `parenttype` = 'Travel Authorization'
					and `party_type` = 'Employee'
					and `party` = {emp})""".format(emp=emp)
		)

	return "({})".format(" or ".join(conditions))


def has_permission(doc, ptype, user):
	if is_privileged(user):
		return True
	if not doc or doc.is_new():
		return True
	if user in (doc.owner, doc.approver):
		return True

	employee = get_session_employee(user)
	if employee and employee == doc.employee:
		return True

	# other travellers get read-only access
	if ptype in ("read", "print", "email", "select") and employee:
		return bool(
			frappe.db.exists(
				"Travellers Item",
				{
					"parenttype": "Travel Authorization",
					"parent": doc.name,
					"party_type": "Employee",
					"party": employee,
				},
			)
		)

	return False
