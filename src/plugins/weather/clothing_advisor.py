from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

OPEN_METEO_SNOW_CODES = {71, 73, 75, 77, 85, 86}


def _to_celsius(temp, units):
    if units == "imperial":
        return (temp - 32) * 5 / 9
    elif units == "standard":
        return temp - 273.15
    return float(temp)


def _get_window_end(now):
    """Before 12:00 → check until 16:00, 12:00-21:59 → check until 22:00, 22:00+ → no recommendation."""
    if now.hour < 12:
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
    wind_values = hourly_data.get('windspeed_10m', [])
    precip_prob_values = hourly_data.get('precipitation_probability', [])
    precip_amount_values = hourly_data.get('precipitation', [])

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
    max_wind = 0.0
    is_rain = False
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

        if i < len(wind_values) and wind_values[i] is not None:
            wind = float(wind_values[i])
            if units == "imperial":
                wind = wind * 0.44704  # mph to m/s
            if wind > max_wind:
                max_wind = wind

        if i < len(weather_codes):
            code = int(weather_codes[i])
            if code in OPEN_METEO_SNOW_CODES:
                is_snow = True

        prob = precip_prob_values[i] if i < len(precip_prob_values) else 0
        amount = precip_amount_values[i] if i < len(precip_amount_values) else 0
        if (prob or 0) > 50 and (amount or 0) >= 0.5:
            is_rain = True

        dt_hour = dt.replace(minute=0, second=0, microsecond=0)
        uv = uv_map.get(dt_hour, 0.0)
        if uv > max_uv:
            max_uv = uv

    return {
        "feels_like_c": min_feels_like_c if min_feels_like_c is not None else 15.0,
        "max_wind_ms": max_wind,
        "is_rain": is_rain,
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
    max_wind_ms = conditions["max_wind_ms"]
    is_rain = conditions["is_rain"]
    is_snow = conditions["is_snow"]
    uv_index = conditions["uv_index"]
    is_day = conditions["is_day"]

    suggestions = []

    # Primary temperature layer
    if is_snow or feels_like_c <= -5:
        suggestions.append({"label": "Snow Jacket", "icon": "winter-clothes.png"})
    elif feels_like_c < 10:
        suggestions.append({"label": "Jacket", "icon": "jacket.png"})
    elif feels_like_c < 20:
        suggestions.append({"label": "Pullover", "icon": "hoodie.png"})
    else:
        suggestions.append({"label": "T-Shirt", "icon": "tshirt.png"})

    # Scarf: below 0°C, or below 8°C and windy
    if feels_like_c < 0 or (feels_like_c < 8 and max_wind_ms > 5):
        suggestions.append({"label": "Scarf", "icon": "scarf.png"})

    if feels_like_c <= -5:
        suggestions.append({"label": "Gloves", "icon": "gloves.png"})

    # Umbrella for any rain
    if is_rain:
        suggestions.append({"label": "Umbrella", "icon": "umbrella.png"})

    # Sun protection
    try:
        uv = float(uv_index)
        if is_day and uv >= 6:
            suggestions.append({"label": "Suncream", "icon": "suncream.png"})
        if is_day and uv >= 4 and feels_like_c > 15:
            suggestions.append({"label": "Sunglasses", "icon": "sunglasses.png"})
    except (ValueError, TypeError):
        pass

    return suggestions
