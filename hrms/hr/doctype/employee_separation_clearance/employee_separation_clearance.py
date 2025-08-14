# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.custom_workflow import validate_workflow_states, notify_workflow_states
from hrms.hr.hr_custom_function import get_officiating_employee

class EmployeeSeparationClearance(Document):
	def validate(self):
		self.check_duplicates()
		self.set_approvers()
		self.workflow_action()

	def on_submit(self):
		self.check_signatures()
		self.update_reference()
		# self.send_notification()


	def workflow_action(self):  
		action = frappe.request.form.get('action')
		
		if action == "Save":
			self.verifyUpdate()           
			if self.icthr_clearance + self.ada_clearance + self.afd_clearance + self.iad_clearance + self.ams_clearance + self.pc_clearance == 6:
				self.verifyUpdate()
				self.verifyUpdate()
		
		if action == "Reapply":
			em = frappe.db.sql("Select user_id from `tabEmployee` where name='{}'".format(self.employee), as_dict=True)
			if frappe.session.user != em[0].user_id:
				frappe.throw("You cannot apply for another employee.")
			self.reApply()

	def verifyUpdate(self):
		user = frappe.session.user
		
		if user == self.iad:
			self.iad_clearance = 1
		if user == self.icthr:
			self.icthr_clearance = 1
		if user == self.afd:
			self.afd_clearance = 1
		if user == self.ams:
			self.ams_clearance = 1
		if user == self.pc:
			self.pc_clearance = 1
		if user == self.ada:
			self.ada_clearance = 1
		if user == self.supervisor:
			self.supervisor_clearance = 1
		if user == self.gm:
			self.gm_clearance = 1

	def reApply(self):
		self.iad_clearance = 0
		self.afd_clearance = 0
		self.icthr_clearance = 0
		self.ada_clearance = 0
		self.ams_clearance = 0
		self.pc_clearance = 0
		self.supervisor_clearance = 0
		self.gm_clearance = 0

		self.iad_remarks = ""
		self.afd_remarks = ""
		self.icthr_remarks = ""
		self.ada_remarks = ""
		self.ams_remarks = ""
		self.pc_remarks = ""
		self.supervisor_remarks = ""
		self.gm_remarks = ""

	def on_cancel(self):
		self.update_reference()
			
	def check_signatures(self):
		if self.supervisor_clearance == 0:
			frappe.throw("Supervisor has not granted clearance.")
		if self.afd_clearance == 0:
			frappe.throw("Finance and Investment has not granted clearance.")
		# if self.ams_clearance == 0:
		# 	frappe.throw("Asset Management Section has not granted clearance.")
		if self.icthr_clearance == 0:
			frappe.throw("Human Resource & Administration has not granted clearance.")
		# if self.iad_clearance == 0:
		# 	frappe.throw("Internal Audit has not granted clearance.")
		if self.ada_clearance == 0:
			frappe.throw("Asset Declaration Administrator has not granted clearance.")
		# if self.pc_clearance == 0:
		# 	frappe.throw("Procurement and Contracts has not granted clearance.")

	def update_reference(self):
		id = frappe.get_doc("Employee Separation",self.employee_separation_id)
		id.clearance_acquired = 1 if self.docstatus == 1 else 0
		id.save()

	def check_duplicates(self):
		duplicates = frappe.db.sql("""
			select name from `tabEmployee Separation Clearance` where employee_separation_id = '{0}'  and name != '{1}' and docstatus != 2
				""".format(self.employee_separation_id,self.name))
		if duplicates:
			frappe.throw("There is already a pending Separation Clearance created for the Employee Separation '{}'".format(self.employee_separation_id))
	
	def get_receipients(self):
		receipients = []
		if self.supervisor:
			receipients.append(self.supervisor)
		if self.afd:
			receipients.append(self.afd)
		if self.ams:
			receipients.append(self.ams)
		if self.icthr:
			receipients.append(self.icthr)
		if self.iad:
			receipients.append(self.iad)
		if self.ada:
			receipients.append(self.ada)
		if self.pc:
			receipients.append(self.pc)

		return receipients

	@frappe.whitelist()
	def set_approvers(self):
		#----------------------------Supervisor------------------------|
		if not frappe.db.get_value("Employee",self.employee, "reports_to"):
			frappe.throw("Reports To for employee {} is not set".format(self.employee))
		supervisor_officiate = get_officiating_employee(frappe.db.get_value("Employee",self.employee, "reports_to"))
		if supervisor_officiate:
			self.supervisor = frappe.db.get_value("Employee",supervisor_officiate[0].officiate,"user_id")
		else:
			self.supervisor = frappe.db.get_value("Employee",frappe.db.get_value("Employee",self.employee, "reports_to"),"user_id")

		#--------------------------- Accounts & Finance --------------------------|
		if not frappe.db.get_single_value("HR Settings", "accounts_finance"):
			frappe.throw("Accounts & Finance clearance approver is not set in HR Settings")
		afd_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "accounts_finance"))
		if afd_officiate:
			self.afd = frappe.db.get_value("Employee",afd_officiate[0].officiate,"user_id")
		else:
			self.afd = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "accounts_finance"),"user_id")

		#--------------------------- Procurement & Human Resource --------------------------|
		if not frappe.db.get_single_value("HR Settings", "procurement"):
			frappe.throw("Accounts & Finance clearance approver is not set in HR Settings")
		procurement_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "procurement"))
		if procurement_officiate:
			self.icthr = frappe.db.get_value("Employee",procurement_officiate[0].officiate,"user_id")
		else:
			self.icthr = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "procurement"),"user_id")

		#--------------------------- Asset Declaration --------------------------|
		if not frappe.db.get_single_value("HR Settings", "asset"):
			frappe.throw("Accounts & Finance clearance approver is not set in HR Settings")
		asset_declaration = get_officiating_employee(frappe.db.get_single_value("HR Settings", "asset"))
		if asset_declaration:
			self.ada = frappe.db.get_value("Employee",asset_declaration[0].officiate,"user_id")
		else:
			self.ada = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "asset"),"user_id")

		#--------------------------- General Manager --------------------------|
		if not frappe.db.get_single_value("HR Settings", "general_manager"):
			frappe.throw("Accounts & Finance clearance approver is not set in HR Settings")
		gm_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "general_manager"))
		if gm_officiate:
			self.gm = frappe.db.get_value("Employee",gm_officiate[0].officiate,"user_id")
		else:
			self.gm = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "general_manager"),"user_id")

		self.db_set("approvers_set", 1)

