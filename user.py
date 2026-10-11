class User:
    """Represents a system user."""

    def __init__(self, id, admin, username, password):
        self.id = id
        self.admin = admin
        self.username = username
        self.password = password
