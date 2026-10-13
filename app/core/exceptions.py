class NotFoundError(Exception):
    def __init__(self, message: str = "Recurso no encontrado"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str = "El recurso ya existe"):
        self.message = message
        super().__init__(message)


class UnauthorizedError(Exception):
    def __init__(self, message: str = "No autorizado"):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "No tiene permiso para esta operación"):
        self.message = message
        super().__init__(message)
