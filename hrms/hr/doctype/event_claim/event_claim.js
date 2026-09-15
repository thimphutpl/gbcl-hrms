// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Event Claim", {
	setup(frm) {
		frm.set_query("event_request", () => ({
			filters: { docstatus: 1, employee: frm.doc.employee },
		}));

		frm.set_query("cost_center", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));

		frm.set_query("expense_account", () => ({
			filters: { company: frm.doc.company, root_type: "Expense", is_group: 0 },
		}));

		frm.set_query("payable_account", () => ({
			filters: { company: frm.doc.company, root_type: ["in", ["Liability", "Asset"]], is_group: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
			frm.add_custom_button(
				__("Journal Entry"),
				() => frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry),
				__("View")
			);
		}
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.db.get_value(
			"Company",
			frm.doc.company,
			["default_expense_account", "default_expense_claim_payable_account", "cost_center", "default_currency"],
			(r) => {
				if (!r) return;
				if (!frm.doc.expense_account && r.default_expense_account)
					frm.set_value("expense_account", r.default_expense_account);
				if (!frm.doc.payable_account && r.default_expense_claim_payable_account)
					frm.set_value("payable_account", r.default_expense_claim_payable_account);
				if (!frm.doc.cost_center && r.cost_center) frm.set_value("cost_center", r.cost_center);
				if (!frm.doc.currency && r.default_currency) frm.set_value("currency", r.default_currency);
			}
		);
	},
});

frappe.ui.form.on("Event Request Cost Breakdown", {
	amount: (frm) => calculate_total(frm),
	cost_breakdown_remove: (frm) => calculate_total(frm),
});

function calculate_total(frm) {
	let total = 0;
	(frm.doc.cost_breakdown || []).forEach((row) => {
		total += flt(row.amount);
	});
	frm.set_value("total_amount", total);
}
