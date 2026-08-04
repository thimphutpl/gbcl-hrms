// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// on traveller rows, show the full name instead of the bare ID once selected.
// scoped to rows that carry a party_type so Employee links elsewhere are untouched.
const traveller_link_formatter = function (value, doc) {
	if (doc && doc.party_type) {
		let name = doc.traveller_name || doc.full_name || doc.employee_name;
		// fall back to a live lookup on the parent's Travellers Detail so the
		// name shows even before the row's own name field is populated
		if (!name && cur_frm && cur_frm.doc && cur_frm.doc.travellers_detail) {
			let m = cur_frm.doc.travellers_detail.find(
				(d) => d.party_type === doc.party_type && String(d.party) === String(value)
			);
			if (m) name = m.full_name;
		}
		if (name) return name;
	}
	return value;
};
frappe.form.link_formatters["Employee"] = traveller_link_formatter;
frappe.form.link_formatters["MQDC"] = traveller_link_formatter;

// new rows keep the traveller of the previous row, so one traveller's
// itinerary/miscellaneous can be entered without re-selecting each time
function inherit_traveller(frm, cdt, cdn, table) {
	let row = locals[cdt][cdn];
	if (row.party) return;

	let rows = frm.doc[table] || [];
	let prev = rows[row.idx - 2];
	if (prev && prev.party) {
		row.party_type = prev.party_type;
		row.party = prev.party;
		row.traveller_name = prev.traveller_name;
	} else if (!prev) {
		// first row: default to the only traveller, if there is just one
		let travellers = (frm.doc.travellers_detail || []).filter((d) => d.party);
		if (travellers.length === 1) {
			row.party_type = travellers[0].party_type;
			row.party = travellers[0].party;
			row.traveller_name = travellers[0].full_name;
		}
	}
	frm.refresh_field(table);
}

frappe.ui.form.on("Travel Authorization", {
	setup: function (frm) {
		frm.set_query("employee", function () {
			return {
				filters: {
					status: "Active",
				},
			};
		});

		// traveller pickers only offer people listed in Travellers Detail
		["items", "miscellaneous_item"].forEach((table) => {
			frm.set_query("party", table, function (doc, cdt, cdn) {
				let row = locals[cdt][cdn];
				let parties = (frm.doc.travellers_detail || [])
					.filter((d) => d.party_type === row.party_type && d.party)
					.map((d) => d.party);
				return {
					filters: {
						name: ["in", parties],
					},
				};
			});
		});
	},

	refresh(frm) {
		frm.events.calc_misc_total(frm);

		// once the request is Approved, the Create actions are hidden
		if (frm.doc.workflow_state === "Approved") return;

		frm.call("has_travel_claim").then((r) => {
			if (!r.message.has_travel_claim) {
				if (
					frm.doc.docstatus === 1 &&
					frappe.model.can_create("Travel Advance")
				) {
					frm.add_custom_button(
						__("Advance"),
						function () {
							frm.events.make_travel_advance(frm);
						},
						__("Create"),
					);
				}

				if (
					frm.doc.docstatus === 1 &&
					frappe.model.can_create("Travel Claim")
				) {

					frm.add_custom_button(
						__("Travel Claim"),
						function () {
							frm.events.make_travel_claim(frm);
						},
						__("Create"),
					);
				}

				if (
					frm.doc.docstatus === 1 &&
					frappe.model.can_create("Travel Adjustment")
				) {
					cur_frm.add_custom_button(
						__("Travel Adjustment"),
						function () {
							frm.events.make_travel_adjustment(frm);
						},
						__("Create")
					);
				}
			}
		});
	},

	calc_misc_total: function (frm) {
		let total = (frm.doc.miscellaneous_item || []).reduce(
			(sum, row) => sum + flt(row.amount),
			0,
		);
		frm.set_value("total_miscellaneous_amount", total);
	},

	make_travel_claim: function (frm) {
		let method = "hrms.hr.doctype.travel_claim.travel_claim.get_travel_claim";
		return frappe.call({
			method: method,
			args: {
				dt: frm.doc.doctype,
				dn: frm.doc.name,
			},
			callback: function (r) {
				var doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			},
		});
	},

	make_travel_adjustment: function (frm) {
		frappe.model.open_mapped_doc({
			method: "hrms.hr.doctype.travel_adjustment.travel_adjustment.make_travel_adjustment",
			frm: cur_frm,
		});
	},

	make_travel_advance: function (frm) {
		let method = "hrms.hr.doctype.travel_advance.travel_advance.make_travel_advance";
		return frappe.call({
			method: method,
			args: {
				dt: frm.doc.doctype,
				dn: frm.doc.name,
			},
			callback: function (r) {
				var doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			},
		});
	},

	employee: function (frm) {
		if (frm.doc.employee) frm.trigger("get_employee_currency");
	},

	get_employee_currency: function (frm) {
		frappe.db.get_value(
			"Salary Structure",
			{ employee: frm.doc.employee},
			"currency",
			(r) => {
				if (r.currency) frm.set_value("currency", r.currency);
				else frm.set_value("currency", erpnext.get_currency(frm.doc.company));
				frm.refresh_fields();
			},
		);
	},

    currency: function (frm) {
		if (frm.doc.currency) {
			var from_currency = frm.doc.currency;
			var company_currency;
			if (!frm.doc.company) {
				company_currency = erpnext.get_currency(frappe.defaults.get_default("Company"));
			} else {
				company_currency = erpnext.get_currency(frm.doc.company);
			}
			if (from_currency != company_currency) {
				frm.events.set_exchange_rate(frm, from_currency, company_currency);
			} else {
				frm.set_value("exchange_rate", 1.0);
				frm.set_df_property("exchange_rate", "hidden", 1);
				frm.set_df_property("exchange_rate", "description", "");
			}
			frm.refresh_fields();
		}
	},

	set_exchange_rate: function (frm, from_currency, company_currency) {
		frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				from_currency: from_currency,
				to_currency: company_currency,
			},
			callback: function (r) {
				frm.set_value("exchange_rate", flt(r.message));
				frm.set_df_property("exchange_rate", "hidden", 0);
				frm.set_df_property(
					"exchange_rate",
					"description",
					"1 " + frm.doc.currency + " = [?] " + company_currency,
				);
			},
		});
	},
});

