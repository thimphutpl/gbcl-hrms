# # Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# # License: GNU General Public License v3. See license.txt

# import re

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe.model.mapper import get_mapped_doc
# from frappe.utils import cint, cstr, flt, getdate, get_first_day, today, get_last_day
# from frappe.model.naming import make_autoname
# from hrms.hr.hr_custom_function import get_payroll_settings, get_salary_tax, get_month_details
# import math


# import erpnext

# from hrms.payroll.utils import sanitize_expression

# class SalaryStructure(Document):
# 	def autoname(self):
# 		if not self.employee:
# 			frappe.throw(_("Employee field cannot be empty for autoname generation."))
# 		self.name = make_autoname(f"{self.employee}/.SST/.####")

# 	def validate(self):
# 		self.validate_dates()
# 		self.validate_amount()
# 		self.update_salary_structure()

# 	def validate_dates(self):
# 		joining_date, relieving_date = frappe.db.get_value(
# 			"Employee", self.employee, ["date_of_joining", "relieving_date"]
# 		)

# 		if self.from_date:
# 			existing_salary_structure = frappe.db.sql("""
# 				SELECT name FROM `tabSalary Structure`
# 				WHERE employee = %s
# 				AND is_active = 'Yes'
# 				AND from_date <= %s
				
# 			""", (self.employee, self.from_date), as_dict=True)

# 			if existing_salary_structure and existing_salary_structure[0]["name"] != self.name:
# 				frappe.throw(_("An active Salary Structure for this employee already exists."))


# 			if joining_date and getdate(self.from_date) < joining_date:
# 				frappe.throw(
# 					_("From Date {0} cannot be before employee's joining Date {1}").format(
# 						self.from_date, joining_date
# 					)
# 				)

# 			# flag - old_employee is for migrating the old employees data via patch
# 			if relieving_date and getdate(self.from_date) > relieving_date and not self.flags.old_employee:
# 				frappe.throw(
# 					_("From Date {0} cannot be after employee's relieving Date {1}").format(
# 						self.from_date, relieving_date
# 					)
# 				)

# 	def validate_amount(self):
# 		if flt(self.net_pay) <= 0: 
# 			frappe.throw(_("Net pay cannot be negative"))

# 	def validate_salary_component(self):
# 		dup = {}
# 		for parentfield in ['earnings', 'deductions']:
# 			parenttype = 'Earning' if parentfield == 'earnings' else 'Deduction'
# 			for i in self.get(parentfield):
# 				# Restricting users from entering earning component under deductions table and vice versa.
# 				component_type, is_loan_component = frappe.db.get_value("Salary Component", i.salary_component, ["type", "is_loan_component"])
# 				if parenttype != component_type:
# 					frappe.throw(_('Salary Component <b>`{1}`</b> of type <b>`{2}`</b> cannot be added under <b>`{3}`</b> table. <br/> <b><u>Reference# : </u></b> <a href="#Form/Salary Structure/{0}">{0}</a>').format(
# 						self.name, i.salary_component, component_type, parentfield.title()), title="Invalid Salary Component")
# 				# Checking duplicate entries
# 				if i.salary_component in ('Basic Pay') and i.salary_component in dup:
# 					frappe.throw(_("Row#{0} : Duplicate entries not allowed for component <b>{1}</b>.")
# 								 .format(i.idx, i.salary_component), title="Duplicate Record Found")
# 				else:
# 					dup.update({i.salary_component: 1})

# 				# Validate Loan details
# 				if parenttype == 'Deduction' and cint(is_loan_component):
# 					if not i.institution_name:
# 						frappe.throw(_("Row#{}: <b>Institution Name</b> is mandatory for <b>{}</b>").format(i.idx, i.salary_component))
# 					elif not i.reference_number:
# 						frappe.throw(_("Row#{}: <b>Loan Account No.(Reference Number)</b> is mandatory for <b>{}</b>").format(i.idx, i.salary_component))

# 	def get_active_amount(self, rec):
# 		''' return amount only if the component is active '''
# 		calc_amt = 0
# 		if rec.from_date or rec.to_date:
# 			if rec.to_date and str(rec.to_date) >= str(get_first_day(today())):
# 				calc_amt = rec.amount
# 			elif rec.from_date and str(rec.from_date) <= str(get_last_day(today())):
# 				calc_amt = rec.amount
# 			else:
# 				calc_amt = 0
# 		else:	
# 			calc_amt = rec.amount

# 		if rec.parentfield == "deductions":
# 			if not flt(rec.total_deductible_amount):
# 				calc_amt = calc_amt
# 			elif flt(rec.total_deductible_amount) and flt(rec.total_deductible_amount) != flt(rec.total_deducted_amount):
# 				calc_amt = calc_amt
# 			else:
# 				calc_amt = 0
				
# 		return flt(calc_amt)

# 	@frappe.whitelist()
# 	def update_salary_structure(self, new_basic_pay=0, remove_flag=1):
# 		'''
# 			This method calculates all the allowances and deductions based on the preferences
# 			set in the GUI. Calculated values are then checked and updated as follows.
# 					1) If the calculated component is missing in the existing earnings/deductions
# 						table then insert a new row.
# 					2) If the calculated component is found in the existing earnings/deductions
# 						table but amounts do not match, then update the respective row.
# 		'''
# 		self.validate_salary_component()
		

# 		basic_pay = comm_allowance = gis_amt = sws_amt = pf_amt = health_cont_amt = tax_amt = basic_pay_arrears = payscale_lower_limit= 0
# 		total_earning = total_deduction = net_pay = 0
# 		payscale_lower_limit = frappe.db.get_value("Employee Grade", frappe.db.get_value("Employee",self.employee,"grade"), "lower_limit")
# 		settings = get_payroll_settings(self.employee)
# 		settings = settings if settings else {}

# 		tbl_list = {'earnings': 'Earning', 'deductions': 'Deduction'}
# 		del_list_all = []
		
# 		for ed in ['earnings', 'deductions']:
# 			add_list = []
# 			del_list = []
# 			calc_map = []

# 			sst_map = {ed: []}
# 			for sc in frappe.db.sql("select * from `tabSalary Component` where `type`='{0}' and ifnull(field_name,'') != ''".format(tbl_list[ed]), as_dict=True):
# 				sst_map.setdefault(ed, []).append(sc)
			
			
# 			ed_map = [i.name for i in sst_map[ed]]
# 			#['Contract Allowance', 'Corporate Allowance', 'Fixed Allowance (Increment)', 'HRA', 'Monthly Variable Compensation (MVC)']
# 			# frappe.throw(frappe.as_json(self.get(ed)))
# 			for ed_item in self.get(ed):
# 				#self.get(ed) here fetch the details of the alraedy existed details
				
# 				# validate component validity dates
# 				if ed_item.from_date and ed_item.to_date and str(ed_item.to_date) < str(ed_item.from_date):
# 					frappe.throw(_("<b>Row#{}:</b> Invalid <b>From Date</b> for <b>{}</b> under <b>{}s</b>").format(ed_item.idx, ed_item.salary_component, tbl_list[ed]))

# 				# ed_item.amount = roundoff(ed_item.amount)
# 				ed_item.amount = flt(ed_item.amount)
# 				amount = ed_item.amount

# 				if ed_item.salary_component not in ed_map:
# 					if ed == 'earnings':
# 						if ed_item.salary_component == 'Basic Pay':
							
# 							if flt(new_basic_pay) > 0 and flt(new_basic_pay) != flt(amount):
								
# 								amount = flt(new_basic_pay)
# 							basic_pay = amount
							
