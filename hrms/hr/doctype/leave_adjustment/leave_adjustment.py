# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from frappe.model.document import Document
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from datetime import datetime
from hrms.hr.doctype.leave_application.leave_application \
	import get_leave_balance_on, get_leaves_for_period

class LeaveAdjustment(Document):
	def validate(self):
		self.calculate_difference()

	def check_mandatory(self):
		if not self.adjustment_date:
			frappe.throw("Adjustment Date is Mandatory")
		if not self.leave_type:
			frappe.throw("Leave Type is Mandatory")

	# def validate_leave_balance(self):
	# 	self.check_mandatory()
	# 	for a in self.items:
	# 		a.leave_balance = get_leave_balance_on(a.employee, self.leave_type, self.adjustment_date)
	# 		a.difference = flt(a.leave_balance) - flt(a.actual_balance)

	def on_submit(self):
		# self.validate_leave_balance()
		self.adjust_leave()

	def before_cancel(self):
		lle = frappe.db.sql("""
			select name from `tabLeave Ledger Entry` where leave_adjustment_id = '{}'
		""".format(self.name), as_dict = 1)
		if lle:
			for a in lle:
				frappe.db.sql("""
					update `tabLeave Ledger Entry` set leave_adjustment_id = NULL where name = '{}'
				""".format(a.name))

	def on_cancel(self):
		self.adjust_leave(1)

	def adjust_leave(self, cancel=0):
		#le = get_le_settings()#Commented by SHIV on 2018/10/16
		for a in self.items:
			if flt(a.difference) == 0:
				pass
			else:
				le = frappe.get_doc("Employee Group",frappe.db.get_value("Employee",a.employee,"employee_group")) # Line added by SHIV on 2018/10/16
				las = frappe.db.sql("select name from `tabLeave Allocation` where employee = %s and leave_type = %s and to_date >= %s and YEAR(from_date) = %s and docstatus = 1", (a.employee, self.leave_type, self.adjustment_date, self.adjustment_date), as_dict=True)
				# if flt(a.actual_balance) > flt(le.encashment_lapse):
				# 	a.actual_balance = flt(le.encashment_lapse)
				# 	a.difference = flt(a.leave_balance) - flt(a.actual_balance)
				for l in las:
					if l.name != None:
						doc = frappe.get_doc("Leave Allocation", l.name)
						# carry_forwarded = flt(doc.carry_forwarded_leaves_count) - flt(a.difference)
						# balance = flt(doc.new_leaves_allocated) - flt(a.difference)
						balance = flt(a.actual_balance)
						leaves = -1*(a.difference)
						if cancel:
							# carry_forwarded = flt(doc.carry_forwarded_leaves_count) + flt(a.difference)
							# balance = flt(doc.new_leaves_allocated) + flt(a.difference)
							balance = a.leave_balance
							leaves = a.difference
						# if flt(carry_forwarded) > flt(le.encashment_lapse):
						# 	carry_forwarded = le.encashment_lapse
						# if flt(balance) > flt(le.encashment_lapse):
						# 	balance = le.encashment_lapse
							
						# doc.db_set("carry_forwarded_leaves_count", carry_forwarded)
						doc.db_set("new_leaves_allocated", balance)

						self.create_additional_leave_ledger_entry(doc, leaves, self.adjustment_date, adjusted_leave = 1, adjustment_id = self.name)

	def create_additional_leave_ledger_entry(self, allocation, leaves, date, adjusted_leave = 0, adjustment_id = None):
		''' Create leave ledger entry for leave types '''
		allocation.new_leaves_allocated = leaves
		allocation.from_date = date
		allocation.unused_leaves = 0
		if self.docstatus != 2:
			allocation.create_leave_ledger_entry(is_adjusted_leave=adjusted_leave, leave_adjustment = adjustment_id)
		else:
			allocation.create_leave_ledger_entry(is_adjusted_leave=adjusted_leave, leave_adjustment = None)

	def calculate_difference(self):
		for a in self.items:
			a.difference = flt(a.leave_balance) - flt(a.actual_balance)

	@frappe.whitelist
	def get_leave_type_info(self, actual_balance):
		if not self.leave_type:
			frappe.throw("Please select Leave Type first")
			if int(frappe.db.get_value("Leave Type",self.leave_type,"allow_negative")) == 0 and flt(actual_balance) < 0:
				frappe.throw("Negative Balance is not allowed for leave type {}".format(self.leave_type))

	@frappe.whitelist()
	def get_employees(self):
		self.check_mandatory()
		query = "select name as employee, employee_name from tabEmployee where status = 'Active' and date_of_joining <= %s"
		if self.branch:
			query += " and branch = \'"+str(self.branch)+"\'"

		entries = frappe.db.sql(query, self.adjustment_date, as_dict=True)
		self.set('items', [])

		for d in entries:
			# max_el = frappe.db.get_value("Employee Group", frappe.db.get_value("Employee",d.employee,"employee_group"), "encashment_lapse")
			ledger_entries = self.get_leave_ledger_entries(datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date, d.employee, self.leave_type)
			adjusted_entries = get_adjusted_leave_ledger_entries(datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date, d.employee, self.leave_type)
			opening = get_leave_balance_on(d.employee, self.leave_type, self.adjustment_date)
			#Leaves Deducted consist of both expired and leaves taken
			leaves_deducted = get_leaves_for_period(d.employee, self.leave_type,
			datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date) * -1
			leaves_taken = leaves_deducted - remove_expired_leave(ledger_entries)
			# frappe.msgprint(str(d.employee)+" "+str(leaves_taken))
			total_allocation, expired_allocation = get_allocated_and_expired_leaves(ledger_entries, datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date)
			leaves_adjusted = get_leaves_adjusted(adjusted_entries, datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date)

			closing = max(total_allocation - (leaves_taken) + leaves_adjusted, 0)
			# frappe.msgprint(str(closing)+" = "+ str(total_allocation)+" - "+str(leaves_taken)+" + "+str(leaves_adjusted))
			# if self.leave_type == "Earned Leave":
			# 	# frappe.msgprint(str(employee))
			# 	if flt(total_allocation) > flt(max_el):
			# 		total_allocation = flt(max_el)
			# 	if flt(closing) > flt(max_el):
			# 		closing = flt(max_el)
			d.leave_balance = closing
			d.actual_balance = closing
			d.difference = 0
			row = self.append('items', {})
			row.update(d)
			
	@frappe.whitelist()
	def get_employee_details(self, employee):
		if not self.adjustment_date:
			frappe.throw("Please set Adjustment Date")
		if not self.leave_type:
			frappe.throw("Please set Leave Type")
		# max_el = frappe.db.get_value("Employee Group", frappe.db.get_value("Employee",employee,"employee_group"), "encashment_lapse")
		ledger_entries = self.get_leave_ledger_entries(datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date, employee, self.leave_type)
		adjusted_entries = get_adjusted_leave_ledger_entries(datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date, employee, self.leave_type)
		opening = get_leave_balance_on(employee, self.leave_type, self.adjustment_date)
		#Leaves Deducted consist of both expired and leaves taken
		leaves_deducted = get_leaves_for_period(employee, self.leave_type,
		datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date) * -1
		leaves_taken = leaves_deducted - remove_expired_leave(ledger_entries)
		# frappe.msgprint(str(d.employee)+" "+str(leaves_taken))
		total_allocation, expired_allocation = get_allocated_and_expired_leaves(ledger_entries, datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date)
		leaves_adjusted = get_leaves_adjusted(adjusted_entries, datetime.strptime(str(self.adjustment_date).split("-")[0]+"-01-01","%Y-%m-%d"), self.adjustment_date)
		closing = max(total_allocation - (leaves_taken) + leaves_adjusted, 0)
		# frappe.msgprint(str(closing)+" = "+ str(total_allocation)+" - "+str(leaves_taken)+" + "+str(leaves_adjusted))
		# if self.leave_type == "Earned Leave":
		# 	# frappe.msgprint(str(employee))
		# 	if flt(total_allocation) > flt(max_el):
		# 		total_allocation = flt(max_el)
		# 	if flt(closing) > flt(max_el):
		# 		closing = flt(max_el)
		return closing, 0

	def get_leave_ledger_entries(self, from_date, to_date, employee, leave_type):
		records= frappe.db.sql("""
		SELECT
			employee, leave_type, from_date, to_date, leaves, transaction_name, transaction_type,
			is_carry_forward, is_expired
		FROM `tabLeave Ledger Entry`
		WHERE employee=%(employee)s AND leave_type=%(leave_type)s
			AND docstatus=1
			AND (from_date between %(from_date)s AND %(to_date)s
				OR to_date between %(from_date)s AND %(to_date)s
				OR (from_date < %(from_date)s AND to_date > %(to_date)s))
		and is_adjusted_leave = 0
		""", {
			"from_date": from_date,
			"to_date": to_date,
			"employee": employee,
			"leave_type": leave_type
		}, as_dict=1)
		return records

