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

# Travel Request workflow: Employee submits -> Director verifies -> CFO approves
# (no Journal Entry here; that only happens when the Travel Claim is approved).
# Director has full oversight of every request regardless of status; CFO only
# needs to see requests currently awaiting their approval.
DIRECTOR_ROLE = "Director"
CFO_ROLE = "CFO"
CFO_PENDING_STATE = "Waiting Approval"


def get_session_employee(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def is_privileged(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


def can_view_all_travel(user=None):
	"""Privileged HR roles plus Director may see every travel request, any status."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool((PRIVILEGED_ROLES | {DIRECTOR_ROLE}) & set(frappe.get_roles(user)))


def is_cfo(user=None):
	user = user or frappe.session.user
	return CFO_ROLE in frappe.get_roles(user)


class TravelAuthorization(Document):
	def onload(self):
		self.filter_rows_for_traveller()

	def validate(self):
		validate_active_employee(self.employee)
		self.validate_applicant_is_self()
		self.sync_traveller_tags()
		self.validate_travel_dates()
		self.validate_travel_last_day()
		self.validate_exchange_rate()
		self.calculate_miscellaneous_total()
		self.set_status()
		# validate_workflow_states(self)

	def validate_applicant_is_self(self):
		"""Applicant/Employee must always be the logged-in user, no exceptions —
		nobody, including HR/System Manager, may file (or reassign) a Travel
		Request on behalf of someone else. Only checked when the document is
		being created or the employee field is actually being changed — NOT on
		every subsequent save, otherwise a Director/CFO verifying or approving
		someone else's already-created request would be wrongly blocked. This
		is the real enforcement; the JS read-only lock is only a convenience on
		top of it. "Administrator" is exempt since that's the raw system
		account used for scripts/imports, not a person filing a request."""
		if frappe.session.user == "Administrator":
			return
		if not (self.is_new() or self.has_value_changed("employee")):
			return
		employee = get_session_employee()
		if employee and self.employee != employee:
			frappe.throw(
				_("You can only create a Travel Request for yourself."),
				frappe.PermissionError,
				title=_("Not Allowed"),
			)

	def on_update(self):
		self.validate_duplicate_entry()

	def on_cancel(self):
		self.set_status(update=True)

	def calculate_miscellaneous_total(self):
		# Skip only on a later save of an ALREADY-submitted doc (e.g. an
		# allow_on_submit field update) so a drifted recompute can't throw
		# "Cannot Update After Submit" on total_miscellaneous_amount_btn, which
		# is not allow_on_submit. Must NOT skip on self.docstatus == 1 alone --
		# Document.submit() sets docstatus to 1 *before* calling save(), so by
		# the time validate() runs during the actual submit action docstatus is
		# already 1; gating on that would skip the calculation on every
		# approval and the totals would never get computed at all.
		if getattr(self, "_action", None) == "update_after_submit":
			return
		rate = flt(self.exchange_rate) or 1
		for m in self.get("miscellaneous_item", []):
			m.amount_in_btn = flt(m.amount) * rate
		self.total_miscellaneous_amount = sum(flt(m.amount) for m in self.get("miscellaneous_item", []))
		self.total_miscellaneous_amount_btn = sum(flt(m.amount_in_btn) for m in self.get("miscellaneous_item", []))

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
		sees their own itinerary and miscellaneous rows on the form, at any
		stage — not just once docstatus reaches 1 (the two-step workflow keeps
		docstatus at 0 through both Waiting for Verification and Waiting
		Approval, so gating on docstatus alone would never filter for a
		pending request)."""
		if self.is_new():
			return

		user = frappe.session.user
		if can_view_all_travel(user) or user in (self.owner, self.approver):
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

	def has_travel_claim(self) -> dict[str, bool]:
		filters = {"docstatus": ("<", 2), "travel_authorization": self.name}

		employee = get_session_employee()
		if employee and (employee == self.employee or employee in self.get_employee_travellers()):
			filters["employee"] = employee

		return {
			"has_travel_claim": bool(frappe.db.exists("Travel Claim", filters))
		}


@frappe.whitelist()
def has_travel_claim(dt, dn) -> dict[str, bool]:
	"""Loaded fresh from the DB by (dt, dn) rather than called as a bound
	document method on the client's in-memory copy of the doc. `frm.call()`
	with a plain method name round-trips the client's own copy of the
	document through `run_doc_method`, which reconstructs a Document from
	that JSON and runs `check_if_latest()` -> for an already-submitted
	document this always demands 'submit' permission, regardless of what
	the called method actually needs -- wrongly blocking a read-only
	traveller who is just viewing an approved request."""
	doc = frappe.get_doc(dt, dn)
	doc.check_permission("read")
	return doc.has_travel_claim()


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
	if can_view_all_travel(user):
		return None

	conditions = [
		"`tabTravel Authorization`.owner = {user}".format(user=frappe.db.escape(user)),
		"`tabTravel Authorization`.approver = {user}".format(user=frappe.db.escape(user)),
	]

	if is_cfo(user):
		conditions.append(
			"`tabTravel Authorization`.workflow_state = {state}".format(state=frappe.db.escape(CFO_PENDING_STATE))
		)

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
	if can_view_all_travel(user):
		return True
	if not doc or doc.is_new():
		return True
	if user in (doc.owner, doc.approver):
		return True

	if is_cfo(user):
		# Only narrow READ-family visibility to the pending stage. Do NOT gate
		# write/submit this way: apply_workflow() sets workflow_state to the
		# *next* state before calling doc.submit(), so by the time a write
		# permission check runs here the state has already moved past
		# CFO_PENDING_STATE. Frappe's own transition engine (transition.allowed
		# in get_transitions) already restricts who can perform which action,
		# independently and before any state mutation, so this is safe.
		if ptype in ("read", "print", "email", "select"):
			return doc.workflow_state == CFO_PENDING_STATE
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