# 							ed_item.amount = basic_pay
# 						elif frappe.db.exists("Salary Component", {"name": ed_item.salary_component, "is_pf_deductible": 1}):
# 							basic_pay_arrears += flt(ed_item.amount)
# 						total_earning += round(amount)
# 					else:
# 						if flt(ed_item.total_deductible_amount) == 0:
# 							total_deduction += amount
# 						else:
# 							if flt(ed_item.total_deductible_amount) != flt(ed_item.total_deducted_amount):
# 								total_deduction += round(amount)
# 				else:
# 					for m in sst_map[ed]:
# 						if m['name'] == ed_item.salary_component and not self.get(m['field_name']):
# 							del_list.append(ed_item)
# 							del_list_all.append(ed_item)

# 			if remove_flag:
# 				[self.remove(d) for d in del_list]

# 			# Calculating Earnings and Deductions based on preferences and values set
# 			# frappe.throw(frappe.as_json(sst_map[ed]))
# 			for m in sst_map[ed]:
# 				#basic,hra,eligible
				
# 				calc_amt = 0
# 				if self.get(m['field_method']) == 'Percent' and flt(self.get(m['field_value'])) < 0:
# 					frappe.throw(
# 						_("Percentage cannot be less than 0 for component <b>{0}</b>").format(m['name']), title="Invalid Data")
# 				elif self.get(m['field_method']) == 'Percent' and flt(self.get(m['field_value'])) > 200:
# 					frappe.throw(
# 						_("Percentage cannot exceed 200 for component <b>{0}</b>").format(m['name']), title="Invalid Data")

# 				if ed == 'earnings':
# 					# frappe.throw('hi')
# 					if self.get(m['field_name']):
# 						if self.get(m["field_method"]) == 'Percent':
# 							if m['based_on'] == 'Pay Scale Lower Limit':
# 								calc_amt = flt(payscale_lower_limit)*flt(self.get(m['field_value']))*0.01
# 							else:
# 								calc_amt = flt(basic_pay)*flt(self.get(m['field_value']))*0.01
# 						else:
# 							calc_amt = flt(self.get(m['field_value']))
				
# 						if m["field_name"] == "eligible_for_fixed_allowance":
# 							calc_amt = frappe.db.get_value("Employee Grade", self.employee_grade, "fixed_allowance")
# 						if m["field_name"] == "eligible_for_hra":
# 							payment_method = frappe.db.get_value("Salary Component", "HRA", "payment_method")
# 							cal_based = frappe.db.get_value("Salary Component", "HRA", "based_on")
# 							amount = frappe.db.get_value("Salary Component", "HRA", "amount")
# 							if not payment_method or not cal_based or not amount:
# 								frappe.throw('Add Payment Method, Calculation Based, Amount in salary component in HRA')
# 							if payment_method == 'Percent' and cal_based == 'Basic Pay' and amount:
# 								calc_amt = (flt(basic_pay) * flt(amount) / 100)
# 							if payment_method == 'Lumpsum' and amount:
# 								# frappe.throw(str(amount))
# 								calc_amt = (flt(amount))
# 						if m["field_name"] == "eligible_for_conveyance_allowance":
# 							payment_method = frappe.db.get_value("Salary Component", "Conveyance Allowance", "payment_method")
# 							amount = frappe.db.get_value("Salary Component", "Conveyance Allowance", "amount")
# 							if payment_method == 'Lumpsum' and amount:
# 								# frappe.throw(str(amount))

# 								calc_amt = (flt(amount))
# 							# calc_amt = roundoff(hra_amount)
# 							# frappe.throw(str(calc_amt))
# 							# calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
						
# 						# calc_amt = roundoff(calc_amt)
# 						calc_amt = flt(calc_amt)
# 						comm_allowance += flt(calc_amt) if m['name'] == 'Communication Allowance' else 0
# 						total_earning += calc_amt
# 						calc_map.append({'salary_component': m['name'], 'amount': calc_amt})
# 				else:
# 					# frappe.throw('hello')
# 					if self.get(m['field_name']) and m['name'] == 'SWS':
# 						sws_amt = flt(settings.get('sws'))
# 						# calc_amt = roundoff(sws_amt)
# 						calc_amt = flt(sws_amt)
# 						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

# 					elif self.get(m['field_name']) and m['name'] == 'GIS':
# 						gis_amt = flt(settings.get("gis"))
# 						# calc_amt = roundoff(gis_amt)
# 						calc_amt = flt(gis_amt)
# 						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

# 					elif self.get(m['field_name']) and m['name'] == 'PF':
# 						pf_amt = (flt(basic_pay)+flt(basic_pay_arrears))*flt(settings.get("employee_pf"))*0.01
# 						# calc_amt = roundoff(pf_amt)
# 						calc_amt = flt(pf_amt)
# 						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

# 					elif self.get(m['field_name']) and m['name'] == 'Health Contribution':
# 						health_cont_amt = flt(total_earning)*flt(settings.get("health_contribution"))*0.01
# 						# calc_amt = roundoff(health_cont_amt)
# 						calc_amt = flt(health_cont_amt)
# 						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
# 					elif self.get(m['field_name']) and m['name'] == 'HRA':
# 						# frappe.throw('hra')
# 						# health_cont_amt = flt(total_earning)*flt(settings.get("health_contribution"))*0.01
# 						payment_method = frappe.db.get_value("Salary Component", "HRA", "payment_method")
# 						cal_based = frappe.db.get_value("Salary Component", "HRA", "based_on")
# 						amount = frappe.db.get_value("Salary Component", "HRA", "amount")
# 						if not payment_method or not cal_based or not amount:
# 							frappe.throw('Add Payment Method, Calculation Based, Amount in salary component in HRA')
# 						if payment_method == 'Percent' and cal_based == 'Basic Pay' and amount:
# 							hra_amount = (flt(basic_pay) * flt(amount) / 100)
# 						# calc_amt = roundoff(hra_amount)
# 						calc_amt = flt(hra_amount)
# 						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
# 					else:
# 						calc_amt = 0
# 					# frappe.throw('hi')
# 					total_deduction += calc_amt

# 			# Calculating Salary Tax
# 			if ed == 'deductions':
# 				calc_amt = get_salary_tax(math.floor(flt(total_earning)-flt(pf_amt)-flt(gis_amt)-(comm_allowance*0.5)))
# 				# calc_amt = roundoff(calc_amt)
# 				calc_amt = flt(calc_amt)
# 				total_deduction += calc_amt
# 				calc_map.append({'salary_component': 'Salary Tax', 'amount': flt(calc_amt)})

# 			# Updating existing Earnings and Deductions tables
# 			for c in calc_map:
# 				found = 0
# 				for ed_item in self.get(ed):
# 					if str(ed_item.salary_component) == str(c['salary_component']):
# 						found = 1
# 						if flt(ed_item.amount) != flt(c['amount']):
# 							ed_item.amount = flt(c['amount'])
# 						break

# 				if not found:
# 					add_list.append(c)
			
# 			[self.append(ed, i) for i in add_list]
		
		
# 		self.total_earning   = sum([self.get_active_amount(rec) for rec in self.get("earnings")])
# 		self.total_deduction = sum([self.get_active_amount(rec) for rec in self.get("deductions")])
# 		self.net_pay = flt(self.total_earning) - flt(self.total_deduction)

# 		if flt(self.total_earning)-flt(self.total_deduction) < 0 and not self.get('__unsaved'):
# 			frappe.throw(_("Total deduction cannot be more than total earning"), title="Invalid Data")
		
# 		return del_list_all

# def roundoff(amount):
# 	return math.ceil(amount) if (amount - int(amount)) >= 0.5 else math.floor(amount)


# # @frappe.whitelist()
# # def make_salary_slip(
# # 	source_name,
# # 	target_doc=None,
# # 	employee=None,
# # 	posting_date=None,
# # 	as_print=False,
# # 	print_format=None,
# # 	for_preview=0,
# # 	ignore_permissions=False,
# # ):
# # 	def postprocess(source, target):
# # 		if employee:
# # 			target.employee = employee
# # 			if posting_date:
# # 				target.posting_date = posting_date

