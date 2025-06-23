def get_data():
	return {
		"fieldname": "travel_claim",
		"non_standard_fieldnames": {
			"Payment Entry": "reference_name",
			"Journal Entry": "reference_name",
		},
		"transactions": [{"items": ["Payment Entry", "Journal Entry"]}],
	}