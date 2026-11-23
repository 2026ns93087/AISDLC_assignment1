"""Application error with a stable code and an exit code (FR-013)."""


class AppError(Exception):
    """A failure that the command line reports as one JSON object on stderr."""

    def __init__(self, code: str, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
