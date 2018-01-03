class Person:

    def __init__(self, user_id, server):
        self.user_id = user_id
        self.server = server

    def getUserServer(self):
        return self.server