# # 		target.run_method("process_salary_structure", for_preview=for_preview)

# # 	doc = get_mapped_doc(
# # 		"Salary Structure",
# # 		source_name,
# # 		{
# # 			"Salary Structure": {
# # 				"doctype": "Salary Slip",
# # 				"field_map": {
# # 					"total_earning": "gross_pay",
# # 					"name": "salary_structure",
# # 				},
# # 			}
# # 		},
# # 		target_doc,
# # 		postprocess,
# # 		ignore_child_tables=True,
# # 		ignore_permissions=ignore_permissions,
# # 		cached=True,
# # 	)

# # 	if cint(as_print):
# # 		doc.name = f"Preview for {employee}"
# # 		return frappe.get_print(doc.doctype, doc.name, doc=doc, print_format=print_format)
# # 	else:
# # 		return doc

# @frappe.whitelist()
# def make_salary_slip(
#     source_name,
#     target_doc=None,
#     employee=None,
#     posting_date=None,
#     as_print=False,
#     print_format=None,
#     for_preview=0,
#     ignore_permissions=False,
# ):
#     def postprocess(source, target):
#         if employee:
#             target.employee = employee
#         if posting_date:
#             target.posting_date = posting_date

#         salary_details = frappe.get_all(
#             "Salary Detail",
#             filters={"parent": source.name},
#             fields=["salary_component", "from_date", "to_date"]
#         )

#         if not salary_details:
#             frappe.throw("No Salary Details found in Salary Structure.")
#         structure_from_date = min([d.from_date for d in salary_details if d.from_date])
#         structure_to_date = max([d.to_date for d in salary_details if d.to_date])
#         target.start_date = structure_from_date
#         target.end_date = structure_to_date
#         target.run_method("process_salary_structure", for_preview=for_preview)

#         def filter_rows(rows):
#             filtered = []
#             for row in rows:
#                 if not row.from_date:
#                     row.from_date = structure_from_date
#                 if not row.to_date:
#                     row.to_date = structure_to_date
#                 filtered.append(row)
#             return filtered

#         target.set("deductions", filter_rows(target.get("deductions")))
#         target.set("earnings", filter_rows(target.get("earnings")))

#     doc = get_mapped_doc(
#         "Salary Structure",
#         source_name,
#         {
#             "Salary Structure": {
#                 "doctype": "Salary Slip",
#                 "field_map": {
#                     "total_earning": "gross_pay",
#                     "name": "salary_structure",
#                 },
#             }
#         },
#         target_doc,
#         postprocess,
#         ignore_child_tables=True,
#         ignore_permissions=ignore_permissions,
#         cached=True,
#     )

#     if cint(as_print):
#         doc.name = f"Preview for {employee}"
#         return frappe.get_print(doc.doctype, doc.name, doc=doc, print_format=print_format)
#     else:
#         return doc





# def get_assigned_salary_structure(employee, on_date):
# 	if not employee or not on_date:
# 		return None
# 	salary_structure = frappe.db.sql(
# 		"""
# 		select name from `tabSalary Structure Assignment`
# 		where employee=%(employee)s
# 		and docstatus = 1
# 		and %(on_date)s >= from_date order by from_date desc limit 1""",
# 		{
# 			"employee": employee,
# 			"on_date": on_date,
# 		},
# 	)
# 	return salary_structure[0][0] if salary_structure else None

# @frappe.whitelist()
# def get_employee_currency(employee):
# 	employee_currency = frappe.db.get_value("Salary Structure", {"employee": employee}, "currency")
# 	if not employee_currency:
# 		frappe.throw(
# 			_("There is no Salary Structure assigned to {0}. First assign a Salary Stucture.").format(
# 				employee
# 			)
# 		)
# 	return employee_currency

# 	'''
# 	def before_validate(self):
# 		self.sanitize_condition_and_formula_fields()

# 	def before_update_after_submit(self):
# 		self.sanitize_condition_and_formula_fields()

# 	def validate(self):
# 		self.set_missing_values()
# 		self.validate_amount()
# 		self.validate_max_benefits_with_flexi()
# 		self.validate_component_based_on_tax_slab()
# 		self.validate_payment_days_based_dependent_component()
# 		self.validate_timesheet_component()
# 		self.validate_formula_setup()

# 	def on_update(self):
# 		self.reset_condition_and_formula_fields()

# 	def on_update_after_submit(self):
# 		self.reset_condition_and_formula_fields()

# 	def validate_formula_setup(self):
# 		for table in ["earnings", "deductions"]:
# 			for row in self.get(table):
# 				if not row.amount_based_on_formula and row.formula:
# 					frappe.msgprint(
# 						_(
# 							"{0} Row #{1}: Formula is set but {2} is disabled for the Salary Component {3}."
# 						).format(
# 							table.capitalize(),
# 							row.idx,
# 							frappe.bold(_("Amount Based on Formula")),
# 							frappe.bold(row.salary_component),
# 						),
# 						title=_("Warning"),
# 						indicator="orange",
# 					)

# 	def set_missing_values(self):
# 		overwritten_fields = [
# 			"depends_on_payment_days",
# 			"variable_based_on_taxable_salary",
# 			"is_tax_applicable",
# 			"is_flexible_benefit",
# 		]
# 		overwritten_fields_if_missing = ["amount_based_on_formula", "formula", "amount"]
# 		for table in ["earnings", "deductions"]:
# 			for d in self.get(table):
# 				component_default_value = frappe.db.get_value(
# 					"Salary Component",
# 					cstr(d.salary_component),
# 					overwritten_fields + overwritten_fields_if_missing,
# 					as_dict=1,
# 				)
# 				if component_default_value:
# 					for fieldname in overwritten_fields:
# 						value = component_default_value.get(fieldname)
# 						if d.get(fieldname) != value:
# 							d.set(fieldname, value)

# 					if not (d.get("amount") or d.get("formula")):
# 						for fieldname in overwritten_fields_if_missing:
# 							d.set(fieldname, component_default_value.get(fieldname))

# 	def validate_component_based_on_tax_slab(self):
# 		for row in self.deductions:
# 			if row.variable_based_on_taxable_salary and (row.amount or row.formula):
# 				frappe.throw(
# 					_(
# 						"Row #{0}: Cannot set amount or formula for Salary Component {1} with Variable Based On Taxable Salary"
# 					).format(row.idx, row.salary_component)
# 				)

# 	def validate_amount(self):
# 		if flt(self.net_pay) < 0 and self.salary_slip_based_on_timesheet:
# 			frappe.throw(_("Net pay cannot be negative"))

# 	def validate_payment_days_based_dependent_component(self):
# 		abbreviations = self.get_component_abbreviations()
# 		for component_type in ("earnings", "deductions"):
# 			for row in self.get(component_type):
# 				if (
# 					row.formula
# 					and row.depends_on_payment_days
# 					# check if the formula contains any of the payment days components
# 					and any(re.search(r"\b" + abbr + r"\b", row.formula) for abbr in abbreviations)
# 				):
# 					message = _("Row #{0}: The {1} Component has the options {2} and {3} enabled.").format(
# 						row.idx,
# 						frappe.bold(row.salary_component),
# 						frappe.bold(_("Amount based on formula")),
# 						frappe.bold(_("Depends On Payment Days")),
# 					)
# 					message += "<br><br>" + _(
# 						"Disable {0} for the {1} component, to prevent the amount from being deducted twice, as its formula already uses a payment-days-based component."
# 					).format(frappe.bold(_("Depends On Payment Days")), frappe.bold(row.salary_component))
# 					frappe.throw(message, title=_("Payment Days Dependency"))

# 	def get_component_abbreviations(self):
# 		abbr = [d.abbr for d in self.earnings if d.depends_on_payment_days]
# 		abbr += [d.abbr for d in self.deductions if d.depends_on_payment_days]

