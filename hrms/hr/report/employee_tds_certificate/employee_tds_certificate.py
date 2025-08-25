# # Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# # For license information, please see license.txt
import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, cstr

def execute(filters=None):
    validate_filters(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data, filters

def get_data(filters=None):
    data = []
    frappe.errprint(f"Filters: {filters}")  # Debug: Print filters

    # Fetch salary data
    salary_data = get_salary_data(filters)
    frappe.errprint(f"Salary Data: {salary_data}")  # Debug: Print salary data

    if not salary_data:
        frappe.msgprint("No data found for the given filters.")
    else:
        data.extend(salary_data)

    return data

def get_salary_data(filters):
    data = []
    query = '''
        SELECT 
            CONCAT(a.month,'-', a.fiscal_year) month_year, 
            a.gross_pay, 
            (SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'Basic Pay') AS basic_pay, 
            (SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'Salary Tax') AS tds, 
            (SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'PF') AS nppf, 
            COALESCE((SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'GIS'), 0) AS gis, 
            (SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'Communication Allowance') AS comm_all, 
            (SELECT b.amount FROM `tabSalary Detail` b WHERE b.parent = a.name AND b.salary_component = 'Health Contribution') AS health, 
            r.receipt_number, 
            r.receipt_date, 
            r.posting_date
        FROM `tabSalary Slip` a
        JOIN `tabTDS Receipt Entry` r ON a.fiscal_year = r.fiscal_year 
        AND CASE 
                WHEN a.month = 'January' THEN '01'
                WHEN a.month = 'February' THEN '02'
                WHEN a.month = 'March' THEN '03'
                WHEN a.month = 'April' THEN '04'
                WHEN a.month = 'May' THEN '05'
                WHEN a.month = 'June' THEN '06'
                WHEN a.month = 'July' THEN '07'
                WHEN a.month = 'August' THEN '08'
                WHEN a.month = 'September' THEN '09'
                WHEN a.month = 'October' THEN '10'
                WHEN a.month = 'November' THEN '11'
                WHEN a.month = 'December' THEN '12'
            END = r.month
        WHERE a.docstatus = 1 
        AND a.employee = %(employee)s 
        AND a.fiscal_year = %(fiscal_year)s
        ORDER BY r.receipt_date ASC
    '''
    # # frappe.throw(str(query))
    salary_data = frappe.db.sql(query, filters, as_dict=True)

    for d in salary_data:
        data.append({
            "month_year": d.month_year,
            "type": "Salary",
            "basic": flt(d.basic_pay, 2),
            "others": flt(flt(d.gross_pay) - flt(d.basic_pay) - (flt(d.comm_all) / 2), 2),
            "total": flt(flt(d.gross_pay) - (flt(d.comm_all) / 2), 2),
            "pf": flt(d.nppf, 2),
            "gis": flt(d.gis, 2),
            "totalPfGis": flt(flt(d.nppf) + flt(d.gis), 2),
            "taxable": flt(d.gross_pay) - flt(d.nppf) - flt(d.gis) - (flt(d.comm_all) / 2),
            "tds": flt(d.tds, 2) if d.tds else 0,
            "health": flt(d.health, 2),
            "receipt_number": d.receipt_number,
            "receipt_date": d.receipt_date,
            "posting_date": d.posting_date
        })
    return data

def validate_filters(filters):
    if not filters.get("fiscal_year"):
        frappe.throw(_("Fiscal Year is required"))
    start, end = frappe.db.get_value("Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"])
    filters.year_start = start
    filters.year_end = end

def get_columns():
    return [
        {
            "fieldname": "month_year", 
            "label": "Month-Year", 
            "fieldtype": "Data", 
            "width": 100
        },
        {
            "fieldname": "type", 
            "label": "Income Type", 
            "fieldtype": "Data", 
            "width": 160
        },
        {
            "fieldname": "basic",
            "label": "Basic Salary", 
            "fieldtype": "Currency", 
            "width": 150
        },
        {
            "fieldname": "others", 
            "label": "Allowances", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "fieldname": "total", 
            "label": "Total Income", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "fieldname": "pf",
            "label": "PF",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "gis",
            "label": "GIS",
            "fieldtype":"Currency", 
            "width": 120
        },
        {
            "fieldname": "totalPfGis",
            "label": "Total of PF & GIS",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "taxable", 
            "label": "Taxable Income", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "fieldname": "tds",
            "label": "TDS Amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "health", 
            "label": "Health", 
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "fieldname": "receipt_number", 
            "label": "RRCO Receipt No.", 
            "fieldtype": "Data", 
            "width": 150
        },
        {
            "fieldname": "receipt_date", 
            "label": "RRCO Receipt Date", 
            "fieldtype": "Date", 
            "width": 130
        },
        {
            "fieldname": "posting_date", 
            "label": "Posting Date", 
            "fieldtype": "Date", 
            "width": 130
        },
    ]