# Following code added by SHIV on 2020/09/21
def get_permission_query_conditions(user):
	if not user: user = frappe.session.user
	user_roles = frappe.get_roles(user)

	if user == "Administrator":
		return
	if "HR User" in user_roles or "HR Manager" in user_roles:
		return

	return """(
		`tabEmployee Separation Clearance`.owner = '{user}'
		or
		exists(select 1
				from `tabEmployee`
				where `tabEmployee`.name = `tabEmployee Separation Clearance`.employee
				and `tabEmployee`.user_id = '{user}')
		or
		(`tabEmployee Separation Clearance`.supervisor = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.afd = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.ada = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.icthr = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.iad = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.ama = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
		or
		(`tabEmployee Separation Clearance`.pc = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)

	)""".format(user=user)







# # Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# # For license information, please see license.txt

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from erpnext.custom_workflow import validate_workflow_states, notify_workflow_states
# from hrms.hr.hr_custom_function import get_officiating_employee

# class EmployeeSeparationClearance(Document):
# 	def validate(self):
# 		self.check_duplicates()
# 		# self.check_reference()
# 		self.set_approvers()
# 		self.workflow_action()

# 	def on_submit(self):
# 		self.check_signatures()
# 		self.update_reference()
# 		self.send_notification()


# 	def workflow_action(self):  
# 		action = frappe.request.form.get('action')
		
# 		if action == "Save":
# 			if self.owner !=frappe.session.user and frappe.session.user not in self.iad and \
# 				frappe.session.user not in self.afd and frappe.session.user not in self.ams and \
# 				frappe.session.user not in self.ada and frappe.session.user not in self.icthr and frappe.session.user not in self.pc and frappe.session.user not in self.supervisor:
				