# 		return abbr

# 	def validate_timesheet_component(self):
# 		if not self.salary_slip_based_on_timesheet:
# 			return

# 		for component in self.earnings:
# 			if component.salary_component == self.salary_component:
# 				frappe.msgprint(
# 					_(
# 						"Row #{0}: Timesheet amount will overwrite the Earning component amount for the Salary Component {1}"
# 					).format(self.idx, frappe.bold(self.salary_component)),
# 					title=_("Warning"),
# 					indicator="orange",
# 				)
# 				break

# 	def sanitize_condition_and_formula_fields(self):
# 		for table in ("earnings", "deductions"):
# 			for row in self.get(table):
# 				row.condition = row.condition.strip() if row.condition else ""
# 				row.formula = row.formula.strip() if row.formula else ""
# 				row._condition, row.condition = row.condition, sanitize_expression(row.condition)
# 				row._formula, row.formula = row.formula, sanitize_expression(row.formula)

# 	def reset_condition_and_formula_fields(self):
# 		# set old values (allowing multiline strings for better readability in the doctype form)
# 		for table in ("earnings", "deductions"):
# 			for row in self.get(table):
# 				row.condition = row._condition
# 				row.formula = row._formula

# 		self.db_update_all()

# 	def validate_max_benefits_with_flexi(self):
# 		have_a_flexi = False
# 		if self.earnings:
# 			flexi_amount = 0
# 			for earning_component in self.earnings:
# 				if earning_component.is_flexible_benefit == 1:
# 					have_a_flexi = True
# 					max_of_component = frappe.db.get_value(
# 						"Salary Component", earning_component.salary_component, "max_benefit_amount"
# 					)
# 					flexi_amount += max_of_component

# 			if have_a_flexi and flt(self.max_benefits) == 0:
# 				frappe.throw(_("Max benefits should be greater than zero to dispense benefits"))
# 			if have_a_flexi and flexi_amount and flt(self.max_benefits) > flexi_amount:
# 				frappe.throw(
# 					_(
# 						"Total flexible benefit component amount {0} should not be less than max benefits {1}"
# 					).format(flexi_amount, self.max_benefits)
# 				)
# 		if not have_a_flexi and flt(self.max_benefits) > 0:
# 			frappe.throw(
# 				_("Salary Structure should have flexible benefit component(s) to dispense benefit amount")
# 			)

# 	def get_employees(self, **kwargs):
# 		conditions, values = [], []
# 		for field, value in kwargs.items():
# 			if value:
# 				conditions.append(f"{field}=%s")
# 				values.append(value)

# 		condition_str = " and " + " and ".join(conditions) if conditions else ""

# 		# nosemgrep: frappe-semgrep-rules.rules.frappe-using-db-sql
# 		employees = frappe.db.sql_list(
# 			f"select name from tabEmployee where status='Active' {condition_str}",
# 			tuple(values),
# 		)

# 		return employees

# 	@frappe.whitelist()
# 	def assign_salary_structure(
# 		self,
# 		branch=None,
# 		grade=None,
# 		department=None,
# 		designation=None,
# 		employee=None,
# 		payroll_payable_account=None,
# 		from_date=None,
# 		base=None,
# 		variable=None,
# 		income_tax_slab=None,
# 	):
# 		employees = self.get_employees(
# 			company=self.company,
# 			grade=grade,
# 			department=department,
# 			designation=designation,
# 			name=employee,
# 			branch=branch,
# 		)

# 		if employees:
# 			if len(employees) > 20:
# 				frappe.enqueue(
# 					assign_salary_structure_for_employees,
# 					timeout=3000,
# 					employees=employees,
# 					salary_structure=self,
# 					payroll_payable_account=payroll_payable_account,
# 					from_date=from_date,
# 					base=base,
# 					variable=variable,
# 					income_tax_slab=income_tax_slab,
# 				)
# 			else:
# 				assign_salary_structure_for_employees(
# 					employees,
# 					self,
# 					payroll_payable_account=payroll_payable_account,
# 					from_date=from_date,
# 					base=base,
# 					variable=variable,
# 					income_tax_slab=income_tax_slab,
# 				)
# 		else:
# 			frappe.msgprint(_("No Employee Found"))


# def assign_salary_structure_for_employees(
# 	employees,
# 	salary_structure,
# 	payroll_payable_account=None,
# 	from_date=None,
# 	base=None,
# 	variable=None,
# 	income_tax_slab=None,
# ):
# 	assignments = []
# 	existing_assignments_for = get_existing_assignments(employees, salary_structure, from_date)
# 	count = 0
# 	savepoint = "before_assignment_submission"

# 	for employee in employees:
# 		try:
# 			frappe.db.savepoint(savepoint)
# 			if employee in existing_assignments_for:
# 				continue

# 			count += 1

# 			assignment = create_salary_structure_assignment(
# 				employee,
# 				salary_structure.name,
# 				salary_structure.company,
# 				salary_structure.currency,
# 				from_date,
# 				payroll_payable_account,
# 				base,
# 				variable,
# 				income_tax_slab,
# 			)
# 			assignments.append(assignment)
# 			frappe.publish_progress(
# 				count * 100 / len(set(employees) - set(existing_assignments_for)),
# 				title=_("Assigning Structures..."),
# 			)
# 		except Exception:
# 			frappe.db.rollback(save_point=savepoint)
# 			frappe.log_error(
# 				f"Salary Structure Assignment failed for employee {employee}",
# 				reference_doctype="Salary Structure Assignment",
# 			)

# 	if assignments:
# 		frappe.msgprint(_("Structures have been assigned successfully"))


# def create_salary_structure_assignment(
# 	employee,
# 	salary_structure,
# 	company,
# 	currency,
# 	from_date,
# 	payroll_payable_account=None,
# 	base=None,
# 	variable=None,
# 	income_tax_slab=None,
# ):
# 	assignment = frappe.new_doc("Salary Structure Assignment")

# 	if not payroll_payable_account:
# 		payroll_payable_account = frappe.db.get_value("Company", company, "default_payroll_payable_account")
# 		if not payroll_payable_account:
# 			frappe.throw(_('Please set "Default Payroll Payable Account" in Company Defaults'))

# 	payroll_payable_account_currency = frappe.db.get_value(
# 		"Account", payroll_payable_account, "account_currency"
# 	)
# 	company_curency = erpnext.get_company_currency(company)
# 	if payroll_payable_account_currency != currency and payroll_payable_account_currency != company_curency:
# 		frappe.throw(
# 			_("Invalid Payroll Payable Account. The account currency must be {0} or {1}").format(
# 				currency, company_curency
# 			)
# 		)

# 	assignment.employee = employee
# 	assignment.salary_structure = salary_structure
# 	assignment.company = company
# 	assignment.currency = currency
# 	assignment.payroll_payable_account = payroll_payable_account
# 	assignment.from_date = from_date
# 	assignment.base = base
# 	assignment.variable = variable
# 	assignment.income_tax_slab = income_tax_slab
# 	assignment.save(ignore_permissions=True)
# 	assignment.submit()

# 	return assignment.name


# def get_existing_assignments(employees, salary_structure, from_date):
# 	# nosemgrep: frappe-semgrep-rules.rules.frappe-using-db-sql
# 	salary_structures_assignments = frappe.db.sql_list(
# 		f"""
# 		SELECT DISTINCT employee FROM `tabSalary Structure Assignment`
# 		WHERE salary_structure=%s AND employee IN ({", ".join(["%s"] * len(employees))})
# 		AND from_date=%s AND company=%s AND docstatus=1
# 		""",
# 		[salary_structure.name, *employees, from_date, salary_structure.company],
# 	)
# 	if salary_structures_assignments:
# 		frappe.msgprint(
# 			_(
# 				"Skipping Salary Structure Assignment for the following employees, as Salary Structure Assignment records already exists against them. {0}"
# 			).format("\n".join(salary_structures_assignments))
# 		)
# 	return salary_structures_assignments


