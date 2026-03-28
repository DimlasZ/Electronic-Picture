from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

OPEN_METEO_RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
OPEN_METEO_HEAVY_RAIN_CODES = {53, 55, 63, 65, 81, 82}
OPEN_METEO_SNOW_CODES = {71, 73, 75, 77, 85, 86}

OWM_HEAVY_RAIN_IDS = {302, 312, 502, 503, 504, 522, 531}


def _to_celsius(temp, units):
    if units == "imperial":
        return (temp - 32) * 5 / 9
    elif units == "standard":
        return temp - 273.15
    return float(temp)


def _get_window_end(now):
    """Before 14:00 → check until 16:00, 14:00-21:59 → check until 22:00, 22:00+ → no recommendation."""
    if now.hour < 14:
        return now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now.hour < 22:
        return now.replace(hour=22, minute=0, second=0, microsecond=0)
    return None


def extract_open_meteo_conditions(hourly_data, aqi_data, units, tz, now):
    """Extract worst-case conditions from Open-Meteo hourly forecast window."""
    window_start = now + timedelta(minutes=15)
    window_end = _get_window_end(now)
    if window_end is None:
        return None

    times = hourly_data.get('time', [])
    feels_like_values = hourly_data.get('apparent_temperature', [])
    weather_codes = hourly_data.get('weather_code', [])

    uv_times = aqi_data.get('hourly', {}).get('time', [])
    uv_values = aqi_data.get('hourly', {}).get('uv_index', [])
    uv_map = {}
    for i, t in enumerate(uv_times):
        try:
            dt = datetime.fromisoformat(t).astimezone(tz)
            uv_map[dt.replace(minute=0, second=0, microsecond=0)] = uv_values[i]
        except (ValueError, IndexError):
            pass

    min_feels_like_c = None
    is_rain = False
    is_heavy_rain = False
    is_snow = False
    max_uv = 0.0

    for i, time_str in enumerate(times):
        try:
            dt = datetime.fromisoformat(time_str).astimezone(tz)
        except ValueError:
            continue

        if dt < window_start or dt > window_end:
            continue

        if i < len(feels_like_values) and feels_like_values[i] is not None:
            feels_c = _to_celsius(feels_like_values[i], units)
            if min_feels_like_c is None or feels_c < min_feels_like_c:
                min_feels_like_c = feels_c

        if i < len(weather_codes):
            code = int(weather_codes[i])
            if code in OPEN_METEO_RAIN_CODES:
                is_rain = True
            if code in OPEN_METEO_HEAVY_RAIN_CODES:
                is_heavy_rain = True
            if code in OPEN_METEO_SNOW_CODES:
                is_snow = True

        dt_hour = dt.replace(minute=0, second=0, microsecond=0)
        uv = uv_map.get(dt_hour, 0.0)
        if uv > max_uv:
            max_uv = uv

    return {
        "feels_like_c": min_feels_like_c if min_feels_like_c is not None else 15.0,
        "is_rain": is_rain,
        "is_heavy_rain": is_heavy_rain,
        "is_snow": is_snow,
        "uv_index": max_uv,
        "is_day": max_uv > 0,
    }


def extract_owm_conditions(hourly_data, units, tz, now):
    """Extract worst-case conditions from OpenWeatherMap hourly forecast window."""
    window_start = now + timedelta(minutes=15)
    window_end = _get_window_end(now)
    if window_end is None:
        return None

    min_feels_like_c = None
    is_rain = False
    is_heavy_rain = False
    is_snow = False
    max_uv = 0.0

    for hour in hourly_data:
        dt_epoch = hour.get('dt')
        if not dt_epoch:
            continue
        dt = datetime.fromtimestamp(dt_epoch, tz=timezone.utc).astimezone(tz)

        if dt < window_start or dt > window_end:
            continue

        feels_like = hour.get("feels_like")
        if feels_like is not None:
            feels_c = _to_celsius(feels_like, units)
            if min_feels_like_c is None or feels_c < min_feels_like_c:
                min_feels_like_c = feels_c

        weather_id = hour.get("weather", [{}])[0].get("id", 0)
        if 200 <= weather_id < 600:
            is_rain = True
        if weather_id in OWM_HEAVY_RAIN_IDS:
            is_heavy_rain = True
        if 600 <= weather_id < 700:
            is_snow = True

        uvi = hour.get("uvi", 0.0) or 0.0
        if uvi > max_uv:
            max_uv = uvi

    return {
        "feels_like_c": min_feels_like_c if min_feels_like_c is not None else 15.0,
        "is_rain": is_rain,
        "is_heavy_rain": is_heavy_rain,
        "is_snow": is_snow,
        "uv_index": max_uv,
        "is_day": max_uv > 0,
    }


def get_clothing_suggestions(conditions):
    """Returns clothing suggestions based on forecast conditions.

    Each item: {"label": str, "icon": str (filename only, e.g. 'jacket.png')}
    Returns empty list if conditions is None (e.g. after 22:00).
    """
    if conditions is None:
        return []
    feels_like_c = conditions["feels_like_c"]
    is_rain = conditions["is_rain"]
    is_heavy_rain = conditions["is_heavy_rain"]
    is_snow = conditions["is_snow"]
    uv_index = conditions["uv_index"]
    is_day = conditions["is_day"]

    suggestions = []

    if is_snow or feels_like_c <= -5:
        suggestions.append({"label": "Snow Jacket", "icon": "winter-clothes.png"})
    elif feels_like_c < 10:
        suggestions.append({"label": "Jacket", "icon": "jacket.png"})
    elif feels_like_c < 20:
        suggestions.append({"label": "Hoodie", "icon": "hoodie.png"})
    else:
        suggestions.append({"label": "T-Shirt", "icon": "tshirt.png"})

    if feels_like_c <= 5:
        suggestions.append({"label": "Scarf", "icon": "scarf.png"})
    if feels_like_c <= 0:
        suggestions.append({"label": "Gloves", "icon": "gloves.png"})

    if is_heavy_rain:
        suggestions.append({"label": "Umbrella", "icon": "umbrella.png"})
    if is_rain:
        suggestions.append({"label": "Raincoat", "icon": "raincoat.png"})

    try:
        uv = float(uv_index)
        if is_day and uv >= 6:
            suggestions.append({"label": "Suncream", "icon": "suncream.png"})
        if is_day and uv >= 3:
            suggestions.append({"label": "Sunglasses", "icon": "sunglasses.png"})
    except (ValueError, TypeError):
        pass

    return suggestions
