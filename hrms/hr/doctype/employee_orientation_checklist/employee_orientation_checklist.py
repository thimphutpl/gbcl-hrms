# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class EmployeeOrientationChecklist(Document):
	# pass
	@frappe.whitelist()
	def get_employee_orientation(self):
		"""Fetch tasks from Pre Arrival Tasks using SQL queries"""
		
		# Check if any Pre Arrival Tasks document exists
		pre_arrival_exists = frappe.db.sql("""
			SELECT name 
			FROM `tabPre Arrival Task` 
			WHERE docstatus < 2
		""")
		
		if not pre_arrival_exists:
			frappe.throw(_("No Pre Arrival Tasks document found. Please create one first."))
		
		# Get the most recent Pre Arrival Tasks document
		latest_pre_arrival = frappe.db.sql("""
			SELECT name 
			FROM `tabPre Arrival Task` 
			WHERE docstatus < 2 
			ORDER BY creation DESC 
		""", as_dict=True)
		
		if not latest_pre_arrival:
			frappe.throw(_("No valid Pre Arrival Tasks document found."))
		
		pre_arrival_name = latest_pre_arrival[0].name
		
		# Clear existing items first
		self.set("employee_orientation_checklist_item", [])
		self.set("first_day_orientation", [])
		self.set("tour_supervisor", [])
		self.set("communications_supervisor", [])
		self.set("technology_and_equipment", [])
		self.set("workspace_supervisor", [])
		self.set("facility_supervisor", [])
		self.set("attendance_supervisor", [])
		self.set("financial_procedures", [])
		self.set("benefits_employee", [])
		self.set("new_hire_training", [])
		self.set("supervisor_information", [])
		self.set("performance", [])
		self.set("gmc_policies", [])
		
		# Fetch items using SQL
		items = frappe.db.sql("""
			SELECT task, description, responsible 
			FROM `tabPre Arrival Tasks Item` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch orientation items using SQL
		orientations = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabFirst Day Orientation Item` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)

		# Fetch Tour Supervisor items using SQL
		tour_supervisor = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabTour Supervisor` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)

		# Fetch Tour Supervisor items using SQL
		technology_and_equipment = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabTechnology and Equipment` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)

		# Fetch Communication Supervisor items using SQL
		communications_supervisor = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabCommunication Supervisor` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)

		# Fetch Workspace Supervisor items using SQL
		workspace_supervisor = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabWorkspace Supervisor` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch Facility Supervisor items using SQL
		facility_supervisor = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabFacility Supervisor` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch Attendance Supervisor items using SQL
		attendance_supervisor = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabAttendance Supervisor` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch Financial Procedures items using SQL
		financial_procedures = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabFinancial Procedures` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch Benefits Employee items using SQL
		benefits_employee = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabBenefits Employee` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch New Hiring Training items using SQL
		new_hire_training = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabNew Hiring Training` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch Supervisor Information items using SQL
		supervisor_information = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabSupervisor Information` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch PErformance Supervisor items using SQL
		performance = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabPerformance` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		# Fetch GMC Policies Supervisor items using SQL
		gmc_policies = frappe.db.sql("""
			SELECT task, day, week, month 
			FROM `tabGMC Policies` 
			WHERE parent = %s AND parenttype = 'Pre Arrival Task'
			ORDER BY idx
		""", pre_arrival_name, as_dict=True)
		
		
		# Populate child tables
		if items:
			for item in items:
				self.append("items", {
					"task": item.task,
					"description": item.description or "",
					"responsible": item.responsible or ""
				})
		else:
			frappe.msgprint(_("No items found in Pre Arrival Tasks"), alert=True)
		
		if orientations:
			for orient in orientations:
				self.append("orientations", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if tour_supervisor:
			for orient in tour_supervisor:
				self.append("tour_supervisor", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if communications_supervisor:
			for orient in communications_supervisor:
				self.append("communications_supervisor", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if technology_and_equipment:
			for orient in tour_supervisor:
				self.append("technology_and_equipment", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if workspace_supervisor:
			for orient in workspace_supervisor:
				self.append("workspace_supervisor", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if facility_supervisor:
			for orient in facility_supervisor:
				self.append("facility_supervisor", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if attendance_supervisor:
			for orient in attendance_supervisor:
				self.append("attendance_supervisor", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if financial_procedures:
			for orient in financial_procedures:
				self.append("financial_procedures", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if benefits_employee:
			for orient in benefits_employee:
				self.append("benefits_employee", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if new_hire_training:
			for orient in new_hire_training:
				self.append("new_hire_training", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if supervisor_information:
			for orient in supervisor_information:
				self.append("supervisor_information", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if performance:
			for orient in performance:
				self.append("performance", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)

		if gmc_policies:
			for orient in gmc_policies:
				self.append("gmc_policies", {
					"task": orient.task,
					"day": orient.day or 0,
					"week": orient.week or 0,
					"month": orient.month or 0
				})
		else:
			frappe.msgprint(_("No orientation tasks found in Pre Arrival Tasks"), alert=True)
					
		
		# Save only if we got data
		if self.get("items") or self.get("orientations") or self.get("tour_supervisor") or self.get("communications_supervisor") or self.get("technology_and_equipment") or self.get("workspace_supervisor") or self.get("facility_supervisor") or self.get("attendance_supervisor") or self.get("financial_procedures") or self.get("benefits_employee") or self.get("new_hire_training") or self.get("supervisor_information") or self.get("performance") or self.get("tour_sgmc_policiesupervisor"):
			self.save()
			frappe.msgprint(_("Employee Orientation tasks fetched successfully"))
		else:
			frappe.throw(_("No data was fetched from Pre Arrival Tasks"))



# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe import _

# class EmployeeOrientationChecklist(Document):
#     @frappe.whitelist()
#     def get_employee_orientation(self):
#         """Fetch tasks from Pre Arrival Tasks with duplicate prevention"""
        
#         # Check if we already have items (prevent duplicate fetches)
#         if self.get("items") or self.get("orientations"):
#             frappe.msgprint(_("Tasks already fetched. To fetch again, please clear existing items first."))
#             return False
        
#         # Check if any Pre Arrival Tasks document exists
#         pre_arrival_exists = frappe.db.sql("""
#             SELECT name 
#             FROM `tabPre Arrival Task` 
#             WHERE docstatus < 2 
#             LIMIT 1
#         """)
        
#         if not pre_arrival_exists:
#             frappe.throw(_("No Pre Arrival Tasks document found. Please create one first."))
        
#         # Get the most recent Pre Arrival Tasks document
#         latest_pre_arrival = frappe.db.sql("""
#             SELECT name 
#             FROM `tabPre Arrival Task` 
#             WHERE docstatus < 2 
#             ORDER BY creation DESC 
#             LIMIT 1
#         """, as_dict=True)
        
#         if not latest_pre_arrival:
#             frappe.throw(_("No valid Pre Arrival Tasks document found."))
        
#         pre_arrival_name = latest_pre_arrival[0].name
        
#         # Fetch items using SQL
#         items = frappe.db.sql("""
#             SELECT task, description, responsible 
#             FROM `tabPre Arrival Tasks Item` 
#             WHERE parent = %s AND parenttype = 'Pre Arrival Task'
#             ORDER BY idx
#         """, pre_arrival_name, as_dict=True)
        
#         # Fetch orientation items using SQL
#         orientations = frappe.db.sql("""
#             SELECT task, day, week, month 
#             FROM `tabFirst Day Orientation Item` 
#             WHERE parent = %s AND parenttype = 'Pre Arrival Task'
#             ORDER BY idx
#         """, pre_arrival_name, as_dict=True)
        
#         # Populate child tables
#         fetched_data = False
        
#         if items:
#             for item in items:
#                 self.append("items", {
#                     "task": item.task,
#                     "description": item.description or "",
#                     "responsible": item.responsible or ""
#                 })
#             fetched_data = True
        
#         if orientations:
#             for orient in orientations:
#                 self.append("orientations", {
#                     "task": orient.task,
#                     "day": orient.day or 0,
#                     "week": orient.week or 0,
#                     "month": orient.month or 0
#                 })
#             fetched_data = True
        
#         if not fetched_data:
#             frappe.throw(_("No data was fetched from Pre Arrival Tasks"))
        
#         # Refresh the form without saving
#         return True