# @frappe.whitelist()
# def get_employees(salary_structure):
# 	employees = frappe.get_list(
# 		"Salary Structure Assignment",
# 		filters={"salary_structure": salary_structure, "docstatus": 1},
# 		pluck="employee",
# 	)

# 	if not employees:
# 		frappe.throw(
# 			_(
# 				"There's no Employee with Salary Structure: {0}. Assign {1} to an Employee to preview Salary Slip"
# 			).format(salary_structure, salary_structure)
# 		)

# 	return list(set(employees))


# @frappe.whitelist()
# def get_salary_component(doctype, txt, searchfield, start, page_len, filters):
# 	sc = frappe.qb.DocType("Salary Component")
# 	sca = frappe.qb.DocType("Salary Component Account")

# 	salary_components = (
# 		frappe.qb.from_(sc)
# 		.left_join(sca)
# 		.on(sca.parent == sc.name)
# 		.select(sc.name, sca.account, sca.company)
# 		.where(
# 			(sc.type == filters.get("component_type"))
# 			& (sc.disabled == 0)
# 			& (sc[searchfield].like(f"%{txt}%") | sc.name.like(f"%{txt}%"))
# 		)
# 		.limit(page_len)
# 		.offset(start)
# 	).run(as_dict=True)

# 	accounts = []
# 	for component in salary_components:
# 		if not component.company:
# 			accounts.append((component.name, component.account, component.company))
# 		else:
# 			if component.company == filters["company"]:
# 				accounts.append((component.name, component.account, component.company))

# 	return accounts
# 	'''



# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, cstr, flt, getdate, get_first_day, today, get_last_day
from frappe.model.naming import make_autoname
from hrms.hr.hr_custom_function import get_payroll_settings, get_salary_tax, get_month_details
import math


import erpnext

from hrms.payroll.utils import sanitize_expression

