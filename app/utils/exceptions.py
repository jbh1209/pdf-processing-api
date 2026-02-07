class PDFProcessingError(Exception):
    """Raised when PDF processing fails."""
    pass

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

class ToolNotAvailableError(Exception):
    """Raised when a required tool is not available."""
    pass

