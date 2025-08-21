import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, date_diff, nowdate
from frappe.utils.data import get_first_day, get_last_day, add_days
from erpnext.custom_utils import get_year_start_date, get_year_end_date
import json
import logging
from datetime import datetime, timedelta
import datetime
import calendar

@frappe.whitelist()
def get_payroll_settings(employee=None):
		settings = {}
		if employee:
			settings = frappe.db.sql("""
						select
							e.employee_group,
							e.grade,
							d.sws,
							d.gis,
							g.health_contribution,
							g.employee_pf,
							g.employer_pf
						from `tabEmployee` e, `tabEmployee Group` g, `tabEmployee Grade` d
						where e.name = '{}'
						and g.name = e.employee_group
						and d.name = e.grade
				""".format(employee), as_dict=True)
		settings = settings[0] if settings else frappe._dict()
		return settings

@frappe.whitelist()
def get_salary_tax(gross_amt):
	tax_amount = max_amount = 0
	max_limit = frappe.db.sql("""select max(b.to_amount)
		from `tabIncome Tax Slab` a, `tabTaxable Salary Slab` b
		where now() between a.effective_from and ifnull(a.effective_till, now())
		and b.parent = a.name
	""")
	if not (gross_amt or max_limit):
		return tax_amount
	max_amount = flt(max_limit[0][0])

	if flt(gross_amt) > flt(max_amount):
		tax_amount = ((flt(gross_amt) - 125000.00) * 0.30) + 20208.00
	else:
		result = frappe.db.sql("""select ifnull(b.tax,0) from
			`tabIncome Tax Slab` a, `tabTaxable Salary Slab` b
			where now() between a.effective_from and ifnull(a.effective_till, now())
			and b.parent = a.name
			and %s between ifnull(b.from_amount,0) and ifnull(b.to_amount,0)
			limit 1
			""", flt(gross_amt))

		if result:
			tax_amount = result[0][0]

	return flt(tax_amount)

@frappe.whitelist()
def get_month_details(year, month):
	ysd = frappe.db.get_value("Fiscal Year", year, "year_start_date")
	if ysd:
		from dateutil.relativedelta import relativedelta
		import calendar, datetime
		diff_mnt = cint(month)-cint(ysd.month)
		if diff_mnt<0:
			diff_mnt = 12-int(ysd.month)+cint(month)
		msd = ysd + relativedelta(months=diff_mnt) # month start date
		month_days = cint(calendar.monthrange(cint(msd.year) ,cint(month))[1]) # days in month
		med = datetime.date(msd.year, cint(month), month_days) # month end date
		return frappe._dict({
			'year': msd.year,
			'month_start_date': msd,
			'month_end_date': med,
			'month_days': month_days
		})
	else:
		frappe.throw(_("Fiscal Year {0} not found").format(year))

@frappe.whitelist()
def get_basic_and_gross_pay(employee, effective_date):
	SalaryStructure = frappe.qb.DocType("Salary Structure")
	SalaryDetail = frappe.qb.DocType("Salary Detail")
	query = (
		frappe.qb.from_(SalaryStructure)
		.join(SalaryDetail)
		.on(SalaryStructure.name == SalaryDetail.parent)
		.select(
			SalaryStructure.net_pay, 
			SalaryStructure.total_earning, 
			SalaryDetail.amount.as_("basic_pay")
		)
		.where(
			(SalaryStructure.is_active == "Yes")
			& (SalaryStructure.employee == employee)
			& (SalaryDetail.salary_component == "Basic Pay")
		)
	)
	
	results = query.run(as_dict=True)
	return results[0] if results else None


@frappe.whitelist()
def get_start_end_dates(fiscal_year, month, company=None):
	"""Returns dict of start and end dates for given month and fisacl year"""

	months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
	month = str(int(months.index(month))+1).rjust(2, "0")

	start_date = "-".join([str(fiscal_year), month, "01"])
	end_date   = get_last_day(start_date)

	return frappe._dict({"start_date": start_date, "end_date": end_date})