class SalaryStructure(Document):
	def autoname(self):
		if not self.employee:
			frappe.throw(_("Employee field cannot be empty for autoname generation."))
		self.name = make_autoname(f"{self.employee}/.SST/.####")

	def validate(self):
		self.validate_dates()
		self.validate_amount()
		self.update_salary_structure()

	def validate_dates(self):
		joining_date, relieving_date = frappe.db.get_value(
			"Employee", self.employee, ["date_of_joining", "relieving_date"]
		)

		if self.from_date:
			existing_salary_structure = frappe.db.sql("""
				SELECT name FROM `tabSalary Structure`
				WHERE employee = %s
				AND is_active = 'Yes'
				AND from_date <= %s
				
			""", (self.employee, self.from_date), as_dict=True)

			if existing_salary_structure and existing_salary_structure[0]["name"] != self.name:
				frappe.throw(_("An active Salary Structure for this employee already exists."))


			if joining_date and getdate(self.from_date) < joining_date:
				frappe.throw(
					_("From Date {0} cannot be before employee's joining Date {1}").format(
						self.from_date, joining_date
					)
				)

			# flag - old_employee is for migrating the old employees data via patch
			if relieving_date and getdate(self.from_date) > relieving_date and not self.flags.old_employee:
				frappe.throw(
					_("From Date {0} cannot be after employee's relieving Date {1}").format(
						self.from_date, relieving_date
					)
				)

	def validate_amount(self):
		if flt(self.net_pay) <= 0: 
			frappe.throw(_("Net pay cannot be negative"))

	def validate_salary_component(self):
		dup = {}
		for parentfield in ['earnings', 'deductions']:
			parenttype = 'Earning' if parentfield == 'earnings' else 'Deduction'
			for i in self.get(parentfield):
				# Restricting users from entering earning component under deductions table and vice versa.
				component_type, is_loan_component = frappe.db.get_value("Salary Component", i.salary_component, ["type", "is_loan_component"])
				if parenttype != component_type:
					frappe.throw(_('Salary Component <b>`{1}`</b> of type <b>`{2}`</b> cannot be added under <b>`{3}`</b> table. <br/> <b><u>Reference# : </u></b> <a href="#Form/Salary Structure/{0}">{0}</a>').format(
						self.name, i.salary_component, component_type, parentfield.title()), title="Invalid Salary Component")
				# Checking duplicate entries
				if i.salary_component in ('Basic Pay') and i.salary_component in dup:
					frappe.throw(_("Row#{0} : Duplicate entries not allowed for component <b>{1}</b>.")
								 .format(i.idx, i.salary_component), title="Duplicate Record Found")
				else:
					dup.update({i.salary_component: 1})

				# Validate Loan details
				if parenttype == 'Deduction' and cint(is_loan_component):
					if not i.institution_name:
						frappe.throw(_("Row#{}: <b>Institution Name</b> is mandatory for <b>{}</b>").format(i.idx, i.salary_component))
					elif not i.reference_number:
						frappe.throw(_("Row#{}: <b>Loan Account No.(Reference Number)</b> is mandatory for <b>{}</b>").format(i.idx, i.salary_component))

	def get_active_amount(self, rec):
		''' return amount only if the component is active '''
		calc_amt = 0
		if rec.from_date or rec.to_date:
			if rec.to_date and str(rec.to_date) >= str(get_first_day(today())):
				calc_amt = rec.amount
			elif rec.from_date and str(rec.from_date) <= str(get_last_day(today())):
				calc_amt = rec.amount
			else:
				calc_amt = 0
		else:	
			calc_amt = rec.amount

		if rec.parentfield == "deductions":
			if not flt(rec.total_deductible_amount):
				calc_amt = calc_amt
			elif flt(rec.total_deductible_amount) and flt(rec.total_deductible_amount) != flt(rec.total_deducted_amount):
				calc_amt = calc_amt
			else:
				calc_amt = 0
				
		return flt(calc_amt)

	@frappe.whitelist()
	def update_salary_structure(self, new_basic_pay=0, remove_flag=1):
		'''
			This method calculates all the allowances and deductions based on the preferences
			set in the GUI. Calculated values are then checked and updated as follows.
					1) If the calculated component is missing in the existing earnings/deductions
						table then insert a new row.
					2) If the calculated component is found in the existing earnings/deductions
						table but amounts do not match, then update the respective row.
		'''
		self.validate_salary_component()
		

		basic_pay = comm_allowance = gis_amt = sws_amt = pf_amt = health_cont_amt = tax_amt = basic_pay_arrears = payscale_lower_limit= 0
		total_earning = total_deduction = net_pay = 0
		payscale_lower_limit = frappe.db.get_value("Employee Grade", frappe.db.get_value("Employee",self.employee,"grade"), "lower_limit")
		settings = get_payroll_settings(self.employee)
		settings = settings if settings else {}

		tbl_list = {'earnings': 'Earning', 'deductions': 'Deduction'}
		del_list_all = []
		
		for ed in ['earnings', 'deductions']:
			add_list = []
			del_list = []
			calc_map = []

			sst_map = {ed: []}
			for sc in frappe.db.sql("select * from `tabSalary Component` where `type`='{0}' and ifnull(field_name,'') != ''".format(tbl_list[ed]), as_dict=True):
				sst_map.setdefault(ed, []).append(sc)
			
			
			ed_map = [i.name for i in sst_map[ed]]
			#['Contract Allowance', 'Corporate Allowance', 'Fixed Allowance (Increment)', 'HRA', 'Monthly Variable Compensation (MVC)']
			# frappe.throw(frappe.as_json(self.get(ed)))
			for ed_item in self.get(ed):
				#self.get(ed) here fetch the details of the alraedy existed details
				
				# validate component validity dates
				if ed_item.from_date and ed_item.to_date and str(ed_item.to_date) < str(ed_item.from_date):
					frappe.throw(_("<b>Row#{}:</b> Invalid <b>From Date</b> for <b>{}</b> under <b>{}s</b>").format(ed_item.idx, ed_item.salary_component, tbl_list[ed]))

				# ed_item.amount = roundoff(ed_item.amount)
				ed_item.amount = flt(ed_item.amount)
				amount = ed_item.amount

				if ed_item.salary_component not in ed_map:
					if ed == 'earnings':
						if ed_item.salary_component == 'Basic Pay':
							
							if flt(new_basic_pay) > 0 and flt(new_basic_pay) != flt(amount):
								
								amount = flt(new_basic_pay)
							basic_pay = amount
							
							ed_item.amount = basic_pay
						elif frappe.db.exists("Salary Component", {"name": ed_item.salary_component, "is_pf_deductible": 1}):
							basic_pay_arrears += flt(ed_item.amount)
						total_earning += round(amount)
					else:
						if flt(ed_item.total_deductible_amount) == 0:
							total_deduction += amount
						else:
							if flt(ed_item.total_deductible_amount) != flt(ed_item.total_deducted_amount):
								total_deduction += round(amount)
				else:
					for m in sst_map[ed]:
						if m['name'] == ed_item.salary_component and not self.get(m['field_name']):
							del_list.append(ed_item)
							del_list_all.append(ed_item)

			if remove_flag:
				[self.remove(d) for d in del_list]

			# Calculating Earnings and Deductions based on preferences and values set
			# frappe.throw(frappe.as_json(sst_map[ed]))
			for m in sst_map[ed]:
				#basic,hra,eligible
				
				calc_amt = 0
				if self.get(m['field_method']) == 'Percent' and flt(self.get(m['field_value'])) < 0:
					frappe.throw(
						_("Percentage cannot be less than 0 for component <b>{0}</b>").format(m['name']), title="Invalid Data")
				elif self.get(m['field_method']) == 'Percent' and flt(self.get(m['field_value'])) > 200:
					frappe.throw(
						_("Percentage cannot exceed 200 for component <b>{0}</b>").format(m['name']), title="Invalid Data")

				if ed == 'earnings':
					# frappe.throw('hi')
					if self.get(m['field_name']):
						if self.get(m["field_method"]) == 'Percent':
							if m['based_on'] == 'Pay Scale Lower Limit':
								calc_amt = flt(payscale_lower_limit)*flt(self.get(m['field_value']))*0.01
							else:
								calc_amt = flt(basic_pay)*flt(self.get(m['field_value']))*0.01
						else:
							calc_amt = flt(self.get(m['field_value']))
				
						if m["field_name"] == "eligible_for_fixed_allowance":
							calc_amt = frappe.db.get_value("Employee Grade", self.employee_grade, "fixed_allowance")
						if m["field_name"] == "eligible_for_hra":
							payment_method = frappe.db.get_value("Salary Component", "HRA", "payment_method")
							cal_based = frappe.db.get_value("Salary Component", "HRA", "based_on")
							amount = frappe.db.get_value("Salary Component", "HRA", "amount")
							if not payment_method or not cal_based or not amount:
								frappe.throw('Add Payment Method, Calculation Based, Amount in salary component in HRA')
							if payment_method == 'Percent' and cal_based == 'Basic Pay' and amount:
								calc_amt = (flt(basic_pay) * flt(amount) / 100)
							if payment_method == 'Lumpsum' and amount:
								# frappe.throw(str(amount))
								calc_amt = (flt(amount))
						if m["field_name"] == "eligible_for_conveyance_allowance":
							payment_method = frappe.db.get_value("Salary Component", "Conveyance Allowance", "payment_method")
							amount = frappe.db.get_value("Salary Component", "Conveyance Allowance", "amount")
							if payment_method == 'Lumpsum' and amount:
								# frappe.throw(str(amount))

								calc_amt = (flt(amount))
							# calc_amt = roundoff(hra_amount)
							# frappe.throw(str(calc_amt))
							# calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
						
						# calc_amt = roundoff(calc_amt)
						calc_amt = flt(calc_amt)
						comm_allowance += flt(calc_amt) if m['name'] == 'Communication Allowance' else 0
						total_earning += calc_amt
						calc_map.append({'salary_component': m['name'], 'amount': calc_amt})
				else:
					# frappe.throw('hello')
					if self.get(m['field_name']) and m['name'] == 'SWS':
						sws_amt = flt(settings.get('sws'))
						# calc_amt = roundoff(sws_amt)
						calc_amt = flt(sws_amt)
						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

					elif self.get(m['field_name']) and m['name'] == 'GIS':
						gis_amt = flt(settings.get("gis"))
						# calc_amt = roundoff(gis_amt)
						calc_amt = flt(gis_amt)
						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

					elif self.get(m['field_name']) and m['name'] == 'PF':
						pf_amt = (flt(basic_pay)+flt(basic_pay_arrears))*flt(settings.get("employee_pf"))*0.01
						# calc_amt = roundoff(pf_amt)
						calc_amt = flt(pf_amt)
						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})

					elif self.get(m['field_name']) and m['name'] == 'Health Contribution':
						health_cont_amt = flt(total_earning)*flt(settings.get("health_contribution"))*0.01
						# calc_amt = roundoff(health_cont_amt)
						calc_amt = flt(health_cont_amt)
						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
					elif self.get(m['field_name']) and m['name'] == 'HRA':
						# frappe.throw('hra')
						# health_cont_amt = flt(total_earning)*flt(settings.get("health_contribution"))*0.01
						payment_method = frappe.db.get_value("Salary Component", "HRA", "payment_method")
						cal_based = frappe.db.get_value("Salary Component", "HRA", "based_on")
						amount = frappe.db.get_value("Salary Component", "HRA", "amount")
						if not payment_method or not cal_based or not amount:
							frappe.throw('Add Payment Method, Calculation Based, Amount in salary component in HRA')
						if payment_method == 'Percent' and cal_based == 'Basic Pay' and amount:
							hra_amount = (flt(basic_pay) * flt(amount) / 100)
						# calc_amt = roundoff(hra_amount)
						calc_amt = flt(hra_amount)
						calc_map.append({'salary_component': m['name'], 'amount': flt(calc_amt)})
					else:
						calc_amt = 0
					# frappe.throw('hi')
					total_deduction += calc_amt

			# Calculating Salary Tax
			if ed == 'deductions':
				calc_amt = get_salary_tax(math.floor(flt(total_earning)-flt(pf_amt)-flt(gis_amt)-(comm_allowance*0.5)))
				# calc_amt = roundoff(calc_amt)
				calc_amt = flt(calc_amt)
				total_deduction += calc_amt
				calc_map.append({'salary_component': 'Salary Tax', 'amount': flt(calc_amt)})

			# Updating existing Earnings and Deductions tables
			for c in calc_map:
				found = 0
				for ed_item in self.get(ed):
					if str(ed_item.salary_component) == str(c['salary_component']):
						found = 1
						if flt(ed_item.amount) != flt(c['amount']):
							ed_item.amount = flt(c['amount'])
						break

				if not found:
					add_list.append(c)
			
			[self.append(ed, i) for i in add_list]
		
		
		self.total_earning   = sum([self.get_active_amount(rec) for rec in self.get("earnings")])
		self.total_deduction = sum([self.get_active_amount(rec) for rec in self.get("deductions")])
		self.net_pay = flt(self.total_earning) - flt(self.total_deduction)

		if flt(self.total_earning)-flt(self.total_deduction) < 0 and not self.get('__unsaved'):
			frappe.throw(_("Total deduction cannot be more than total earning"), title="Invalid Data")
		
		return del_list_all

def roundoff(amount):
	return math.ceil(amount) if (amount - int(amount)) >= 0.5 else math.floor(amount)


