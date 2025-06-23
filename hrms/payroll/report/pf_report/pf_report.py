# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _


def execute(filters=None):
	columns, data = [], []
	columns = get_columns(data)
	queries = construct_query(filters)
	data = get_data(queries, filters)

	return columns, data

def get_columns(data):
	return [
		{
			"fieldname": "employee",
			"label": "Employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 150
		},
		{
			"fieldname": "employee_name",
			"label": "Employee Name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "designation",
			"label": "Designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 120
		},
		{
			"fieldname": "employement_type",
			"label": "Employment Type",
			"fieldtype": "Data",
			"width":100
		},
		{
			"fieldname": "cid",
			"label": "CID",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "pf_number",
			"label": "PF Number",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "basic_pay",
			"label": "Basic Pay",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "employee_pf",
			"label": "Employee PF",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "employer_pf",
			"label": "Employer PF",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "total",
			"label": "Total",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "company",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120
		},
		{
			"fieldname": "cost_center",
			"label": "Cost Center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 120
		},
		{
			"fieldname": "branch",
			"label": "Branch",
			"fieldtype": "Link",
			"options": "Branch",
			"width": 120
		},
		{
			"fieldname": "department",
			"label": "Department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 120
		},
		{
			"fieldname": "division",
			"label": "Division",
			"fieldtype": "Link",
			"options": "Department",
			"width": 120
		},
		{
			"fieldname": "section",
			"label": "Section",
			"fieldtype": "Link",
			"options": "Department",
			"width": 120
		},
		{
			"fieldname": "year",
			"label": "Year",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"fieldname": "month",
			"label": "Month",
			"fieldtype": "Data",
			"width": 80
		},

	]
def construct_query(filters):
	conditions, filters = get_conditions(filters)
	query =("""
			select t1.employee as employee, t3.employee_name as employee_name, t1.designation as designation,  t3.passport_number as passport_number, t3.pf_number as pf_number,
				sum(case when t2.salary_component = 'Basic Pay' then ifnull(t2.amount,0) else 0 end) as basicpay,
				sum(case when t2.salary_component = 'PF' then ifnull(t2.amount,0) else 0 end) as employeepf,
				sum(case when t2.salary_component = 'PF' then ifnull(t2.amount,0) else 0 end) as employerpf,
				sum(case when t2.salary_component = 'PF' then ifnull(t2.amount,0)*2 else 0 end) as total,
				t1.company as company, t1.branch as branch, t1.cost_center as cost_center, t1.department as department,  t1.section as section,
				t1.fiscal_year as fiscal_year, t1.month as month
			from `tabSalary Slip` t1, `tabSalary Detail` t2, `tabEmployee` t3
			where t1.docstatus = 1 
			and t3.employee = t1.employee
			and t2.parent = t1.name
			and t2.salary_component in ('Basic Pay','PF')
			{0}
			group by t1.employee, t3.employee_name, t1.designation, t3.passport_number,
					t1.company, t1.branch, t1.department,  
					t1.fiscal_year, t1.month
			""".format(conditions))
	return query
def get_data(query, filters):
	conditions = ""
	data = []
	datas = frappe.db.sql(query, as_dict=True)
	for d in datas:
		if d.total > 0:
			# frappe.msgprint(str(d.employeepf))
			row = {
				"employee":d.employee,
				"employee_name":d.employee_name,
				"designation":	d.designation,
				"employement_type": d.employment_type,
				"cid": d.passport_number,
				"pf_number": d.pf_number,
				"basic_pay": d.basicpay,
				"employee_pf":d.employeepf,
				"employer_pf": d.employerpf,
				"total":d.total,
				"company":d.company,
				"cost_center":d.cost_center,
				"beanch":	d.branch,
				"department": d.department,
				"division": d.division,
				"section": d.section,
				"year": d.fiscal_year,
				"month":d.month
			}
			data.append(row)
	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("fiscal_year"): 
		conditions += """and t1.fiscal_year = '{}'""".format(filters.get("fiscal_year"))
	if filters.get("month"):
		# month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(filters["month"]) + 1
		# filters["month"] = month
		conditions += """and t1.month = '{}'""".format(filters.get("month"))
	if filters.get("employee"): 
		conditions += """and t1.employee ='{}'""".format(filters.get("employee"))
	# if filters.get("employment_type"): 
	# 	conditions += """and t1.employment_type = '{}'""".format(filters.get("employment_type"))
	if filters.get("cost_center"): 
		conditions += """and exists(select 1 from `tabCost Center` cc where t1.cost_center = cc.name and (cc.parent_cost_center = '{0}' or cc.name = '{0}'))""".format(filters.cost_center)
	if filters.get("company"): 
		conditions += """and t1.company = '{}'""".format(filters.get("company"))
	return conditions, filters