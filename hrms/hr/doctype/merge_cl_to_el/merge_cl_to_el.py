# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe import msgprint
from frappe.model.document import Document
from frappe.utils import flt, cint, nowdate, getdate, formatdate
from erpnext.accounts.utils import get_fiscal_year
from hrms.hr.doctype.leave_application.leave_application \
		import get_leave_allocation_records, get_leave_balance_on, get_approved_leaves_for_period
from frappe.utils import getdate, get_first_day, get_last_day, flt
from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import create_leave_ledger_entry

class MergeCLToEL(Document):
	def validate(self):
		self.validate_duplicate()
		# self.get_data()

	def validate_duplicate(self):
		current_fiscal_year = get_fiscal_year(getdate(nowdate()), company=self.company)[0]
		query = """select name from `tabMerge CL To EL` where docstatus != 2 and fiscal_year = '{0}' and name != '{1}' and job_type='{2}'
			""".format(self.fiscal_year, self.name,self.job_type)
		if self.employee_type:
			query += " and employee_type = '{0}'".format(self.employee_type)
		if self.branch:
			query += " and branch = '{0}'".format(self.branch)
		doc = frappe.db.sql(query)

	def on_submit(self):
		self.create_leave_ledger_entries()

	def on_cancel(self):
		frappe.db.sql("""DELETE FROM `tabLeave Ledger Entry` WHERE `transaction_name`=%s """,(self.name))

	def create_leave_ledger_entries(self):
		year_start_date, year_end_date = frappe.db.get_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"]
		)

		for em in self.items:
			# Deduct Casual Leave
			self.create_leave_ledger_entry(
				employee = em.employee,
				employee_name = em.employee_name,
				leave_type = "Casual Leave",
				leave_balance= -1 * em.leave_balance,
				year_start_date = year_start_date,
				year_end_date = year_end_date,
			)

			# Add Earned Leave
			self.create_leave_ledger_entry(
				employee = em.employee,
				employee_name = em.employee_name,
				leave_type = "Earned Leave",
				leave_balance = em.leave_balance,
				year_start_date = year_start_date,
				year_end_date = year_end_date,
			)

	def create_leave_ledger_entry(self, employee, employee_name, leave_type, leave_balance, year_start_date, year_end_date):
		doc = frappe.new_doc("Leave Ledger Entry")
		doc.employee = employee
		doc.employee_name = employee_name
		doc.from_date = year_start_date
		doc.to_date = year_end_date
		doc.leave_type = leave_type
		doc.transaction_type = self.doctype
		doc.transaction_name = self.name
		doc.leaves = leave_balance
		doc.flags.ignore_validate = True
		doc.insert(ignore_permissions=True)
		doc.submit()

	@frappe.whitelist()		
	def get_data(self):
		if not self.fiscal_year:
			frappe.throw("Please select Fiscal Year.")

		year_start_date, year_end_date = frappe.db.get_value("Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"])
		if not year_start_date:
			frappe.throw(_("Fiscal Year {0} not found.").format(self.fiscal_year))
	
		from_date = get_first_day(getdate(year_start_date))
		to_date = get_last_day(getdate(year_end_date))
		employee = ''

		filters_dict = { "status": "Active", "company": self.company}
		if self.branch:
			filters_dict['branch'] = self.branch
		if self.job_type:
			filters_dict['job_type'] = self.job_type		
		# if self.employeement_type:
		# 	filters_dict['employee_type'] = self.employeement_type
		if self.employee:
			filters_dict['name'] = self.employee	

		active_employees = frappe.get_all("Employee",
			filters = filters_dict,
			fields = ["name", "employee_name", "department", "branch", "date_of_joining"])

		self.set('items', [])
		for employee in active_employees:
			#leaves allocated
			leaves_allocated = 0.0
			allocation = get_leave_allocation_records(employee=employee.name, date=to_date, leave_type=self.leave_type)
			
			if allocation:
				leaves_allocated = allocation[self.leave_type]['total_leaves_allocated']
			
			# leaves taken
			leaves_taken = get_approved_leaves_for_period(employee.name, self.leave_type,
				from_date, to_date)
			# closing balance
			employee_id = employee.name
			employee_name = employee.employee_name
			leave_balance = flt(leaves_allocated) - flt(leaves_taken)
			if leave_balance > 0:
				row = self.append('items', {})
				d = {'employee': employee_id, 'employee_name': employee_name,\
					'leaves_allocated': leaves_allocated, 'leaves_taken': round(leaves_taken,2), 'leave_balance': round(leave_balance,2)}
				row.update(d)