# @frappe.whitelist()
# def make_salary_slip(
# 	source_name,
# 	target_doc=None,
# 	employee=None,
# 	posting_date=None,
# 	as_print=False,
# 	print_format=None,
# 	for_preview=0,
# 	ignore_permissions=False,
# ):
# 	def postprocess(source, target):
# 		if employee:
# 			target.employee = employee
# 			if posting_date:
# 				target.posting_date = posting_date

# 		target.run_method("process_salary_structure", for_preview=for_preview)

# 	doc = get_mapped_doc(
# 		"Salary Structure",
# 		source_name,
# 		{
# 			"Salary Structure": {
# 				"doctype": "Salary Slip",
# 				"field_map": {
# 					"total_earning": "gross_pay",
# 					"name": "salary_structure",
# 				},
# 			}
# 		},
# 		target_doc,
# 		postprocess,
# 		ignore_child_tables=True,
# 		ignore_permissions=ignore_permissions,
# 		cached=True,
# 	)

# 	if cint(as_print):
# 		doc.name = f"Preview for {employee}"
# 		return frappe.get_print(doc.doctype, doc.name, doc=doc, print_format=print_format)
# 	else:
# 		return doc



@frappe.whitelist()
def make_salary_slip(
    source_name,
    target_doc=None,
    employee=None,
    posting_date=None,
    as_print=False,
    print_format=None,
    for_preview=0,
    ignore_permissions=False,
):
    def postprocess(source, target):
        if employee:
            target.employee = employee
        if posting_date:
            target.posting_date = posting_date

        salary_details = frappe.get_all(
            "Salary Detail",
            filters={"parent": source.name},
            fields=["salary_component", "from_date", "to_date"]
        )

        if not salary_details:
            frappe.throw("No Salary Details found in Salary Structure.")
        structure_from_date = min([d.from_date for d in salary_details if d.from_date])
        structure_to_date = max([d.to_date for d in salary_details if d.to_date])
        target.start_date = structure_from_date
        target.end_date = structure_to_date
        target.run_method("process_salary_structure", for_preview=for_preview)

        def filter_rows(rows):
            filtered = []
            for row in rows:
                if not row.from_date:
                    row.from_date = structure_from_date
                if not row.to_date:
                    row.to_date = structure_to_date
                filtered.append(row)
            return filtered

        target.set("deductions", filter_rows(target.get("deductions")))
        target.set("earnings", filter_rows(target.get("earnings")))

    doc = get_mapped_doc(
        "Salary Structure",
        source_name,
        {
            "Salary Structure": {
                "doctype": "Salary Slip",
                "field_map": {
                    "total_earning": "gross_pay",
                    "name": "salary_structure",
                },
            }
        },
        target_doc,
        postprocess,
        ignore_child_tables=True,
        ignore_permissions=ignore_permissions,
        cached=True,
    )

    if cint(as_print):
        doc.name = f"Preview for {employee}"
        return frappe.get_print(doc.doctype, doc.name, doc=doc, print_format=print_format)
    else:
        return doc

def get_assigned_salary_structure(employee, on_date):
	if not employee or not on_date:
		return None
	salary_structure = frappe.db.sql(
		"""
		select name from `tabSalary Structure Assignment`
		where employee=%(employee)s
		and docstatus = 1
		and %(on_date)s >= from_date order by from_date desc limit 1""",
		{
			"employee": employee,
			"on_date": on_date,
		},
	)
	return salary_structure[0][0] if salary_structure else None

