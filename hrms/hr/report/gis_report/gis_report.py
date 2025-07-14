# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _


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
		_("Employee") + ":Link/Employee:100",
		_("Employee Name") + "::140",
		_("Designation") + ":Link/Designation:120",
		_("CID") + "::110",
		_("Date Of Birth") + "::100",
		_("Date Of Joining") + "::100",
		_("Group") + "::100",
		_("Grade") + "::60",
		_("GIS Number") + "::100",
		_("Policy Number") + "::100",
		_("Basic Pay") + ":Currency:120",
		_("GIS Contribution") + ":Currency:120",
		_("Company") + ":Link/Branch:120",
		_("Cost Center") + ":Link/Cost Center:120",
		_("Branch") + ":Link/Branch:120",
		_("Department") + ":Link/Department:120",
		_("Division") + ":Data:120",
		_("Section") + ":Data:120",
		_("Year") + "::80",
		_("Month") + "::80"
	]
	return columns

def get_data(filters):
	conditions, filters = get_conditions(filters)
	data = frappe.db.sql("""select 
				t1.employee as n, t3.employee_name, t1.designation, t3.passport_number, 
				t3.date_of_birth, t3.date_of_joining, t3.employee_group, t1.gis_number, t1.gis_policy_number,
				sum(case when t2.salary_component = 'Basic Pay' then ifnull(t2.amount,0) else 0 end) as basicpay,
				sum(case when t2.salary_component = 'GIS' then ifnull(t2.amount,0) else 0 end) as gisamount,
							t1.company, t1.branch, t1.cost_center, t1.department, t1.section,t1.fiscal_year, t1.month
						from `tabSalary Slip` t1, `tabSalary Detail` t2, `tabEmployee` t3
						where t1.docstatus = 1 %s
					  	and t3.employee_group !='Temporary'
						and t3.employee = t1.employee
						and t2.parent = t1.name
						and t2.salary_component in ('Basic Pay','GIS')
						group by t1.employee, t3.employee_name, t1.designation, t3.passport_number,  t3.gis_number, 
				t1.company, t1.branch, t1.department, t1.section, t1.fiscal_year, t1.month
				""" % conditions, filters)
	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("month"):
		month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
			"Dec"].index(filters["month"]) + 1
		filters["month"] = month
		conditions += " and t1.month = %(month)s"

	if filters.get("fiscal_year"): conditions += " and t1.fiscal_year = %(fiscal_year)s"
	if filters.get("company"): conditions += " and t1.company = %(company)s"
	if filters.get("employee"): 
		conditions += " and t1.employee = %(employee)s "
	if filters.get("cost_center"): conditions += " and exists(select 1 from `tabCost Center` cc where t1.cost_center = cc.name and (cc.parent_cost_center = '{0}' or cc.name = '{0}'))".format(filters.cost_center)
	return conditions, filters
