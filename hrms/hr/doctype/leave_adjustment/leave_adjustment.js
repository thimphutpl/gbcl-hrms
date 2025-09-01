// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Leave Adjustment', {
	refresh: function(frm) {

	},
	get_employees: function(frm) {
		return frappe.call({
			method: "get_employees",
			doc: frm.doc,
			callback: function(r, rt) {
				frm.refresh_field("items");
				frm.refresh_fields();
			}
		});
	}
});

frappe.ui.form.on('Leave Adjustment Item', {
	actual_balance: function(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		frappe.call({
			method: "get_leave_type_info",
			args: {"actual_balance":row.actual_balance},
			doc: frm.doc,
			callback: function(r){
					frappe.model.set_value(cdt,cdn,"difference",flt(row.leave_balance)-flt(row.actual_balance))
			}
		})
	},
	employee: function(frm, cdt, cdn){
		var row = locals[cdt][cdn];
		frappe.call({
			method: "get_employee_details",
			args: {"employee":row.employee},
			doc: frm.doc,
			callback: function(r){
				if(r.message){
					frappe.model.set_value(cdt, cdn, "leave_balance", r.message[0]);
					frappe.model.set_value(cdt, cdn, "actual_balance", r.message[0]);
					frappe.model.set_value(cdt, cdn, "difference", r.message[1]);
				}
			}
		})
		frm.refresh_fields();
	}
});
