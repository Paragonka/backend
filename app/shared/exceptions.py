# N818 - base application exception; renaming it would affect the entire codebase
class AppException(Exception):  # noqa: N818
    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


class AppHttpException(AppException):
    status_code: int = 500

    def __init__(
        self, message: str, status_code: int | None = None, code: str | None = None
    ):
        if status_code is not None:
            self.status_code = status_code

        super().__init__(message, code=code)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(status_code={self.status_code}, "
            f"message={self.message!r})"
        )


class NotFoundException(AppHttpException):
    status_code = 404


class ForbiddenException(AppHttpException):
    status_code = 403


class ConflictException(AppHttpException):
    status_code = 409


class GoneException(AppHttpException):
    status_code = 410


class ValidationException(AppHttpException):
    status_code = 422


class NotAuthenticatedException(AppHttpException):
    status_code = 401

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, code="NOT_AUTHENTICATED")


class EmailAlreadyRegistered(ConflictException):
    def __init__(self, email: str):
        super().__init__(f"Email already registered: {email}", code="EMAIL_EXISTS")


class OrgAccessDenied(ForbiddenException):
    def __init__(self, org_id: str):
        super().__init__("Access denied", code="ORG_ACCESS_DENIED")


class EavValidationError(ValidationException):
    def __init__(self, field_code: str, message: str):
        super().__init__(
            f"EAV field '{field_code}': {message}", code="EAV_VALIDATION_ERROR"
        )


class MediaValidationError(ValidationException):
    def __init__(self, message: str):
        super().__init__(f"Media: {message}", code="MEDIA_VALIDATION_ERROR")


class StockError(ValidationException):
    def __init__(self, product_id: str, requested: float, available: float):
        super().__init__(
            f"Insufficient stock for {product_id}: requested {requested}, "
            f"available {available}",
            code="INSUFFICIENT_STOCK",
        )
