class Bus:
    """Represents a physical bus assigned to a service."""

    def __init__(self, id, service_id, bus_model_id, runs_on):
        self.id = id
        self.service_id = service_id
        self.bus_model_id = bus_model_id
        self.runs_on = runs_on
