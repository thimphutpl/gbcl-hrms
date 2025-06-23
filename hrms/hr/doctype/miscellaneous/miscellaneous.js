// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Miscellaneous", {
	refresh(frm) {

	},
    company:function(frm){
        frm.set_query('accounts', function(doc) {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    }
});
