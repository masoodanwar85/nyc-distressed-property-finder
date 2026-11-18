class FakeClient:
    """Stands in for SocrataClient: returns canned rows per dataset id and records the queries."""

    def __init__(self, rows_by_dataset):
        self.rows_by_dataset = rows_by_dataset
        self.calls = []

    def fetch_all(self, dataset_id, where=None, select=None):
        self.calls.append({"dataset": dataset_id, "where": where, "select": select})
        rows = self.rows_by_dataset.get(dataset_id, [])
        return iter(rows(where) if callable(rows) else rows)


def hpd_row(**over):
    row = {
        "buildingid": "132720", "boroid": "3", "boro": "BROOKLYN", "housenumber": "84",
        "streetname": "6 AVENUE", "zip": "11217", "block": "935", "lot": "7504", "bin": "3018734",
        "dobbuildingclass": "HEREAFTER CONVERTED CLASS B", "legalclassa": "1", "legalclassb": "6",
        "registrationid": "310062", "lifecycle": "Building", "recordstatus": "Active",
    }
    row.update(over)
    return row
