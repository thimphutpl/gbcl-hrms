// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shift Assignment Schedule", {
    setup:function(frm) {
        frm.set_query("branch", function() {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
        
    },
	get_all_employee(frm) {

        if (!frm.doc.attendance_location) {
            frappe.msgprint(__("Please select an attendance location first."));
            return;
        }

        frm.clear_table("shift_assignment_schedule_employee");
        frm.refresh_field("shift_assignment_schedule_employee");

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Employee",
                filters: {
                    attendance_location: frm.doc.attendance_location,
                    status: "Active"
                },
                fields: ["name", "employee_name", "company"],
                limit_page_length: 1000
            },
            callback(r) {
                if (r.message && r.message.length > 0) {
                    r.message.forEach(emp => {
                        let row = frm.add_child("shift_assignment_schedule_employee");
                        row.employee = emp.name;
                        row.employee_name = emp.employee_name;
                    });

                    frm.refresh_field("shift_assignment_schedule_employee");
                } else {
                    frappe.msgprint(__("No active employees found for this attendance location."));
                }
            }
        });
    }
});
