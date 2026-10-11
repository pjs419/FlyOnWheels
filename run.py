class Run:
    """Represents one dated instance of a service."""

    def __init__(self, id, service_id, date, bus_id):
        self.id = id
        self.service_id = service_id
        self.date = date
        self.bus_id = bus_id