@frappe.whitelist()
def get_employee_currency(employee):
	employee_currency = frappe.db.get_value("Salary Structure", {"employee": employee}, "currency")
	if not employee_currency:
		frappe.throw(
			_("There is no Salary Structure assigned to {0}. First assign a Salary Stucture.").format(
				employee
			)
		)
	return employee_currency

	'''
	def before_validate(self):
		self.sanitize_condition_and_formula_fields()

	def before_update_after_submit(self):
		self.sanitize_condition_and_formula_fields()

	def validate(self):
		self.set_missing_values()
		self.validate_amount()
		self.validate_max_benefits_with_flexi()
		self.validate_component_based_on_tax_slab()
		self.validate_payment_days_based_dependent_component()
		self.validate_timesheet_component()
		self.validate_formula_setup()

	def on_update(self):
		self.reset_condition_and_formula_fields()

	def on_update_after_submit(self):
		self.reset_condition_and_formula_fields()

	def validate_formula_setup(self):
		for table in ["earnings", "deductions"]:
			for row in self.get(table):
				if not row.amount_based_on_formula and row.formula:
					frappe.msgprint(
						_(
							"{0} Row #{1}: Formula is set but {2} is disabled for the Salary Component {3}."
						).format(
							table.capitalize(),
							row.idx,
							frappe.bold(_("Amount Based on Formula")),
							frappe.bold(row.salary_component),
						),
						title=_("Warning"),
						indicator="orange",
					)

	def set_missing_values(self):
		overwritten_fields = [
			"depends_on_payment_days",
			"variable_based_on_taxable_salary",
			"is_tax_applicable",
			"is_flexible_benefit",
		]
		overwritten_fields_if_missing = ["amount_based_on_formula", "formula", "amount"]
		for table in ["earnings", "deductions"]:
			for d in self.get(table):
				component_default_value = frappe.db.get_value(
					"Salary Component",
					cstr(d.salary_component),
					overwritten_fields + overwritten_fields_if_missing,
					as_dict=1,
				)
				if component_default_value:
					for fieldname in overwritten_fields:
						value = component_default_value.get(fieldname)
						if d.get(fieldname) != value:
							d.set(fieldname, value)

					if not (d.get("amount") or d.get("formula")):
						for fieldname in overwritten_fields_if_missing:
							d.set(fieldname, component_default_value.get(fieldname))

	def validate_component_based_on_tax_slab(self):
		for row in self.deductions:
			if row.variable_based_on_taxable_salary and (row.amount or row.formula):
				frappe.throw(
					_(
						"Row #{0}: Cannot set amount or formula for Salary Component {1} with Variable Based On Taxable Salary"
					).format(row.idx, row.salary_component)
				)

	def validate_amount(self):
		if flt(self.net_pay) < 0 and self.salary_slip_based_on_timesheet:
			frappe.throw(_("Net pay cannot be negative"))

	def validate_payment_days_based_dependent_component(self):
		abbreviations = self.get_component_abbreviations()
		for component_type in ("earnings", "deductions"):
			for row in self.get(component_type):
				if (
					row.formula
					and row.depends_on_payment_days
					# check if the formula contains any of the payment days components
					and any(re.search(r"\b" + abbr + r"\b", row.formula) for abbr in abbreviations)
				):
					message = _("Row #{0}: The {1} Component has the options {2} and {3} enabled.").format(
						row.idx,
						frappe.bold(row.salary_component),
						frappe.bold(_("Amount based on formula")),
						frappe.bold(_("Depends On Payment Days")),
					)
					message += "<br><br>" + _(
						"Disable {0} for the {1} component, to prevent the amount from being deducted twice, as its formula already uses a payment-days-based component."
					).format(frappe.bold(_("Depends On Payment Days")), frappe.bold(row.salary_component))
					frappe.throw(message, title=_("Payment Days Dependency"))

	def get_component_abbreviations(self):
		abbr = [d.abbr for d in self.earnings if d.depends_on_payment_days]
		abbr += [d.abbr for d in self.deductions if d.depends_on_payment_days]

		return abbr

	def validate_timesheet_component(self):
		if not self.salary_slip_based_on_timesheet:
			return

		for component in self.earnings:
			if component.salary_component == self.salary_component:
				frappe.msgprint(
					_(
						"Row #{0}: Timesheet amount will overwrite the Earning component amount for the Salary Component {1}"
					).format(self.idx, frappe.bold(self.salary_component)),
					title=_("Warning"),
					indicator="orange",
				)
				break

	def sanitize_condition_and_formula_fields(self):
		for table in ("earnings", "deductions"):
			for row in self.get(table):
				row.condition = row.condition.strip() if row.condition else ""
				row.formula = row.formula.strip() if row.formula else ""
				row._condition, row.condition = row.condition, sanitize_expression(row.condition)
				row._formula, row.formula = row.formula, sanitize_expression(row.formula)

	def reset_condition_and_formula_fields(self):
		# set old values (allowing multiline strings for better readability in the doctype form)
		for table in ("earnings", "deductions"):
			for row in self.get(table):
				row.condition = row._condition
				row.formula = row._formula

		self.db_update_all()

	def validate_max_benefits_with_flexi(self):
		have_a_flexi = False
		if self.earnings:
			flexi_amount = 0
			for earning_component in self.earnings:
				if earning_component.is_flexible_benefit == 1:
					have_a_flexi = True
					max_of_component = frappe.db.get_value(
						"Salary Component", earning_component.salary_component, "max_benefit_amount"
					)
					flexi_amount += max_of_component

			if have_a_flexi and flt(self.max_benefits) == 0:
				frappe.throw(_("Max benefits should be greater than zero to dispense benefits"))
			if have_a_flexi and flexi_amount and flt(self.max_benefits) > flexi_amount:
				frappe.throw(
					_(
						"Total flexible benefit component amount {0} should not be less than max benefits {1}"
					).format(flexi_amount, self.max_benefits)
				)
		if not have_a_flexi and flt(self.max_benefits) > 0:
			frappe.throw(
				_("Salary Structure should have flexible benefit component(s) to dispense benefit amount")
			)

	def get_employees(self, **kwargs):
		conditions, values = [], []
		for field, value in kwargs.items():
			if value:
				conditions.append(f"{field}=%s")
				values.append(value)

		condition_str = " and " + " and ".join(conditions) if conditions else ""

		# nosemgrep: frappe-semgrep-rules.rules.frappe-using-db-sql
		employees = frappe.db.sql_list(
			f"select name from tabEmployee where status='Active' {condition_str}",
			tuple(values),
		)

		return employees

	@frappe.whitelist()
	def assign_salary_structure(
		self,
		branch=None,
		grade=None,
		department=None,
		designation=None,
		employee=None,
		payroll_payable_account=None,
		from_date=None,
		base=None,
		variable=None,
		income_tax_slab=None,
	):
		employees = self.get_employees(
			company=self.company,
			grade=grade,
			department=department,
			designation=designation,
			name=employee,
			branch=branch,
		)

		if employees:
			if len(employees) > 20:
				frappe.enqueue(
					assign_salary_structure_for_employees,
					timeout=3000,
					employees=employees,
					salary_structure=self,
					payroll_payable_account=payroll_payable_account,
					from_date=from_date,
					base=base,
					variable=variable,
					income_tax_slab=income_tax_slab,
				)
			else:
				assign_salary_structure_for_employees(
					employees,
					self,
					payroll_payable_account=payroll_payable_account,
					from_date=from_date,
					base=base,
					variable=variable,
					income_tax_slab=income_tax_slab,
				)
		else:
			frappe.msgprint(_("No Employee Found"))


def assign_salary_structure_for_employees(
	employees,
	salary_structure,
	payroll_payable_account=None,
	from_date=None,
	base=None,
	variable=None,
	income_tax_slab=None,
):
	assignments = []
	existing_assignments_for = get_existing_assignments(employees, salary_structure, from_date)
	count = 0
	savepoint = "before_assignment_submission"

	for employee in employees:
		try:
			frappe.db.savepoint(savepoint)
			if employee in existing_assignments_for:
				continue

			count += 1

			assignment = create_salary_structure_assignment(
				employee,
				salary_structure.name,
				salary_structure.company,
				salary_structure.currency,
				from_date,
				payroll_payable_account,
				base,
				variable,
				income_tax_slab,
			)
			assignments.append(assignment)
			frappe.publish_progress(
				count * 100 / len(set(employees) - set(existing_assignments_for)),
				title=_("Assigning Structures..."),
			)
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(
				f"Salary Structure Assignment failed for employee {employee}",
				reference_doctype="Salary Structure Assignment",
			)

	if assignments:
		frappe.msgprint(_("Structures have been assigned successfully"))


def create_salary_structure_assignment(
	employee,
	salary_structure,
	company,
	currency,
	from_date,
	payroll_payable_account=None,
	base=None,
	variable=None,
	income_tax_slab=None,
):
	assignment = frappe.new_doc("Salary Structure Assignment")

	if not payroll_payable_account:
		payroll_payable_account = frappe.db.get_value("Company", company, "default_payroll_payable_account")
		if not payroll_payable_account:
			frappe.throw(_('Please set "Default Payroll Payable Account" in Company Defaults'))

	payroll_payable_account_currency = frappe.db.get_value(
		"Account", payroll_payable_account, "account_currency"
	)
	company_curency = erpnext.get_company_currency(company)
	if payroll_payable_account_currency != currency and payroll_payable_account_currency != company_curency:
		frappe.throw(
			_("Invalid Payroll Payable Account. The account currency must be {0} or {1}").format(
				currency, company_curency
			)
		)

	assignment.employee = employee
	assignment.salary_structure = salary_structure
	assignment.company = company
	assignment.currency = currency
	assignment.payroll_payable_account = payroll_payable_account
	assignment.from_date = from_date
	assignment.base = base
	assignment.variable = variable
	assignment.income_tax_slab = income_tax_slab
	assignment.save(ignore_permissions=True)
	assignment.submit()

	return assignment.name


def get_existing_assignments(employees, salary_structure, from_date):
	# nosemgrep: frappe-semgrep-rules.rules.frappe-using-db-sql
	salary_structures_assignments = frappe.db.sql_list(
		f"""
		SELECT DISTINCT employee FROM `tabSalary Structure Assignment`
		WHERE salary_structure=%s AND employee IN ({", ".join(["%s"] * len(employees))})
		AND from_date=%s AND company=%s AND docstatus=1
		""",
		[salary_structure.name, *employees, from_date, salary_structure.company],
	)
	if salary_structures_assignments:
		frappe.msgprint(
			_(
				"Skipping Salary Structure Assignment for the following employees, as Salary Structure Assignment records already exists against them. {0}"
			).format("\n".join(salary_structures_assignments))
		)
	return salary_structures_assignments


@frappe.whitelist()
def get_employees(salary_structure):
	employees = frappe.get_list(
		"Salary Structure Assignment",
		filters={"salary_structure": salary_structure, "docstatus": 1},
		pluck="employee",
	)

	if not employees:
		frappe.throw(
			_(
				"There's no Employee with Salary Structure: {0}. Assign {1} to an Employee to preview Salary Slip"
			).format(salary_structure, salary_structure)
		)

	return list(set(employees))


@frappe.whitelist()
def get_salary_component(doctype, txt, searchfield, start, page_len, filters):
	sc = frappe.qb.DocType("Salary Component")
	sca = frappe.qb.DocType("Salary Component Account")

	salary_components = (
		frappe.qb.from_(sc)
		.left_join(sca)
		.on(sca.parent == sc.name)
		.select(sc.name, sca.account, sca.company)
		.where(
			(sc.type == filters.get("component_type"))
			& (sc.disabled == 0)
			& (sc[searchfield].like(f"%{txt}%") | sc.name.like(f"%{txt}%"))
		)
		.limit(page_len)
		.offset(start)
	).run(as_dict=True)

	accounts = []
	for component in salary_components:
		if not component.company:
			accounts.append((component.name, component.account, component.company))
		else:
			if component.company == filters["company"]:
				accounts.append((component.name, component.account, component.company))

	return accounts
	'''