# 				frappe.throw("Only the Owner and Verifier and Approver can edit.")
	
# 		if action == "Forward to Approver": 
# 			self.verifyUpdate()           
# 			if self.icthr_clearance + self.ada_clearance + self.afd_clearance + self.iad_clearance + self.ams_clearance + self.pc_clearance==6:
# 				self.workflow_state = "Waiting Supervisor Approval"
# 			else:
# 				self.workflow_state = "Waiting for Verification"
		
# 		if action =="Forward":
# 			self.verifyUpdate()
		
# 		if action == "Approve":
# 			self.verifyUpdate()
		
# 		if action == "Reapply":
# 			em= frappe.db.sql("Select user_id from `tabEmployee` where name='{}'".format(self.employee), as_dict=True)
# 			if frappe.session.user != em[0].user_id:
# 				frappe.throw("You cannot apply for another employee.")
# 			self.reApply()
	
# 	def verifyUpdate(self):
# 		user = frappe.session.user
		
# 		if user== self.iad:
# 			self.iad_clearance=1
# 		if user == self.icthr:
# 			self.icthr_clearance=1
# 		if user == self.afd:
# 			self.afd_clearance=1
# 		if user == self.ams:
# 			self.ams_clearance=1
# 		if user == self.pc:
# 			self.pc_clearance=1
# 		if user == self.ada:
# 			self.ada_clearance=1
# 		if user == self.supervisor:
# 			self.supervisor_clearance=1

# 	def reApply(self):
# 		self.iad_clearance = 0
# 		self.afd_clearance = 0
# 		self.icthr_clearance = 0
# 		self.ada_clearance = 0
# 		self.ams_clearance = 0
# 		self.pc_clearance = 0
# 		self.supervisor_clearance = 0

# 		self.iad_remarks = ""
# 		self.afd_remarks = ""
# 		self.icthr_remarks = ""
# 		self.ada_remarks = ""
# 		self.ams_remarks = ""
# 		self.pc_remarks = ""
# 		self.supervisor_remarks = ""

# 	def send_notification(self):
# 		action = frappe.request.form.get('action')  
# 		if action == "Apply" or action == "Reapply":
# 			em= frappe.db.sql("Select user_id from `tabEmployee` where name='{}'".format(self.employee), as_dict=True)
# 			if frappe.session.user != em[0].user_id:
# 				frappe.throw("You cannot apply for another employee.")
		  
# 		if self.workflow_state == "Draft" or action == "Save":
# 			return
# 		elif self.workflow_state in ("Approved", "Rejected", "Cancelled"):
# 			self.notify_employee()
				
   
# 		elif self.workflow_state == "Waiting for Verification":
# 			if self.iad + self.afd + self.icthr + self.ictcr ==0:
# 				recipients=[self.iad, self.ictcr, self.icthr, self.afd]
# 				self.notify_reviewers(recipients)
   
# 		elif self.workflow_state == "Waiting HR Approval":
# 			recipients=[self.supervisor]
# 			self.notify_reviewers(recipients)
   
# 	def notify_employee(self):
# 		self.doc = self
# 		parent_doc = frappe.get_doc(self.doc.doctype, self.doc.name)
# 		args = parent_doc.as_dict()
# 		args.update({
# 			"workflow_state": self.doc.workflow_state
# 		})
		
# 		try:
# 			email_template = frappe.get_doc("Email Template", 'Employee Separation Clearance Notification')
# 			message = frappe.render_template(email_template.response, args)
# 			recipients = self.doc.owner
# 			subject = email_template.subject
# 			self.send_mail(recipients, message, subject)
# 		except :
# 			frappe.msgprint(_("Employee Separation Clearance Notification is missing."))
		
# 	def notify_reviewers(self, recipients):
# 		parent_doc = frappe.get_doc(self.doctype, self.name)
# 		args = parent_doc.as_dict()
		
