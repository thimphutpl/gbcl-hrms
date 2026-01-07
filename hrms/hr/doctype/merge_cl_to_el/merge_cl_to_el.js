frappe.ui.form.on('Merge CL To EL', {
	onload: function(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Leave Ledger Entry"];	
	},
	
	setup: function (frm) {
		frm.get_field('items').grid.editable_fields = [
			{ fieldname: 'employee', columns: 2 },
			{ fieldname: 'employee_name', columns: 2 },
			{ fieldname: 'leaves_allocated', columns: 2 },
			{ fieldname: 'leaves_taken', columns: 2 },
			{ fieldname: 'leave_balance', columns: 2 }
		];
	},
	"get_details": function (frm) {
		return frappe.call({
			method: "get_data",
			doc: frm.doc,
			callback: function (r, rt) {
				frm.refresh_field("items");
				frm.refresh_fields();
			}
		});
	}
});
