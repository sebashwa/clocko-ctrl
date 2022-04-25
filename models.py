class ClockodoTask:
    def __init__(self, name, project_id=None, customer_id=None):
        self.project_id = project_id
        self.customer_id = customer_id
        self.name = name

    @staticmethod
    def from_dict(d):
        name = d.get("name")
        customer_id = d.get("customer_id")
        project_id = d.get("project_id")

        no_name = name is None
        no_id = customer_id is None and project_id is None
        if no_name or no_id:
            return None

        return ClockodoTask(name=name, customer_id=customer_id, project_id=project_id)
