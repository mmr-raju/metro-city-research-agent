"""Public errors: messages must never include HTTP bodies, headers or credentials."""


class ResearchError(Exception):
    """An actionable error safe to display to the user."""


class ConfigurationError(ResearchError):
    pass


class CountryValidationError(ResearchError):
    pass


class CountryAmbiguityError(CountryValidationError):
    pass


class InsufficientRankingError(ResearchError):
    pass


class EvidenceError(ResearchError):
    pass


class ModelError(ResearchError):
    pass


class SearchError(ResearchError):
    pass


class SearchAuthenticationError(SearchError):
    pass


class SearchRateLimitError(SearchError):
    pass


class SearchNetworkError(SearchError):
    pass


class SearchResponseError(SearchError):
    pass
