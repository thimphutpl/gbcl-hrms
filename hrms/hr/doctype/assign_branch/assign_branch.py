# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AssignBranch(Document):
	def validate(self):
		self.assign_name()	
		# self.check_mandatory()
		self.check_employee_duplicate()
		self.check_duplicate()


	def check_mandatory(self):
		if not self.user:
			frappe.throw("User Id is Mandatory")	

	def assign_name(self):
		if not self.employee:
			frappe.throw(_("Employee ID is Mandatory"))

		emp = frappe.get_doc(self.employee_type, self.employee)

		if self.employee_type == "User":
			self.user = emp.get("name")
			self.employee_name = emp.get("full_name")
		elif self.employee_type == "Muster Roll Employee":
			self.employee_name = emp.get("person_name")
		else:    
			self.user = emp.get("user_id")
			self.company = emp.get("company")
			self.current_branch = emp.get("branch")
			self.employee_name = emp.get("employee_name")

	def check_employee_duplicate(self):
		docs = frappe.db.sql("select name from `tabAssign Branch` where employee = %s and user = %s and name != %s", (self.employee, self.user, self.name), as_dict=True)
		if docs:
			frappe.throw("The Employee has been already assigned Branch through <b>" + str(docs[0].name) + "</b>")

	def check_duplicate(self):		
		for a in self.items:
			for b in self.items:
				if a.branch == b.branch and a.idx != b.idx:
					frappe.throw("Duplicate Entries in row " + str(a.idx) + " and " + str(b.idx))

	def assign_branch(self):
		#Clear user branch permissions 
		user_perms = frappe.defaults.get_user_permissions(self.user)
		for doc, names in user_perms.items():
			if doc == 'Branch':
				for a in names:
					frappe.permissions.remove_user_permission(doc, a, self.user)
			
		#Add the branch permissions back as per assigned branches
		frappe.permissions.add_user_permission("Branch", self.current_branch, self.user)
		for a in self.items:
			frappe.permissions.add_user_permission('Branch', a.branch, self.user)

		frappe.msgprint("Branch Assigned")

	#Populate branches with active branches 
	@frappe.whitelist()
	def get_all_branches(self):
		query = "select name as branch from tabBranch where disabled != 1" 
		entries = frappe.db.sql(query, as_dict=True)
		self.set('items', [])

		for d in entries:
			row = self.append('items', {})
			row.update(d)

