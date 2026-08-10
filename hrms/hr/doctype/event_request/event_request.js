// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Event Request", {
	setup(frm) {
		frm.set_query("expense_account", () => ({
			filters: {
				company: frm.doc.company,
				root_type: "Expense",
				is_group: 0,
			},
		}));

		frm.set_query("payable_account", () => ({
			filters: {
				company: frm.doc.company,
				root_type: ["in", ["Liability", "Asset"]],
				is_group: 0,
			},
		}));

		frm.set_query("cost_center", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));

		frm.set_query("event_approver", () => ({
			query: "frappe.core.doctype.user.user.user_query",
		}));
	},

	company(frm) {
		if (frm.doc.company) {
			frappe.db.get_value(
				"Company",
				frm.doc.company,
				[
					"default_expense_account",
					"default_expense_claim_payable_account",
					"cost_center",
					"default_currency",
				],
				(r) => {
					if (!r) return;
					if (!frm.doc.expense_account && r.default_expense_account)
						frm.set_value("expense_account", r.default_expense_account);
					if (!frm.doc.payable_account && r.default_expense_claim_payable_account)
						frm.set_value("payable_account", r.default_expense_claim_payable_account);
					if (!frm.doc.cost_center && r.cost_center)
						frm.set_value("cost_center", r.cost_center);
					if (!frm.doc.currency && r.default_currency)
						frm.set_value("currency", r.default_currency);
				}
			);
		}
	},

	estimated_event_cost(frm) {
		calculate_total(frm);
	},

	add_cost_breakdown(frm) {
		if (!frm.doc.add_cost_breakdown) {
			frm.clear_table("cost_breakdown");
			frm.refresh_field("cost_breakdown");
		}
		calculate_total(frm);
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
			frm.add_custom_button(
				__("Journal Entry"),
				() => frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry),
				__("View")
			);
		}

		// Approval actions — only on a SUBMITTED, still-pending request, for approver roles
		if (frm.doc.docstatus === 1 && frm.doc.approval_status === "Draft" && can_approve()) {
			frm.add_custom_button(__("Approve"), () => approve_event_request(frm)).addClass(
				"btn-primary"
			);
			frm.add_custom_button(__("Reject"), () => reject_event_request(frm)).addClass("btn-danger");
		}
	},
});

function can_approve() {
	const roles = frappe.user_roles || [];
	return ["System Manager", "HR Manager", "HR User", "Expense Approver"].some((r) =>
		roles.includes(r)
	);
}

function approve_event_request(frm) {
	frappe.confirm(
		__("Approve this Event Request? A Journal Entry will be posted for the estimated cost."),
		() => {
			frm.call("approve").then(() => frm.reload_doc());
		}
	);
}

function reject_event_request(frm) {
	frappe.prompt(
		[{ label: __("Reason for Rejection"), fieldname: "reason", fieldtype: "Small Text", reqd: 1 }],
		(values) => {
			frm.call("reject", { reason: values.reason }).then(() => frm.reload_doc());
		},
		__("Reject Event Request"),
		__("Reject")
	);
}

frappe.ui.form.on("Event Request Cost Breakdown", {
	amount: (frm) => calculate_total(frm),
	cost_breakdown_remove: (frm) => calculate_total(frm),
});

function calculate_total(frm) {
	let breakdown_total = 0;
	(frm.doc.cost_breakdown || []).forEach((row) => {
		breakdown_total += flt(row.amount);
	});

	if (frm.doc.add_cost_breakdown && breakdown_total) {
		frm.set_value("estimated_event_cost", breakdown_total);
		frm.set_value("total_estimated_cost", breakdown_total);
	} else {
		frm.set_value("total_estimated_cost", flt(frm.doc.estimated_event_cost));
	}
}
