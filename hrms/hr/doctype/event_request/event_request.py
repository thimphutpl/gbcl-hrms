# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

import erpnext

from hrms.hr.utils import set_employee_name, validate_active_employee

# Event Request workflow (see the "Event Request" Workflow doc): Employee
# submits -> Director verifies -> CFO approves. This mirrors Travel
# Authorization exactly: no Journal Entry here -- that only happens when
# the resulting Event Claim is approved. Director has full oversight of
# every request regardless of status; CFO only needs to see requests
# currently awaiting their own approval.
PRIVILEGED_ROLES = {"System Manager", "HR Manager", "HR User"}
DIRECTOR_ROLE = "Director"
CFO_ROLE = "CFO"
CFO_PENDING_STATE = "Waiting Approval"


def is_privileged(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


def can_view_all_events(user=None):
	"""Privileged HR roles plus Director may see every event request, any status."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool((PRIVILEGED_ROLES | {DIRECTOR_ROLE}) & set(frappe.get_roles(user)))


def is_cfo(user=None):
	user = user or frappe.session.user
	return CFO_ROLE in frappe.get_roles(user)


def get_session_employee(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


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

	def on_cancel(self):
		self.set_status(update=True)

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

	def set_status(self, update=False):
		status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
		status = status_map.get(self.docstatus, "Draft")

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def has_event_claim(self) -> dict[str, bool]:
		filters = {"docstatus": ("<", 2), "event_request": self.name}

		employee = get_session_employee()
		if employee and employee == self.employee:
			filters["employee"] = employee

		return {"has_event_claim": bool(frappe.db.exists("Event Claim", filters))}


@frappe.whitelist()
def has_event_claim(dt, dn) -> dict[str, bool]:
	"""Loaded fresh from the DB by (dt, dn) — see the matching comment on
	Travel Authorization's has_travel_claim for why."""
	doc = frappe.get_doc(dt, dn)
	doc.check_permission("read")
	return doc.has_event_claim()


def get_permission_query_conditions(user=None):
	"""List-view visibility.

	- Admin / HR / Director: see everything.
	- CFO: only requests currently awaiting CFO approval.
	- Everyone else (requesters): only their own requests.
	"""
	user = user or frappe.session.user
	if can_view_all_events(user):
		return None

	conditions = ["`tabEvent Request`.owner = {0}".format(frappe.db.escape(user))]

	if is_cfo(user):
		conditions.append(
			"`tabEvent Request`.workflow_state = {0}".format(frappe.db.escape(CFO_PENDING_STATE))
		)

	employee = get_session_employee(user)
	if employee:
		conditions.append("`tabEvent Request`.employee = {0}".format(frappe.db.escape(employee)))

	return "({0})".format(" or ".join(conditions))


def has_permission(doc, ptype, user):
	if can_view_all_events(user):
		return True
	if not doc or doc.is_new():
		return True
	if user == doc.owner:
		return True

	if is_cfo(user):
		# Only narrow READ-family visibility to the pending stage. Do NOT gate
		# write/submit this way — see the matching comment on Travel
		# Authorization's has_permission for why.
		if ptype in ("read", "print", "email", "select"):
			return doc.workflow_state == CFO_PENDING_STATE
		return True

	employee = get_session_employee(user)
	if employee and employee == doc.employee:
		return True

	return None
