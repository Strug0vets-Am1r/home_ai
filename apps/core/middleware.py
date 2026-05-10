import urllib.parse
import zoneinfo
from django.utils import timezone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_tz = request.COOKIES.get('browser_timezone')
        if cookie_tz:
            cookie_tz = urllib.parse.unquote(cookie_tz)
        tz_name = cookie_tz or request.POST.get('browser_timezone')
        if tz_name:
            try:
                timezone.activate(zoneinfo.ZoneInfo(tz_name))
            except (zoneinfo.ZoneInfoNotFoundError, TypeError):
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)
