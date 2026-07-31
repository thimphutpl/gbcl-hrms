# # Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# # For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import add_days, get_weekday, nowdate

# from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import create_shift_assignment


# class ShiftAssignmentSchedule(Document):
# 	def create_shifts(self, start_date: str, end_date: str | None = None) -> None:
# 		gap = {
# 			"Every Week": 0,
# 			"Every 2 Weeks": 1,
# 			"Every 3 Weeks": 2,
# 			"Every 4 Weeks": 3,
# 		}[self.frequency]

# 		date = start_date
# 		individual_assignment_start = None
# 		week_end_day = get_weekday(add_days(start_date, -1))
# 		repeat_on_days = [day.day for day in self.repeat_on_days]

# 		if not end_date:
# 			end_date = add_days(start_date, 90)

# 		while date <= end_date:
# 			weekday = get_weekday(date)
# 			if weekday in repeat_on_days:
# 				if not individual_assignment_start:
# 					individual_assignment_start = date
# 				if date == end_date:
# 					self.create_individual_assignment(individual_assignment_start, date)

# 			elif individual_assignment_start:
# 				self.create_individual_assignment(individual_assignment_start, add_days(date, -1))
# 				individual_assignment_start = None

# 			if weekday == week_end_day and gap:
# 				if individual_assignment_start:
# 					self.create_individual_assignment(individual_assignment_start, date)
# 					individual_assignment_start = None
# 				date = add_days(date, 7 * gap)

# 			date = add_days(date, 1)

# 	def create_individual_assignment(self, start_date, end_date):
# 		create_shift_assignment(
# 			self.employee, self.company, self.shift_type, start_date, end_date, self.shift_status, self.name
# 		)
# 		self.create_shifts_after = end_date
# 		self.save()


# def process_auto_shift_creation():
# 	schedules = frappe.get_all(
# 		"Shift Assignment Schedule",
# 		filters={"enabled": 1, "create_shifts_after": ["<=", nowdate()]},
# 		pluck="name",
# 	)
# 	for d in schedules:
# 		doc = frappe.get_doc("Shift Assignment Schedule", d)
# 		doc.create_shifts(add_days(doc.create_shifts_after, 1))
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, get_weekday, getdate, nowdate
from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import create_shift_assignment
from hrms.hr.doctype.shift_assignment.shift_assignment import OverlappingShiftError

BATCH_SIZE = 50  # Number of employees per batch

class ShiftAssignmentSchedule(Document):

	def create_shifts(self, start_date: str, end_date: str | None = None):
		if not start_date:
			frappe.throw("Please set 'Create Shifts After'")
		if not end_date:
			frappe.throw("Please set 'End Date'")

		start_date = getdate(start_date)
		end_date = getdate(end_date)

		repeat_on_days = [d.day.lower() for d in self.repeat_on_days or []]
		if not repeat_on_days:
			frappe.throw("Please select 'Repeat On Days'")

		employees = self.shift_assignment_schedule_employee or []
		if not employees:
			frappe.throw("No employees found in this schedule")

	   
		# Process day by day
		date = start_date
		while date <= end_date:
			weekday_name = get_weekday(date).lower()
			if weekday_name in repeat_on_days:
				# Process in batches
				total = len(employees)
				for i in range(0, total, BATCH_SIZE):
					batch = employees[i:i+BATCH_SIZE]
					self.create_shift_batch(batch, date, date)
			date = add_days(date, 1)

	def create_shift_batch(self, batch, start_date, end_date):
		skipped_employees = []

		for row in batch:
			employee = row.employee

			# Skip if shift already exists
			exists = frappe.db.exists(
				"Shift Assignment",
				{
					"employee": employee,
					"start_date": start_date,
					"shift_type": self.shift_type,
					"docstatus": ["!=", 2],
				}
			)
			if exists:
				skipped_employees.append(employee)
				continue

			try:
				create_shift_assignment(
					employee=employee,
					company=self.company,
					shift_type=self.shift_type,
					start_date=start_date,
					end_date=end_date,
					status=self.shift_status,
					schedule=self.name
				)
			except OverlappingShiftError:
				skipped_employees.append(employee)
				continue

		# if skipped_employees:
		#     frappe.log_error(
		#         f"Skipped employees on {start_date}: {', '.join(skipped_employees)}",
		#         "Shift Creation Skipped"
		#     )
		if skipped_employees:
			# Short title
			title = f"Shift Creation Skipped on {start_date}"

			# Show only first 10 employees
			display_employees = skipped_employees[:10]

			# Prepare message
			message = f"Skipped employees on {start_date}: {', '.join(display_employees)}"

			# If more than 10, indicate remaining
			if len(skipped_employees) > 10:
				message += f", and {len(skipped_employees) - 10} more..."

			# Log the error
			frappe.log_error(message=message, title=title)


# Daily cron job
def process_auto_shift_creation():
	schedules = frappe.get_all(
		"Shift Assignment Schedule",
		filters={"enabled": 1},
		pluck="name",
	)

	for name in schedules:
		doc = frappe.get_doc("Shift Assignment Schedule", name)
		doc.create_shifts(doc.create_shifts_after, doc.end_date)
