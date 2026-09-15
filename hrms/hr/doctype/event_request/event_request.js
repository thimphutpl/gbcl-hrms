// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Event Request", {
	setup(frm) {
		frm.set_query("cost_center", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
	},

	company(frm) {
		if (frm.doc.company) {
			frappe.db.get_value(
				"Company",
				frm.doc.company,
				["cost_center", "default_currency"],
				(r) => {
					if (!r) return;
					if (!frm.doc.cost_center && r.cost_center) frm.set_value("cost_center", r.cost_center);
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
		// The "Create Event Claim" action only applies to an approved (submitted)
		// request that hasn't been claimed yet — skip the round trip for a
		// new/pending document, which also sidesteps calling has_event_claim with
		// a not-yet-saved document name.
		if (frm.doc.docstatus === 1) {
			frm.call({
				method: "hrms.hr.doctype.event_request.event_request.has_event_claim",
				args: { dt: frm.doctype, dn: frm.docname },
			}).then((r) => {
				if (!r.message.has_event_claim && frappe.model.can_create("Event Claim")) {
					frm.add_custom_button(
						__("Event Claim"),
						() => make_event_claim(frm),
						__("Create")
					);
				}
			});
		}
	},
});

function make_event_claim(frm) {
	frappe.call({
		method: "hrms.hr.doctype.event_claim.event_claim.get_event_claim",
		args: { dt: frm.doc.doctype, dn: frm.doc.name },
		callback: function (r) {
			const doclist = frappe.model.sync(r.message);
			frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
		},
	});
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