# 		try:
# 			email_template = frappe.get_doc("Email Template", 'Employee Separation Clearance Verification Notification')
# 			message = frappe.render_template(email_template.response, args)
# 			subject = email_template.subject
# 			self.send_mail(recipients,message,subject)
# 		except :
# 			frappe.msgprint(_("Employee Separation Clearance Verification Notification is missing."))
			
	   
	
# 	def send_mail(self, recipients, message, subject):
# 		frappe.sendmail(
# 				recipients=recipients,
# 				subject=_(subject),
# 				message= _(message),  
# 			)

# 	def on_cancel(self):
# 		self.update_reference()
# 		self.notify_employee()
			
# 	def check_signatures(self):
# 		if self.supervisor_clearance == 0:
# 			frappe.throw("Supervisor has not granted clearance.")
# 		if self.afd_clearance == 0:
# 			frappe.throw("Finance and Investment has not granted clearance.")
# 		if self.ams_clearance == 0:
# 			frappe.throw("Asset Management Section has not granted clearance.")
# 		if self.icthr_clearance == 0:
# 			frappe.throw("Human Resource & Administration has not granted clearance.")
# 		if self.iad_clearance == 0:
# 			frappe.throw("Internal Audit has not granted clearance.")
# 		if self.ada_clearance == 0:
# 			frappe.throw("Asset Declaration Administrator has not granted clearance.")
# 		if self.pc_clearance == 0:
# 			frappe.throw("Procurement and Contracts has not granted clearance.")
# 		# if self.sws_clearance == 0:
# 		# 	frappe.throw("SWS Treasurer has not granted clearance.")

# 	def update_reference(self):
# 		id = frappe.get_doc("Employee Separation",self.employee_separation_id)
# 		id.clearance_acquired = 1 if self.docstatus == 1 else 0
# 		id.save()

# 	def check_reference(self):
# 		if not self.employee_separation_id:
# 			frappe.throw("Employee Separation Clearance creation should route through Employee Separation Document.",title="Cannot Save")

# 	def check_duplicates(self):
# 		duplicates = frappe.db.sql("""
# 			select name from `tabEmployee Separation Clearance` where employee_separation_id = '{0}'  and name != '{1}' and docstatus != 2
# 				""".format(self.employee_separation_id,self.name))
# 		if duplicates:
# 			frappe.throw("There is already a pending Separation Clearance created for the Employee Separation '{}'".format(self.employee_separation_id))
	
# 	def get_receipients(self):
# 		receipients = []
# 		if self.supervisor:
# 			receipients.append(self.supervisor)
# 		if self.afd:
# 			receipients.append(self.afd)
# 		if self.ams:
# 			receipients.append(self.ams)
# 		if self.icthr:
# 			receipients.append(self.icthr)
# 		if self.iad:
# 			receipients.append(self.iad)
# 		if self.ada:
# 			receipients.append(self.ada)
# 		if self.pc:
# 			receipients.append(self.pc)
# 		# if self.sws:
# 		# 	receipients.append(self.sws)

# 		return receipients


# 	@frappe.whitelist()
# 	def set_approvers(self):
# 		#----------------------------Supervisor-----------------------------------------------------------------------------------------------------------------------------------------------------------|
# 		if not frappe.db.get_value("Employee",self.employee, "reports_to"):
# 			frappe.throw("Reports To for employee {} is not set".format(self.employee))
# 		supervisor_officiate = get_officiating_employee(frappe.db.get_value("Employee",self.employee, "reports_to"))
# 		if supervisor_officiate:
# 			self.supervisor = frappe.db.get_value("Employee",supervisor_officiate[0].officiate,"user_id")
# 		else:
# 			self.supervisor = frappe.db.get_value("Employee",frappe.db.get_value("Employee",self.employee, "reports_to"),"user_id")
# 		#--------------------------- Accounts & Finance Division-----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		if not frappe.db.get_single_value("HR Settings", "accounts_finance"):
# 			frappe.throw("Accounts & Finance clearance approver is not set in HR Settings")
# 		afd_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "accounts_finance"))
# 		if afd_officiate:
# 			self.afd = frappe.db.get_value("Employee",afd_officiate[0].officiate,"user_id")
# 		else:
# 			self.afd = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "accounts_finance"),"user_id")
# 		# #--------------------------- CEO -----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		# ama_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "ama"))
# 		# # if not frappe.db.get_value("Employee", {"designation": "Chief Executive Officer", "status": "Active"}, "name"):
# 		# # 	frappe.throw("Store & Procurement clearance approver is not set in HR Settings")
# 		# if ama_officiate:
# 		# 	self.ams = frappe.db.get_single_value("HR Settings", "ama")
# 		# else:
# 		# 	self.ams = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "ama"),"user_id")
		
