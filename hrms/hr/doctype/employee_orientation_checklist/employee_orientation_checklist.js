// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Orientation Checklist", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Employee Orientation'), function() {
                frappe.call({
                    method: 'get_employee_orientation',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Fetching Employee Orientation Tasks...'),
                    callback: function(r) {
                        if (!r.exc) {
                            frm.refresh_fields();
                            frappe.show_alert(__('Tasks fetched successfully'));
                        }
                    }
                });
            }).addClass('btn-primary');
            
            // Add clear button if items exist 
            if (frm.doc.items && frm.doc.items.length || 
                frm.doc.orientations && frm.doc.orientations.length || 
                frm.doc.tour_supervisor && frm.doc.tour_supervisor.length || 
                frm.doc.communications_supervisor && frm.doc.communications_supervisor.length || 
                frm.doc.technology_and_equipment && frm.doc.technology_and_equipment.length || 
                frm.doc.workspace_supervisor && frm.doc.workspace_supervisor.length || 
                frm.doc.facility_supervisor && frm.doc.facility_supervisor.length || 
                frm.doc.attendance_supervisor && frm.doc.attendance_supervisor.length || 
                frm.doc.financial_procedures && frm.doc.financial_procedures.length || 
                frm.doc.benefits_employee && frm.doc.benefits_employee.length || 
                frm.doc.new_hire_training && frm.doc.new_hire_training.length || 
                frm.doc.supervisor_information && frm.doc.supervisor_information.length || 
                frm.doc.performance && frm.doc.performance.length || 
                frm.doc.gmc_policies && frm.doc.gmc_policies.length) {
                frm.add_custom_button(__('Clear Employee'), function() {
                    frm.set_value('items', []);
                    frm.set_value('orientations', []);
					frm.set_value('tour_supervisor', []);
					frm.set_value('communications_supervisor', []);
					frm.set_value('technology_and_equipment', []);
					frm.set_value('workspace_supervisor', []);
					frm.set_value('facility_supervisor', []);
					frm.set_value('attendance_supervisor', []);
					frm.set_value('financial_procedures', []);
					frm.set_value('benefits_employee', []);
					frm.set_value('new_hire_training', []);
					frm.set_value('supervisor_information', []);
					frm.set_value('performance', []);
					frm.set_value('gmc_policies', []);
                    frm.refresh_fields();
                }).addClass('btn-default');
            }
        }
    },
	// refresh(frm) {
	// 	if (frm.doc.docstatus === 0 ) {
	// 		frm.page.clear_primary_action();
	// 		frm.add_custom_button(__("Get Employee Orientation"), function () {
	// 			frm.events.get_employee_orientation(frm);
	// 		}).toggleClass("btn-primary", !(frm.doc.employees || []).length);
	// 	}
	// }
	
	// get_employee_orientation: function (frm) {
	// 	return frappe
	// 		.call({
	// 			doc: frm.doc,
	// 			method: "get_employee_orientation",
	// 			freeze: true,
	// 			freeze_message: __("Fetching Employees"),
	// 		})
	// 		.then((r) => {
	// 			if (r.docs?.[0]?.employees) {
	// 				frm.dirty();
	// 				frm.save();
	// 			}

	// 			frm.refresh();

	// 			if (r.docs?.[0]?.validate_attendance) {
	// 				render_employee_attendance(frm, r.message);
	// 			}
	// 			frm.scroll_to_field("employees");
	// 		});
	// },
		
});