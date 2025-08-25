// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Employee TDS Certificate"] = {
	"filters": [
		{
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": frappe.defaults.get_user_default("fiscal_year"),
		},
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"reqd": 1,
			"on_change": function (query_report) {
				var emp = query_report.get_values().employee;
				if (!emp) {
					return;
				}
				frappe.model.with_doc("Employee", emp, function (r) {
					var fy = frappe.model.get_doc("Employee", emp);
					frappe.query_report.set_filter_value("e_name", fy.employee_name);
					frappe.query_report.set_filter_value("cid", fy.passport_number);
					frappe.query_report.set_filter_value("tpn", fy.tpn_number);
					frappe.query_report.refresh();
				});
				frappe.call({
					method: "frappe.client.get_single_value",
					args: {
						doctype: "HR Settings",
						field: "seal",
					},
					callback: function (r) {
						console.log(r.message);
						frappe.query_report.set_filter_value("seal", r.message);
						frappe.query_report.refresh();
					}
				});
			}
		},
		{
			"fieldname": "e_name",
			"fieldtype": "Data",
			"label": __("Employee Name"),
			"read_only": 1
		},
		{
			"fieldname": "cid",
			"fieldtype": "Data",
			"label": __("CID"),
			"read_only": 1
		},
		{
			"fieldname": "tpn",
			"fieldtype": "Data",
			"label": __("TPN"),
			"read_only": 1
		},
		{
			"fieldname": "seal",
			"label": "Seal and Signature",
			"fieldtype": "Data",
			"read_only": 1,
			"hidden": 1
		}
	],
	onload: function (report) {
		report.page.add_inner_button("Clear Filters", function () {
			report.set_filter_value("fiscal_year", null);
			report.set_filter_value("employee", null);
			report.set_filter_value("e_name", null);
			report.set_filter_value("cid", null);
			report.set_filter_value("tpn", null);
			report.set_filter_value("seal", null);
		});
	},

}