# 		if not frappe.db.get_single_value("HR Settings", "procurement"):
# 			frappe.throw("Human Resource & Administration clearance approver is not set in HR Settings")
# 		icthr_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "procurement"))
# 		if icthr_officiate:
# 			self.icthr = frappe.db.get_value("Employee",icthr_officiate[0].officiate,"user_id")
# 		else:
# 			self.icthr = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "procurement"),"user_id")

# 		# #--------------------------- Internal Audit Division-----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		# if not frappe.db.get_single_value("HR Settings", "iad"):
# 		# 	frappe.throw("Internal Audit clearance approver is not set in HR Settings")
# 		# iad_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "iad"))
# 		# if iad_officiate:
# 		# 	self.iad = frappe.db.get_value("Employee",iad_officiate[0].officiate,"user_id")
# 		# else:
# 		# 	self.iad = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "iad"),"user_id")
		
# 		# #--------------------------- Rental and Tenancy-----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		# if not frappe.db.get_single_value("HR Settings", "ada"):
# 		# 	frappe.throw("Asset Declaration Administrator clearance approver is not set in HR Settings")
# 		# ada_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "ada"))
# 		# if ada_officiate:
# 		# 	self.ada = frappe.db.get_value("Employee",ada_officiate[0].officiate,"user_id")
# 		# else:
# 		# 	self.ada = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "ada"),"user_id")
		
# 		# #--------------------------- ICT Division-----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		# if not frappe.db.get_single_value("HR Settings", "pc"):
# 		# 	frappe.throw("Procurement and Contracts clearance approver is not set in HR Settings")
# 		# pc_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "pc"))
# 		# if pc_officiate:
# 		# 	self.pc = frappe.db.get_value("Employee",pc_officiate[0].officiate,"user_id")
# 		# else:
# 		# 	self.pc = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "pc"),"user_id")
# 		#--------------------------- SWS Treasurer-----------------------------------------------------------------------------------------------------------------------------------------------------|
# 		# sws_officiate = get_officiating_employee(frappe.db.get_single_value("HR Settings", "ict"))
# 		# if sws_officiate:
# 		# 	self.sws = frappe.db.get_value("Employee",sws_officiate[0].officiate,"user_id")
# 		# else:
# 		# 	self.sws = frappe.db.get_value("Employee",frappe.db.get_single_value("HR Settings", "sws"),"user_id")

# 		self.db_set("approvers_set",1)

# # Following code added by SHIV on 2020/09/21
# def get_permission_query_conditions(user):
# 	if not user: user = frappe.session.user
# 	user_roles = frappe.get_roles(user)

# 	if user == "Administrator":
# 		return
# 	if "HR User" in user_roles or "HR Manager" in user_roles:
# 		return

# 	return """(
# 		`tabEmployee Separation Clearance`.owner = '{user}'
# 		or
# 		exists(select 1
# 				from `tabEmployee`
# 				where `tabEmployee`.name = `tabEmployee Separation Clearance`.employee
# 				and `tabEmployee`.user_id = '{user}')
# 		or
# 		(`tabEmployee Separation Clearance`.supervisor = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.afd = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.ada = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.icthr = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.iad = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.ama = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)
# 		or
# 		(`tabEmployee Separation Clearance`.pc = '{user}' and `tabEmployee Separation Clearance`.docstatus = 0)

# 	)""".format(user=user)