def get_adjusted_leave_ledger_entries(from_date, to_date, employee, leave_type):
	records= frappe.db.sql("""
		SELECT
			employee, leave_type, from_date, to_date, leaves, transaction_name, transaction_type,
			is_carry_forward, is_expired
		FROM `tabLeave Ledger Entry`
		WHERE employee=%(employee)s AND leave_type=%(leave_type)s
			AND docstatus=1
			AND (from_date between %(from_date)s AND %(to_date)s
				OR to_date between %(from_date)s AND %(to_date)s
				OR (from_date < %(from_date)s AND to_date > %(to_date)s))
		AND is_adjusted_leave = 1
	""", {
		"from_date": from_date,
		"to_date": to_date,
		"employee": employee,
		"leave_type": leave_type
	}, as_dict=1)
	# frappe.msgprint(str(records))
	return records

def get_leaves_adjusted(records, from_date, to_date):

	from frappe.utils import getdate

	new_allocation = 0
	expired_leaves = 0

	for record in records:
		# if record.to_date <= getdate(to_date) and record.leaves>0:
		# 	expired_leaves += record.leaves
		if record.from_date >= getdate(from_date):
			new_allocation += record.leaves

	return new_allocation

def get_allocated_and_expired_leaves(records, from_date, to_date):

	from frappe.utils import getdate

	new_allocation = 0
	expired_leaves = 0
	for record in records:
		if record.to_date <= getdate(to_date) and record.leaves>0:
			expired_leaves += record.leaves

		if record.from_date >= getdate(from_date):
			if record.leaves > 0:
				new_allocation += record.leaves
			elif record.is_expired == 0 and record.transaction_type == "Leave Allocation":
				new_allocation += record.leaves if record.leaves else 0

	return new_allocation, expired_leaves

def remove_expired_leave(records):
	expired_within_period = 0
	for record in records:
		if record.is_expired:
			expired_within_period += record.leaves
	return expired_within_period * -1

