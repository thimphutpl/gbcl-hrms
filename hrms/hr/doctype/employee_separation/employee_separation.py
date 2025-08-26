# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from hrms.controllers.employee_boarding_controller import EmployeeBoardingController


import frappe
from frappe.model.mapper import get_mapped_doc
# from erpnext.custom_workflow import validate_workflow_states, notify_workflow_states
from frappe.utils import today

class EmployeeSeparation(EmployeeBoardingController):
	def validate(self):
		super(EmployeeSeparation, self).validate()
		# validate_workflow_states(self)
		# notify_workflow_states(self)

	def on_submit(self):
		super(EmployeeSeparation, self).on_submit()

	def on_cancel(self):
		super(EmployeeSeparation, self).on_cancel()

	def before_save(self):
		# Check if the employee is already associated with another Employee Separation document
		existing_separation = frappe.db.exists("Employee Separation", {
			"employee": self.employee,
			"name": ("!=", self.name),  # Exclude the current document
			"docstatus": ("!=", 2)  # Exclude cancelled documents
		})

		if existing_separation:
			frappe.throw(f"Employee {self.employee} is already created with another Employee Separation document: {existing_separation}") 	
  
@frappe.whitelist()
def make_employee_benefit(source_name, target_doc=None, skip_item_mapping=False):
	def update_item(source, target, source_parent):
		# target.purpose = "Separation"
		target.employee_separation_id = source.name
		target.grade = source.employee_grade
	mapper = {
		"Employee Separation": {
			"doctype": "Employee Benefits",
			"fieldmap": {
				"name": "employee_separation_id",
				"employee_grade": "grade",
			},
			"postprocess": update_item
		},
	}

	target_doc = get_mapped_doc("Employee Separation", source_name, mapper, target_doc)

	return target_doc

@frappe.whitelist()
def make_separation_clearance(source_name, target_doc=None, skip_item_mapping=False):
	def update_item(source_doc, target_doc, source_parent):
		target_doc.employee_separation_id = source_doc.name
		target_doc.cid = frappe.db.get_value("Employee",source_doc.employee,"passport_number")
		target_doc.phone_number = frappe.db.get_value("Employee",source_doc.employee,"cell_number")
		target_doc.grade = source_doc.employee_grade
		target_doc.approver = None
		target_doc.approver_name = None
		target_doc.approver_designation = None
	mapper = {
		"Employee Separation": {
			"doctype": "Employee Separation Clearance",
			"field_map":{
				"name": "employee_separation_id",
				"employee_grade": "grade",
			},
			"postprocess": update_item,
		},
		
	}

	target_doc = get_mapped_doc("Employee Separation", source_name, mapper, target_doc)

	return target_doc

@frappe.whitelist()
def make_exit_interview(source_name, target_doc=None):

    doc = get_mapped_doc(
        "Employee Separation",
        source_name,
        {
            "Employee Separation": {
                "doctype": "Exit Interview",
                "field_map": {
					"name":"employee_separation",
                    "employee": "employee",
					"reason_for_resignation": "resignation_type",
					"expected_relieving_date": "date_of_separation"
                },                
            },
        },
        target_doc,
    )
    return doc

# Following code added by SHIV on 2020/09/21
def get_permission_query_conditions(user):
	if not user: user = frappe.session.user
	user_roles = frappe.get_roles(user)

	if user == "Administrator":
		return
	if "HR User" in user_roles or "HR Manager" in user_roles or "Approver" in user_roles:
		return

	return """(
		`tabEmployee Separation`.owner = '{user}' and `tabEmployee Separation`.docstatus = 0
		or
		exists(select 1
				from `tabEmployee`
				where `tabEmployee`.name = `tabEmployee Separation`.employee
				and `tabEmployee`.user_id = '{user}')
		or
		(`tabEmployee Separation`.approver = '{user}' and `tabEmployee Separation`.workflow_state not in ('Draft','Submitted','Rejected','Cancelled') and `tabEmployee Separation`.docstatus = 0)
	)""".format(user=user)

