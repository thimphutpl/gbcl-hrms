# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _


def execute(filters=None):
    if not filters:
        filters = {}
    
    data = get_data(filters)
    columns = get_columns()
    
    if not data:
        msgprint(_("No data found for the selected filters"))
        return columns, []
    
    return columns, data

def get_columns():
    columns = [
        {
            "label": _("Employee"), 
            "fieldname": "employee", 
            "fieldtype": "Link", 
            "options": "Employee", 
            "width": 80
        },
        {
            "label": _("Employee Name"), 
            "fieldname": "employee_name", 
            "width": 140
        },
        {
            "label": _("Designation"), 
            "fieldname": "designation", 
            "fieldtype": "Link", 
            "options": "Designation", 
            "width": 120
        },
        # {
        #     "label": _("CID"), 
        #     "fieldname": "passport_number", 
        #     "width": 120
        # },
        {
            "label": _("TPN#"), 
            "fieldname": "tpn_number", 
            "width": 80
        },
        {
            "label": _("Basic Salary"), 
            "fieldname": "basicpay", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Allowances"), 
            "fieldname": "allowances", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Arrears"), 
            "fieldname": "arrears", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Gross Salary(A)"), 
            "fieldname": "grosspay", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("PF Amount(B)"), 
            "fieldname": "pfamount", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("GIS Amount(C)"), 
            "fieldname": "gisamount", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Net Salary(A-(B+C))"), 
            "fieldname": "netpay", 
            "fieldtype": "Currency", 
            "width": 140
        },
        {
            "label": _("Salary Tax(X)"), 
            "fieldname": "salarytax", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Health Contr(Y)"), 
            "fieldname": "healthcont", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Total(X+Y)"), 
            "fieldname": "total", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "label": _("Company"), 
            "fieldname": "company", 
            "fieldtype": "Link", 
            "options": "Company", 
            "width": 120
        },
        {
            "label": _("Cost Center"), 
            "fieldname": "cost_center", 
            "fieldtype": "Link", 
            "options": "Cost Center", 
            "width": 120
        },
        {
            "label": _("Branch"), 
            "fieldname": "branch", 
            "fieldtype": "Link", 
            "options": "Branch", 
            "width": 120
        },
        {
            "label": _("Department"), 
            "fieldname": "department", 
            "fieldtype": "Link", 
            "options": "Department", 
            "width": 120
        },
        # {
        #     "label": _("Section"), 
        #     "fieldname": "section", 
        #     "fieldtype": "Link", 
        #     "options": "Department", 
        #     "width": 120
        # },
        {
            "label": _("Year"), 
            "fieldname": "fiscal_year", 
            "width": 80
        },
        {
            "label": _("Month"), 
            "fieldname": "month", 
            "width": 80
        }
    ]
    return columns

def get_data(filters):
    conditions, filters = get_conditions(filters)
    
    try:
        data = frappe.db.sql("""
            select 
                t1.employee, 
                t3.employee_name, 
                t1.designation, 
                t3.passport_number, 
                t3.tpn_number,
                sum(case when t2.salary_component = 'Basic Pay' then ifnull(t2.amount,0) else 0 end) as basicpay,
                sum(case when t2.parentfield = 'earnings'
                     then (case when t2.salary_component = 'Basic Pay' then 0
                            when t2.salary_component = 'Salary  Arrears' then 0
                           else ifnull(t2.amount,0) end)
                     else 0 end) as allowances,
                sum(case when t2.salary_component = 'Salary  Arrears' then ifnull(t2.amount,0) else 0 end) as arrears,
                sum(case when t2.parentfield = 'earnings' then ifnull(t2.amount,0) else 0 end) as grosspay,
                sum(case when t2.salary_component = 'PF' then ifnull(t2.amount,0) else 0 end) as pfamount,
                sum(case when t2.salary_component = 'GIS' then ifnull(t2.amount,0) else 0 end) as gisamount,
                sum(
                   (case when t2.parentfield = 'earnings' then ifnull(t2.amount,0) else 0 end)
                   - (case when t2.salary_component = 'PF' then ifnull(t2.amount,0) else 0 end)
                   - (case when t2.salary_component = 'GIS' then ifnull(t2.amount,0) else 0 end)
                ) as netpay,
                sum(case when t2.salary_component = 'Salary Tax' then ifnull(t2.amount,0) else 0 end) as salarytax,
                sum(case when t2.salary_component = 'Health Contribution' then ifnull(t2.amount,0) else 0 end) as healthcont,
                sum(
                   (case when t2.salary_component = 'Salary Tax' then ifnull(t2.amount,0) else 0 end)
                   + (case when t2.salary_component = 'Health Contribution' then ifnull(t2.amount,0) else 0 end)
                ) as total,
                t1.company, 
                t1.cost_center, 
                t1.branch, 
                t1.department, 
                t1.section,
                t1.fiscal_year, 
                t1.month
            from `tabSalary Slip` t1, `tabSalary Detail` t2, `tabEmployee` t3
            where t1.docstatus = 1 %s
            and t3.employee = t1.employee
            and t2.parent = t1.name
            group by 
                t1.employee, 
                t3.employee_name, 
                t1.designation, 
                t3.passport_number,
                t3.tpn_number, 
                t1.company, 
                t1.branch, 
                t1.department, 
                t1.section,
                t1.fiscal_year, 
                t1.month
            """ % conditions, filters, as_dict=1)
            
        return data
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Tax and Health Report Error")
        msgprint(_("Error generating report: {0}").format(str(e)))
        return []

def get_conditions(filters):
    conditions = ""
    month_map = {
        'January': 'January', 'February': 'February', 'March': 'March', 
        'April': 'April', 'May': 'May', 'June': 'June',
        'July': 'July', 'August': 'August', 'September': 'September',
        'October': 'October', 'November': 'November', 'December': 'December',
    }
    
    if filters.get("month"):
        month = month_map.get(filters["month"])
        if month:
            conditions += " and t1.month = %(month)s"
            filters["month"] = month
        else:
            frappe.throw(_("Invalid month specified"))
    
    if filters.get("fiscal_year"): 
        conditions += " and t1.fiscal_year = %(fiscal_year)s"
    if filters.get("company"): 
        conditions += " and t1.company = %(company)s"
    if filters.get("employee"): 
        conditions += " and t1.employee = %(employee)s"
    if filters.get("cost_center"): 
        conditions += """ and exists(select 1 from `tabCost Center` cc 
                          where t1.cost_center = cc.name 
                          and (cc.parent_cost_center = %(cost_center)s 
                               or cc.name = %(cost_center)s))"""
    
    return conditions, filters