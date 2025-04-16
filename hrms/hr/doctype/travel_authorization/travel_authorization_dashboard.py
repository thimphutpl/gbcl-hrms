def get_data():
	return {
		"fieldname": "travel_authorization",
		"non_standard_fieldnames": {
			"Payment Entry": "reference_name",
			"Journal Entry": "reference_name",
		},
		"transactions": [{"items": ["Travel Claim", "Travel Advance", "Travel Adjustment"]}, {"items": ["Journal Entry"]}],
	}
