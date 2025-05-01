# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}
	columns, data = [], []
	data = get_data(filters)
	if not data:
		return columns, data
	columns = get_columns(data)
	return columns, data

def get_columns(data):
	columns = [
		_("Employee") + ":Link/Employee:80", 
		_("Employee Name") + ":Data:140", 
		_("CID") + ":Data:120", 
		_("Designation") + ":Link/Designation:120",
		_("Loan Type") + ":Data:140", 
		_("Loan From") + ":Data:160", 
		_("Account No") + ":Data:140",  
		_("Deduction Amount") + ":Currency:140", 
		_("Total Deductible Amount") + ":Currency:170", 
		_("Balance Amount") + ":Currency:140",
		_("Company") + ":Link/Company:120", 
		_("Cost Center") + ":Link/Cost Center:120", 
		_("Branch") + ":Link/Branch:120", 
		_("Department") + ":Link/Department:120",
		_("Division") + ":Link/Department:120", 
		_("Section") + ":Link/Department:120", 
		_("Year") + ":Data:80", 
		_("Month") + ":Data:80"
	]
	return columns

def get_data(filters):
	conditions, filters = get_conditions(filters)

	data = frappe.db.sql("""
		select t1.employee, t3.employee_name, t3.passport_number, t1.designation,
			t2.reference_type, t2.institution_name, t2.reference_number, t2.amount, t2.total_deductible_amount, t2.total_outstanding_amount,
			t1.company, t1.cost_center, t1.branch, t1.department, t1.devision, t1.section,
			t1.fiscal_year, t1.month
		from `tabSalary Slip` t1, `tabSalary Detail` t2, `tabEmployee` t3
		where t1.docstatus = 1 {}
		and t3.employee = t1.employee
		and t2.parent = t1.name
		and t2.parentfield = 'deductions'
		and case when t2.institution_name = 'RICBL' then t2.reference_type like '%loan%' else 1 = 1 end
		and exists
			(select 1
				from `tabSalary Component` sc
				where sc.name = t2.salary_component
			)
		and t2.reference_type != 'NULL'
	""".format(conditions))
	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("month"):
		month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
			"Dec"].index(filters["month"]) + 1
		filters["month"] = month
		conditions += " and t1.month = {}".format(filters.get("month"))
	
	if filters.get("fiscal_year"): conditions += " and t1.fiscal_year = {}".format(filters.get("fiscal_year"))
	if filters.get("company"): conditions += " and t1.company = '{}'".format(filters.get("company"))
	if filters.get("employee"): conditions += " and t1.employee = '{}'".format(filters.get("employee"))
	if filters.get("bank"): conditions += "and t2.institution_name = '{0}'".format(filters.bank)
	if filters.get("cost_center"): conditions += " and exists(select 1 from `tabCost Center` cc where t1.cost_center = cc.name and (cc.parent_cost_center = '{0}' or cc.name = '{0}'))".format(filters.cost_center)

	return conditions, filters
