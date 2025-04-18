// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Travel Claim", {
    onload: function (frm) {
		let grid = frm.fields_dict['items'].grid;
        grid.cannot_add_rows = true;
	},
    
	refresh(frm) {
		refresh_html(frm);
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

frappe.ui.form.on("Travel Claim Item", {
	mileage_rate: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},

	distance: function (frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},

	dsa_percent: function(frm, cdt, cdn) {
		frm.trigger("calculate", cdt, cdn);
	},

	calculate: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
		// calculate mileage
        frappe.model.set_value(cdt, cdn, "mileage_amount", flt(row.mileage_rate) * flt(row.distance));

		// calcuate dsa
		let new_dsa = flt(row.dsa_percent)/flt(100) * flt(row.dsa)
		frappe.model.set_value(cdt, cdn, "amount", flt(new_dsa) * flt(row.no_of_days));

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