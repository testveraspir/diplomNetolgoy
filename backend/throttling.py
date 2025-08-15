from rest_framework.throttling import AnonRateThrottle


class RegisterThrottle(AnonRateThrottle):
    rate = '5/hour'
    scope = 'register'
