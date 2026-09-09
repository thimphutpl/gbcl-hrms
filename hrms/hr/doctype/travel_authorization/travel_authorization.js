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

// relabel "Add Row" -> "Add" and make it black (low-contrast complaint on some
// devices), scoped only to this form's grids via a marker class on frm.wrapper.
// Pure CSS so it survives every grid re-render without re-running JS.
function apply_add_button_styling(frm) {
	const STYLE_ID = "hrms-travel-add-btn-style";
	if (!document.getElementById(STYLE_ID)) {
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			.hrms-travel-add-btn .grid-add-row {
				color: transparent !important;
				background-color: #000 !important;
				border-color: #000 !important;
				position: relative;
			}
			.hrms-travel-add-btn .grid-add-row::after {
				content: "${__("Add")}";
				position: absolute;
				inset: 0;
				display: flex;
				align-items: center;
				justify-content: center;
				color: #fff;
			}
			/* row editor footer: "Insert Below" (grid-append-row) is the actual
			   add-a-row action here, already at the bottom — just relabel it.
			   The "..." chevron near the top is Collapse, left untouched. */
			.hrms-travel-add-btn .grid-footer-toolbar .grid-append-row {
				color: transparent !important;
				background-color: #000 !important;
				border-color: #000 !important;
				position: relative;
			}
			.hrms-travel-add-btn .grid-footer-toolbar .grid-append-row::after {
				content: "${__("Add")}";
				position: absolute;
				inset: 0;
				display: flex;
				align-items: center;
				justify-content: center;
				color: #fff;
			}
		`;
		document.head.appendChild(style);
	}
	$(frm.wrapper).addClass("hrms-travel-add-btn");
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
		frm.events.relabel_misc_amount(frm);
		apply_add_button_styling(frm);
		frm.events.lock_applicant_to_self(frm);

		// the buttons below only ever apply to an already-approved (docstatus 1)
		// request, so skip the round trip entirely for a new/pending document --
		// this also sidesteps calling has_travel_claim with a not-yet-saved
		// document name, which would 404 against the DB
		if (frm.doc.docstatus === 1) {
			frm.call({
				method: "hrms.hr.doctype.travel_authorization.travel_authorization.has_travel_claim",
				args: { dt: frm.doctype, dn: frm.docname },
			}).then((r) => {
				if (!r.message.has_travel_claim) {
					if (frappe.model.can_create("Travel Claim")) {
						frm.add_custom_button(
							__("Travel Claim"),
							function () {
								frm.events.make_travel_claim(frm);
							},
							__("Create"),
						);
					}

					if (frappe.model.can_create("Travel Adjustment")) {
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
		}
	},

	// the "Amount" column's own currency formatting already follows frm.doc.currency
	// (options: "currency" on the field), but the grid's column HEADER text is
	// static -- relabel it so the header itself shows which currency is selected
	relabel_misc_amount: function (frm) {
		let grid = frm.fields_dict["miscellaneous_item"] && frm.fields_dict["miscellaneous_item"].grid;
		if (!grid) return;
		let label = frm.doc.currency ? __("Amount ({0})", [frm.doc.currency]) : __("Amount");
		grid.update_docfield_property("amount", "label", label);
		repaint_grid(frm, "miscellaneous_item");
	},

	calc_misc_total: function (frm) {
		let rate = flt(frm.doc.exchange_rate) || 1;
		let total = 0;
		let total_btn = 0;
		(frm.doc.miscellaneous_item || []).forEach((row) => {
			row.amount_in_btn = flt(row.amount) * rate;
			total += flt(row.amount);
			total_btn += flt(row.amount_in_btn);
		});
		frm.set_value("total_miscellaneous_amount", total);
		frm.set_value("total_miscellaneous_amount_btn", total_btn);
		// repaint_grid is the same guarded helper used elsewhere in this file --
		// a plain frm.refresh_field()/grid.refresh() here would rebuild the row
		// controls and discard whatever the user is still typing mid-edit
		repaint_grid(frm, "miscellaneous_item");
	},

	// Applicant/Employee is always the logged-in user, no exceptions — auto-fill
	// it and lock it, so it no longer depends on each Employee record having
	// "Create User Permission" correctly configured. Nobody, including HR/System
	// Manager, can file a request on someone else's behalf through this form.
	// This is a UX convenience only — the real enforcement is server-side in
	// validate(). "Administrator" is exempt since that's the raw system account
	// used for scripts/imports, not a person filing a request.
	lock_applicant_to_self: function (frm) {
		if (frappe.session.user === "Administrator") return;

		if (frm.is_new() && !frm.doc.employee) {
			frappe.db.get_value(
				"Employee",
				{ user_id: frappe.session.user },
				"name",
			).then((r) => {
				if (r.message && r.message.name) {
					frm.set_value("employee", r.message.name).then(() => {
						// lock only after the value (and its fetched name/title)
						// has fully resolved and rendered — locking too early
						// leaves the read-only display blank
						frm.set_df_property("employee", "read_only", 1);
						frm.refresh_field("employee");
					});
				}
			});
		} else if (frm.doc.employee) {
			frm.set_df_property("employee", "read_only", 1);
			frm.refresh_field("employee");
		}
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
		frm.events.relabel_misc_amount(frm);
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

	exchange_rate: function (frm) {
		frm.events.calc_misc_total(frm);
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
// A grid.refresh() rebuilds every row control, which throws away whatever the
// user is currently typing in an open cell or row editor. Only repaint once the
// user has moved out of that grid, so a repaint can never eat a pending edit.
function repaint_grid(frm, fieldname) {
	let field = frm.fields_dict[fieldname];
	if (!field || !field.grid) return;
	let grid = field.grid;
	if (grid.open_grid_row) return;
	if (grid.wrapper && grid.wrapper[0] && $.contains(grid.wrapper[0], document.activeElement)) return;
	grid.refresh();
}

function refresh_traveller_grid(frm, cdt) {
	let fn = TRAVELLER_GRID[cdt];
	if (fn && frm.fields_dict[fn]) {
		// defer so the row that was just edited finishes its own render first;
		// refreshing immediately leaves the active cell showing the bare ID
		setTimeout(() => repaint_grid(frm, fn), 100);
	}
}

// repaint the itinerary + cost grids so their Traveller cells pick up a name
// that just became available in Travellers Detail
function refresh_dependent_grids(frm) {
	setTimeout(() => {
		["items", "miscellaneous_item"].forEach((fn) => repaint_grid(frm, fn));
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

	from_date: function(frm, cdt, cdn) {
		let child = locals[cdt][cdn];
		if (!child.halt && child.from_date != child.to_date) {
			if (child.from_date) {
				frappe.model.set_value(cdt, cdn, "to_date", child.from_date);
			}
		}
	},

	to_date: function(frm, cdt, cdn) {
		let child = locals[cdt][cdn];
		if (child.from_date) {
			if (child.to_date < child.from_date) {
				msgprint("To Date cannot be earlier than From Date")
				frappe.model.set_value(cdt, cdn, "to_date", child.from_date);
			}
		}
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