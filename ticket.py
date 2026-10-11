class Ticket:
    """Represents a user's ticket for a specific run."""

    def __init__(self, id, user_id, run_id, number):
        self.id = id
        self.user_id = user_id
        self.run_id = run_id
        self.number = number
