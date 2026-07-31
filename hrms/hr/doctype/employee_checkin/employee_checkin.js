// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Checkin", {
    refresh: async (frm) => {
        if (!frm.doc.__islocal) frm.trigger("add_fetch_shift_button");

        const allow_geolocation_tracking = await frappe.db.get_single_value(
            "HR Settings",
            "allow_geolocation_tracking",
        );

        if (!allow_geolocation_tracking) {
            hide_field(["fetch_geolocation", "latitude", "longitude", "geolocation"]);
            return;
        }
    },

    fetch_geolocation: (frm) => {
        hrms.fetch_geolocation(frm);
    },
    employee: async function (frm) {

        if (!frm.doc.employee) return;

        await frappe.call({
            method: "fetch_shift",
            doc: frm.doc
        });

        frm.refresh_field("shift");
    },

    before_save: function (frm) {

        // ❌ block save initially
        frappe.validated = false;

        // Step 1: get user IP
        fetch("https://api.ipify.org?format=json")
            .then(res => res.json())
            .then(ipData => {

                let user_ip = ipData.ip;
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Shift Type",
                        filters: {
                            name: frm.doc.shift
                        },
                        fieldname: ["ip"]
                    },
                    callback: function (r) {

                        let allowed_ip = r.message?.ip;
                        if (allowed_ip && user_ip !== allowed_ip) {
                            frappe.msgprint({
                                title: "Not Allowed",
                                message: `Check-in is allowed only from office network. Your current IP (${user_ip}) is not permitted.`,
                                indicator: "red"
                            });

                            frappe.validated = false;

                        } else {

                            // ✅ allow save
                            frappe.validated = true;


                        }
                    }
                });

            })
            .catch(err => {
                console.error(err);

                frappe.validated = false;
            });
    },

    add_fetch_shift_button(frm) {
        if (frm.doc.attendace) return;
        frm.add_custom_button(__("Fetch Shift"), function () {
            const previous_shift = frm.doc.shift;
            frappe.call({
                method: "fetch_shift",
                doc: frm.doc,
                freeze: true,
                freeze_message: __("Fetching Shift"),
                callback: function () {
                    if (previous_shift === frm.doc.shift) return;
                    frm.dirty();
                    frm.save();
                    frappe.show_alert({
                        message: __("Shift has been successfully updated to {0}.", [
                            frm.doc.shift,
                        ]),
                        indicator: "green",
                    });
                },
            });
        });
    },
});