def get_officiating_employee(employee):
	if not employee:
		frappe.throw("Employee is Mandatory")
		
	qry = "select officiating_employee from `tabOfficiating Employee` where docstatus = 1 and revoked != 1 and %(today)s between from_date and to_date and employee = %(employee)s order by creation desc limit 1"
	officiate = frappe.db.sql(qry, {"today": nowdate(), "employee": employee}, as_dict=True)

	if officiate:
		flag = True
		while flag:
			temp = frappe.db.sql(qry, {"today": nowdate(), "employee": officiate[0].officiate}, as_dict=True)
			if temp:
				officiate = temp
			else:
				flag = False
	return officiate


def post_earned_leaves():	
	if not getdate(frappe.utils.nowdate()) == getdate(get_first_day(frappe.utils.nowdate())):
		
		return 0
	
	date = add_days(frappe.utils.nowdate(), -20)
	start = get_first_day(date);
	end = get_last_day(date);
	from datetime import datetime, timedelta,date
	today = datetime.today()
	first_day_of_year = datetime(today.year, 1, 1)
	last_day_of_year = datetime(today.year, 12, 31)	
	employees = frappe.db.sql("select name, employee_name, date_of_joining from `tabEmployee` where status = 'Active'", as_dict=True)
	
	for e in employees:
		# print(e.name)
		if cint(date_diff(end, getdate(e.date_of_joining))) > 14:
			employee_name = e.name
			employee_full_name = e.employee_name
			leave_type = "Earned Leave"
			from_date = first_day_of_year.strftime(f'%Y-%m-%d')
			to_date = last_day_of_year.strftime(f'%Y-%m-%d')
			existing_allocation = frappe.db.exists("Leave Allocation", {
    			"employee": employee_name,
    			"leave_type": leave_type,
    			"from_date": from_date,
    			"to_date": to_date,
    			"docstatus": 1  # Check for submitted documents only
			})

			max_leaves_allowed = flt(
				frappe.db.get_value("Leave Type", leave_type, "max_leaves_allowed")
			)

			if existing_allocation:
				current_year = datetime.now().year
				first_day = date(current_year, 1, 1).isoformat()
				last_day = date(current_year, 12, 31).isoformat()
				

				la = frappe.get_doc("Leave Allocation", existing_allocation)
				leave_sum = frappe.get_all(
											'Leave Ledger Entry',
											filters={
        											'leave_type': 'Earned Leave',
        											'employee': employee_name,
        											'docstatus': 1,
        											'from_date': ['between', [first_day, last_day]],
        											'to_date': ['between', [first_day, last_day]]
    												},
											fields=['SUM(leaves) as Leave_sum'],
											as_list=True
											)

# Access the result
				if leave_sum:
					total_leaves = leave_sum[0][0]
					#frappe.throw(str(total_leaves))
					print(f"Total Leaves: {total_leaves}")
				else:
					print("No leaves found.")
				if flt(total_leaves) + flt(2.5) <= max_leaves_allowed:
					la.new_leaves_allocated = flt(la.new_leaves_allocated) + flt(2.5)
					la.save()
					frappe.db.commit()
					print(f"Leave Allocation updated successfully for {employee_name}!")
				# else:
				# 	frappe.throw(str(la.new_leaves_allocated+2.5))
			else:
    
				la = frappe.new_doc("Leave Allocation")
				la.employee = employee_name
				la.employee_name = employee_full_name
				la.leave_type = leave_type
				la.from_date = from_date
				la.to_date = to_date
				la.carry_forward = cint(1)
				la.new_leaves_allocated = flt(2.5)
				la.submit()
				print(f"Leave Allocation submitted successfully for {employee_name}!")
				
			# la = frappe.new_doc("Leave Allocation")
			# la.employee = e.name
			# la.employee_name = e.employee_name
			# la.leave_type = "Earned Leave"
			# la.from_date = first_day_of_year.strftime(f'%Y-%m-%d')
			# la.to_date = last_day_of_year.strftime(f'%Y-%m-%d')
			# la.carry_forward = cint(1)
			# la.new_leaves_allocated = flt(2.5)
			# la.submit()
			#print(f"Leave Allocation submitted successfully for {e.name}!")
		else:
			pass

#function to get the difference between two dates
@frappe.whitelist()
def get_date_diff(start_date, end_date):
	if start_date is None:
		return 0
	elif end_date is None:
		return 0
	else:	
		return frappe.utils.data.date_diff(end_date, start_date) + 1