class AssertionException(Exception):

    def __init__(self, reason: str):
        self.reason = reason

    def __str__(self):
        return f"AssertionException[{self.reason}]"

    def __repr__(self):
        return str(self)

class MissingAttribute(AssertionException):

    def __init__(self, attributes: str, filename: str):
        super().__init__(f"Can't find '{attributes}' in {filename} file.")

class UnknownValue(AssertionException):

    def __init__(self, value: str, attributes: str):
        super().__init__(f"Unknown value '{value}' for '{attributes}'.")