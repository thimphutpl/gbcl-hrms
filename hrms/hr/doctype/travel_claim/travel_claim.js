// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Travel Claim", {
    onload: function (frm) {
		let grid = frm.fields_dict['items'].grid;
        grid.cannot_add_rows = true;
	},
    
	refresh(frm) {
		refresh_html(frm);
		frm.events.calc_misc_total(frm);
		frm.events.relabel_misc_amount(frm);
	},

	// the "Amount" column's own currency formatting already follows frm.doc.currency
	// (options: "currency" on the field), but the grid's column HEADER text is
	// static -- relabel it so the header itself shows which currency is selected
	relabel_misc_amount: function (frm) {
		let grid = frm.fields_dict["miscellaneous_item"] && frm.fields_dict["miscellaneous_item"].grid;
		if (!grid) return;
		let label = frm.doc.currency ? __("Amount ({0})", [frm.doc.currency]) : __("Amount");
		grid.update_docfield_property("amount", "label", label);
		if (!grid.open_grid_row &&
			!(grid.wrapper && grid.wrapper[0] && $.contains(grid.wrapper[0], document.activeElement))) {
			grid.refresh();
		}
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
		frm.set_value("miscellaneous_amount", total);
		frm.set_value("miscellaneous_amount_btn", total_btn);
		let field = frm.fields_dict["miscellaneous_item"];
		if (field && field.grid && !field.grid.open_grid_row &&
			!(field.grid.wrapper && field.grid.wrapper[0] && $.contains(field.grid.wrapper[0], document.activeElement))) {
			field.grid.refresh();
		}
	},

	exchange_rate: function (frm) {
		frm.events.calc_misc_total(frm);
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

frappe.ui.form.on("Travel Miscellaneous", {
	amount: function (frm) {
		frm.events.calc_misc_total(frm);
	},

	miscellaneous_item_remove: function (frm) {
		frm.events.calc_misc_total(frm);
	},
});

frappe.ui.form.on("Travel Claim Item", {
	mileage_rate: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},

	distance: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},

	calculate: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        frappe.model.set_value(cdt, cdn, "mileage_amount", flt(row.mileage_rate) * flt(row.distance));
        frappe.model.set_value(cdt, cdn, "amount", flt(row.mileage_amount) + flt(row.amount));
    },
});

var refresh_html = function(frm){
	var journal_entry_status = "";
	if(frm.doc.journal_entry_status){
		journal_entry_status = '<div style="font-style: italic; font-size: 0.8em; ">* '+frm.doc.journal_entry_status+'</div>';
	}
	
	if(frm.doc.journal_entry){
		$(cur_frm.fields_dict.journal_entry_html.wrapper).html('<label class="control-label" style="padding-right: 0px;">Journal Entry</label><br><b>'+'<a href="/desk/Form/Journal Entry/'+frm.doc.journal_entry+'">'+frm.doc.journal_entry+"</a> "+"</b>"+journal_entry_status);
	}	
}