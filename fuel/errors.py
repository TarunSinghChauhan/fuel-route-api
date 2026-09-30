class APIError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message, *, status=None, code=None):
        super().__init__(message)
        self.message = message
        if status:
            self.status = status
        if code:
            self.code = code


class InvalidLocation(APIError):
    status = 400
    code = "invalid_location"


class RoutingError(APIError):
    status = 502
    code = "routing_failed"


class NoRoute(APIError):
    status = 422
    code = "no_route"


class InfeasibleTrip(APIError):
    status = 422
    code = "infeasible_trip"
