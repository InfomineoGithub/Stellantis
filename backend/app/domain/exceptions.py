class VehicleAlreadyExistsError(Exception):
    """Raised when (manufacturer, model_name, year) already exists."""


class VehicleNotFoundError(Exception):
    """Raised when a vehicle with the given ID does not exist."""


class SourceAlreadyExistsError(Exception):
    """Raised when a source with the same URL already exists."""


class SourceNotFoundError(Exception):
    """Raised when a source with the given ID does not exist."""


class VehicleSourceLinkError(Exception):
    """Raised when a vehicle-source link operation fails."""
