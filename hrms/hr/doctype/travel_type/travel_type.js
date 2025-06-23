// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Travel Type", {
// 	refresh(frm) {

// 	},
// });

// frappe.ui.form.on("Travel Type Item", {
//     onload: function (frm) {
// 		frm.set_query("account", function() {
//             return {
//                 filters: {
//                     "company": frm.doc.company,
//                 }
//             };
//         });
// 	},
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Travel Type", {
    onload(frm) {
        // Assuming frm.doc.accounts is an array of account objects
        if (frm.doc.accounts) {
            frm.doc.accounts.forEach(function(account) {
                frm.set_query("account", "accounts", function() {
                    return {
                        filters: {
                            "company": account.company
                        }
                    };
                });
            });
        }
    },
    
    refresh(frm) {
        // Your refresh logic for Travel Type form
    }
});

frappe.ui.form.on("Travel Type Item", {
    refresh(frm) {
        // Your refresh logic for Travel Type Item form
    }
});