// re-render the grid that holds this child row so the link cell repaints with
// the traveller's name (the formatter needs the name field populated first)
const TRAVELLER_GRID = {
	"Travellers Item": "travellers_detail",
	"Travel Authorization Item": "items",
	"Travel Miscellaneous": "miscellaneous_item",
};
function refresh_traveller_grid(frm, cdt) {
	let fn = TRAVELLER_GRID[cdt];
	if (fn && frm.fields_dict[fn]) {
		// defer so the row that was just edited finishes its own render first;
		// refreshing immediately leaves the active cell showing the bare ID
		setTimeout(() => frm.fields_dict[fn].grid.refresh(), 100);
	}
}

// repaint the itinerary + cost grids so their Traveller cells pick up a name
// that just became available in Travellers Detail
function refresh_dependent_grids(frm) {
	setTimeout(() => {
		["items", "miscellaneous_item"].forEach((fn) => {
			if (frm.fields_dict[fn]) frm.fields_dict[fn].grid.refresh();
		});
	}, 100);
}

function set_traveller_name(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let match = (frm.doc.travellers_detail || []).find(
		(d) => d.party_type === row.party_type && d.party === row.party
	);
	Promise.resolve(
		frappe.model.set_value(cdt, cdn, "traveller_name", match ? match.full_name : "")
	).then(() => refresh_traveller_grid(frm, cdt));
}

frappe.ui.form.on("Travel Miscellaneous", {
	miscellaneous_item_add: function (frm, cdt, cdn) {
		inherit_traveller(frm, cdt, cdn, "miscellaneous_item");
	},

	amount: function (frm, cdt, cdn) {
		frm.events.calc_misc_total(frm);
		refresh_traveller_grid(frm, cdt);
	},

	miscellaneous_type: function (frm, cdt, cdn) {
		refresh_traveller_grid(frm, cdt);
	},

	miscellaneous_item_remove: function (frm) {
		frm.events.calc_misc_total(frm);
	},

	party: set_traveller_name,

	party_type: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "party", "");
	},
});

frappe.ui.form.on("Travel Authorization Item", {
	items_add: function (frm, cdt, cdn) {
		inherit_traveller(frm, cdt, cdn, "items");
	},

	party: set_traveller_name,

	party_type: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "party", "");
	},

	travel_from: function (frm, cdt, cdn) {
		refresh_traveller_grid(frm, cdt);
	},

	travel_to: function (frm, cdt, cdn) {
		refresh_traveller_grid(frm, cdt);
	},

	from_date: function(frm, cdt, cdn) {
		let child = locals[cdt][cdn];
		if (!child.halt && child.from_date != child.to_date) {
			if (child.from_date) {
				frappe.model.set_value(cdt, cdn, "to_date", child.from_date);
			}
		}
		refresh_traveller_grid(frm, cdt);
	},

	to_date: function(frm, cdt, cdn) {
		let child = locals[cdt][cdn];
		if (child.from_date) {
			if (child.to_date < child.from_date) {
				msgprint("To Date cannot be earlier than From Date")
				frappe.model.set_value(cdt, cdn, "to_date", child.from_date);
			}
		}
		refresh_traveller_grid(frm, cdt);
	},
});

frappe.ui.form.on('Travellers Item', {
    party: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.party_type === "Employee" && row.party) {

            frappe.db.get_value("Employee", row.party, [
                "employee_name",
                "designation"
            ]).then(r => {

                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "full_name", r.message.employee_name);
                    frappe.model.set_value(cdt, cdn, "designation", r.message.designation);
                    refresh_traveller_grid(frm, cdt);
                    refresh_dependent_grids(frm);
                }
            });
        }
		if (row.party_type === "MQDC" && row.party) {

			frappe.db.get_value("MQDC", row.party, ["full_name", "designation"])
				.then(r => {
					if (r && r.message) {
						frappe.model.set_value(cdt, cdn, "full_name", r.message.full_name);
						frappe.model.set_value(cdt, cdn, "designation", r.message.designation);
						refresh_traveller_grid(frm, cdt);
						refresh_dependent_grids(frm);
					}
				});
		}
    }
});