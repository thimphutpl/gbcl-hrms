import frappe


def execute():
	"""Rename the traveller party doctype `Others` to `MQDC` and convert the
	stored `party_type` values in the traveller tables. Runs pre-model-sync so
	it happens before the schema sync would otherwise create an empty `MQDC`."""
	if frappe.db.exists("DocType", "Others") and not frappe.db.exists("DocType", "MQDC"):
		frappe.rename_doc("DocType", "Others", "MQDC", force=True)

	for doctype in ("Travellers Item", "Travel Authorization Item", "Travel Miscellaneous"):
		if frappe.db.has_column(doctype, "party_type"):
			frappe.db.sql(
				"update `tab{0}` set party_type = 'MQDC' where party_type = 'Others'".format(doctype)
			)
