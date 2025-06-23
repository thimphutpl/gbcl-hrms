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

class TravelAuthorization(Document):
	def validate(self):
		validate_active_employee(self.employee)
		self.validate_travel_dates()
		self.validate_travel_last_day()
		self.validate_exchange_rate()
		self.set_status()
		# validate_workflow_states(self)

	def on_update(self):
		self.validate_duplicate_entry()

	def on_cancel(self):
		self.set_status(update=True)

	def set_status(self, update=False):
		status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
		status = status_map.get(self.docstatus, "Unknown")

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def validate_travel_dates(self):
		self._validate_overlap_dates()
		for item in self.get("items", []):
			if cint(item.halt):
				self._validate_halt_entry(item)
			else:
				self._validate_travel_entry(item)

	def _validate_overlap_dates(self):
		sorted_itinerary = sorted(self.items, key=lambda x: x.from_date)
		
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
		duplicate_query = """
			SELECT 
				t3.idx, 
				t1.name AS authorization_name, 
				t2.from_date, 
				t2.to_date 
			FROM `tabTravel Authorization` t1
			JOIN `tabTravel Authorization Item` t2 ON t2.parent = t1.name
			JOIN `tabTravel Authorization Item` t3 ON t3.parent = %s
			WHERE 
				t1.employee = %s
				AND t1.docstatus != 2
				AND t1.workflow_state != 'Rejected'
				AND t1.name != %s
				AND t2.from_date <= t3.to_date
				AND t2.to_date >= t3.from_date
		"""

		overlaps = frappe.db.sql(duplicate_query, (self.name, self.employee, self.name), as_dict=True)

		if overlaps:
			t = overlaps[0]
			frappe.throw(
				_("Row #{}: This request overlaps with {} ({} to {}).").format(
					t.idx, 
					frappe.get_desk_link("Travel Authorization", t.authorization_name), 
					t.from_date, 
					t.to_date
				),
				title=_("Duplicate Travel Entry")
			)

	def validate_travel_last_day(self):
		items = self.get("items", [])
		if len(items) > 1:
			for item in items:
				item.is_last_day = 0
			items[-1].is_last_day = 1

	def validate_exchange_rate(self):
		if not self.exchange_rate and self.travel_type != 'Domestic':
			frappe.throw(_("Exchange Rate cannot be zero."), title="Missing Exchange Rate")

	@frappe.whitelist()
	def has_travel_claim(self) -> dict[str, bool]:
		ta = frappe.qb.DocType("Travel Claim")

		travel_claim = (
			frappe.qb.from_(ta)
			.select(ta.name)
			.where(
				(ta.docstatus < 2)
				& (ta.travel_authorization == self.name)
			)
		).run(as_dict=True)

		return {
			"has_travel_claim": bool(travel_claim)
		}
