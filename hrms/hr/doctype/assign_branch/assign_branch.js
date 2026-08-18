// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Assign Branch", {
	// refresh(frm) {

	// },
	get_all_branch: function (frm) {
		//load_accounts(frm.doc.company)
		return frappe.call({
			method: "get_all_branches",
			doc: frm.doc,
			callback: function (r, rt) {
				frm.refresh_field("items");
				frm.refresh_fields();
			}
		});
	}
});

cur_frm.fields_dict['employee'].get_query = function (doc, dt, dn) {
	if (doc.employee_type && doc.employee_type === "User") {
		// If employee_type is "User", ignore filters (show all employees)
		return {
			filters: { "enabled": 1 }
		};
	} else {
		return {
			filters: { "status": "Active" }
		}
	}
}