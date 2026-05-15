class MembraError(Exception):
    pass

class IdentityError(MembraError):
    pass

class RiskDeniedError(MembraError):
    pass

class PaymentError(MembraError):
    pass

class InsuranceError(MembraError):
    pass

class AccessDeniedError(MembraError):
    pass

class CoverageNotActiveError(MembraError):
    pass
