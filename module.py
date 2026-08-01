from config import groq_api_key, maps_api_key, redis_client
import streamlit as st
import numpy as np
import pandas as pd
from groq import Groq
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
from datetime import datetime
import hashlib
import json
import math
import pydeck as pdk
import re
import requests
import uuid

# Category definitions: the single source of truth for the UI labels and for the
# includedPrimaryTypes sent to Places API (New).
#
# Types are language-independent, which is why no user-typed text ever reaches Google.
# Searching the Italian word "ristorante" abroad used to surface Italian restaurants;
# 'restaurant' returns local ones everywhere and 'lang' only localises the labels.
#
# Group composition matters because types are hierarchical - a parent pulls in its
# children. Two deliberate omissions, both verified against the API:
#   - 'aperitivo' omits the generic 'bar' ('bar' is a parent of 'pub'/'irish_pub')
#   - 'pastry' omits 'dessert_shop' ('dessert_shop' is a parent of 'ice_cream_shop')
CATEGORIES = {
    'restaurants': {'emoji': '🍴', 'it': 'Ristoranti', 'en': 'Restaurants',
                    'types': ['restaurant'],
                    'exclude': ['fast_food_restaurant', 'hamburger_restaurant']},
    'pizzeria':    {'emoji': '🍕', 'it': 'Pizzerie', 'en': 'Pizzerias',
                    'types': ['pizza_restaurant']},
    'pastry':      {'emoji': '🥐', 'it': 'Pasticcerie', 'en': 'Pastry shops',
                    'types': ['pastry_shop', 'bakery', 'cake_shop']},
    'gelato':      {'emoji': '🍦', 'it': 'Gelaterie', 'en': 'Ice cream',
                    'types': ['ice_cream_shop']},
    'breakfast':   {'emoji': '☕', 'it': 'Colazione e caffè', 'en': 'Breakfast & coffee',
                    'types': ['cafe', 'coffee_shop', 'breakfast_restaurant']},
    'aperitivo':   {'emoji': '🍸', 'it': 'Aperitivo', 'en': 'Aperitivo',
                    'types': ['cocktail_bar', 'wine_bar', 'lounge_bar']},
    'pub':         {'emoji': '🍺', 'it': 'Pub e birrerie', 'en': 'Pubs & breweries',
                    'types': ['pub', 'irish_pub', 'brewpub', 'beer_garden']},
    'stay':        {'emoji': '🛏️', 'it': 'Dove dormire', 'en': 'Where to stay',
                    'types': ['hotel', 'bed_and_breakfast', 'guest_house', 'hostel',
                              'inn', 'resort_hotel', 'lodging']},
    'museum':      {'emoji': '🏛️', 'it': 'Musei', 'en': 'Museums',
                    'types': ['museum', 'art_museum', 'history_museum', 'art_gallery']},
    'landmarks':   {'emoji': '📌', 'it': 'Luoghi di interesse', 'en': 'Landmarks',
                    'types': ['cultural_landmark', 'historical_landmark', 'historical_place',
                              'monument', 'castle', 'sculpture', 'fountain', 'plaza',
                              'observation_deck']},
    'worship':     {'emoji': '⛪', 'it': 'Luoghi di culto', 'en': 'Places of worship',
                    'types': ['church', 'mosque', 'synagogue', 'buddhist_temple',
                              'hindu_temple', 'shinto_shrine']},
    'attractions': {'emoji': '🎡', 'it': 'Attrazioni turistiche', 'en': 'Attractions',
                    'types': ['tourist_attraction', 'amusement_park', 'zoo', 'aquarium',
                              'planetarium']},
    'nature':      {'emoji': '🌳', 'it': 'Parchi e natura', 'en': 'Parks & nature',
                    'types': ['park', 'city_park', 'national_park', 'garden',
                              'botanical_garden', 'beach', 'scenic_spot']},
    'shows':       {'emoji': '🎭', 'it': 'Teatri e concerti', 'en': 'Theatre & music',
                    'types': ['performing_arts_theater', 'opera_house', 'concert_hall',
                              'live_music_venue']},
}

# Categories that are places to eat or drink. Used to decide which card rows make
# sense: a church has no price level and a park has no phone number.
FOOD_CATEGORIES = {'restaurants', 'pizzeria', 'pastry', 'gelato', 'breakfast', 'aperitivo', 'pub'}

# Old ?keyword= values, so links shared before this change keep working.
LEGACY_KEYWORD_ALIASES = {
    'restaurants': 'restaurants',
    'pizzeria': 'pizzeria',
    'pub': 'pub',
    'museum': 'museum',
    'cocktail': 'aperitivo',
    'point+of+interest': 'landmarks',
    'point of interest': 'landmarks',
}

DAY_TRIP_KEYWORD = 'a+day+trip'

# A hand-typed (or documented) '?keyword=a+day+trip' arrives as 'a day trip', because
# parse_qs decodes '+' as a space. Links shared from the app are unaffected - Streamlit
# writes the key back as %2B - but the pseudo-category must answer to both forms or the
# literal URL falls through to normalize_category and silently becomes 'restaurants'.
DAY_TRIP_KEYWORD_ALIASES = {DAY_TRIP_KEYWORD, DAY_TRIP_KEYWORD.replace('+', ' ')}

# A planned day is always the same standard day: breakfast at 09:30 through to a last round
# ending by 23:30. The traveller used to pick a start time and a half-day flag; both are gone
# on purpose. They multiplied the shapes a plan could take (and the cache keys behind them)
# to answer a question the traveller is better placed to answer on the day itself - the
# itinerary is a running order, and shifting it by an hour needs no app.
#
# The one thing still asked for is the DATE, because it is not a preference: opening hours
# are per weekday, and a Monday plan in Rome must not send anyone to a closed museum.
DAY_TRIP_START_MINUTES = 9 * 60 + 30
DAY_TRIP_END_MINUTES = 23 * 60 + 30

# The shape of a day is data, not prose. Every slot is one entry here and the searches, the
# planner prompt, the map and the timeline all pick it up - adding a stop never means
# editing main.py.
#
#   category   a CATEGORIES key. Two slots may share one ('landmarks', 'restaurants'); a
#              shared category is still ONE Places call, split into disjoint candidate
#              slices so the same place cannot fill both slots.
#   dwell      minutes spent at the stop, used to compute the clock.
#   essential  a meal. The model may drop any other slot to keep the day tight, but a day
#              trip without dinner is a bug, so these are refilled in code when it does.
#   earliest /
#   latest     the sensible arrival window, in minutes from midnight. Times are clamped
#              forward into it, so a morning that overruns does not serve dinner at 15:00,
#              and a slot whose window has already passed is skipped rather than faked -
#              that is how a slow museum drops the green break instead of the dinner.
#
# The windows are cut to the fixed frame: every slot satisfies
# `latest + dwell <= DAY_TRIP_END_MINUTES`, so no reachable schedule can run past 23:30.
# `test_day_trip_windows_fit_the_day` asserts it, and any new slot must keep it true.
DAY_TRIP_SLOTS = [
    {'key': 'breakfast',   'category': 'breakfast',   'dwell': 45, 'essential': True, 'emoji': '☕',
     'it': 'Colazione', 'en': 'Breakfast',
     'earliest': 8 * 60, 'latest': 11 * 60},
    {'key': 'landmark_am', 'category': 'landmarks',   'dwell': 60, 'emoji': '📌',
     'it': 'Prima tappa', 'en': 'First stop',
     'earliest': 9 * 60, 'latest': 13 * 60},
    {'key': 'museum',      'category': 'museum',      'dwell': 90, 'emoji': '🏛️',
     'it': 'Museo', 'en': 'Museum',
     'earliest': 9 * 60 + 30, 'latest': 16 * 60},
    {'key': 'lunch',       'category': 'restaurants', 'dwell': 75, 'essential': True, 'emoji': '🍴',
     'it': 'Pranzo', 'en': 'Lunch',
     'earliest': 12 * 60, 'latest': 14 * 60 + 30},
    {'key': 'nature',      'category': 'nature',      'dwell': 60, 'emoji': '🌳',
     'it': 'Pausa verde', 'en': 'Green break',
     'earliest': 13 * 60, 'latest': 18 * 60},
    {'key': 'landmark_pm', 'category': 'landmarks',   'dwell': 45, 'emoji': '📌',
     'it': 'Nel pomeriggio', 'en': 'In the afternoon',
     'earliest': 14 * 60, 'latest': 19 * 60},
    {'key': 'aperitivo',   'category': 'aperitivo',   'dwell': 60, 'emoji': '🍸',
     'it': 'Aperitivo', 'en': 'Aperitivo',
     'earliest': 17 * 60, 'latest': 20 * 60},
    {'key': 'dinner',      'category': 'restaurants', 'dwell': 90, 'essential': True, 'emoji': '🍴',
     'it': 'Cena', 'en': 'Dinner',
     'earliest': 19 * 60, 'latest': 21 * 60},
    {'key': 'pub',         'category': 'pub',         'dwell': 60, 'emoji': '🍺',
     'it': 'Ultimo giro', 'en': 'Last round',
     'earliest': 20 * 60 + 30, 'latest': 22 * 60 + 30},
]


# Below this a plan is not the day the mode promises - a village can yield a lunch and a
# dinner five hours apart, which renders as a perfectly ordinary two-stop itinerary. The UI
# says so rather than letting it pass for one.
DAY_TRIP_THIN_STOPS = len(DAY_TRIP_SLOTS) // 2


def day_trip_slots() -> list:
    """The slots that make up a plan, in visiting order."""
    return list(DAY_TRIP_SLOTS)


def day_trip_categories() -> list:
    """Distinct categories to search - one Places call each, so this is the cost of a plan."""
    seen = []
    for slot in DAY_TRIP_SLOTS:
        if slot['category'] not in seen:
            seen.append(slot['category'])
    return seen


def slot_by_key(key: str) -> dict:
    return next((s for s in DAY_TRIP_SLOTS if s['key'] == key), None)


def slot_label(slot: dict, lang: str) -> str:
    return f"{slot['emoji']} {slot[lang if lang in ('it', 'en') else 'en']}"


def category_label(key: str, lang: str) -> str:
    """Emoji + localised name, e.g. '🥐 Pasticcerie'."""
    cat = CATEGORIES[key]
    return f"{cat['emoji']} {cat[lang if lang in ('it', 'en') else 'en']}"


def is_day_trip(keyword: str) -> bool:
    """True for the day-trip pseudo-category, in either its '+' or space-decoded form."""
    return keyword in DAY_TRIP_KEYWORD_ALIASES


def normalize_category(keyword: str) -> str:
    """Map any ?keyword= value (current or legacy) to a valid category key."""
    if keyword in CATEGORIES:
        return keyword
    return LEGACY_KEYWORD_ALIASES.get(keyword, 'restaurants')


class PlacesApiError(Exception):
    """Places API returned a non-200 response"""
    pass


class BadAddressError(Exception):
    """No results found for address"""
    pass

class ServiceError(Exception):
    """Nominatim service issue (quota, timeout, etc.)"""
    pass

def _redis_key_for_address(address: str) -> str:
    """Normalize address for consistent caching"""
    norm = address.strip().lower()
    return f"geocode:{norm[:200]}"

def _log_geocode_usage(address: str):
    """Simple stats counter"""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    redis_client.incr(f"stats:geocode:total:{day}")
    addr_key = _redis_key_for_address(address)
    redis_client.incr(f"stats:geocode:addr:{day}:{addr_key}")

# Google's terms allow caching place IDs indefinitely but other Places content for at
# most 30 consecutive days, so this matches the geocode TTL above rather than exceeding it.
PLACES_CACHE_TTL = 60 * 60 * 24 * 30

# An empty result set is cached too, but only briefly. Not caching it at all would let
# Streamlit's rerun-on-every-interaction turn one fruitless search into a burst of
# billable calls; caching it for the full 30 days would stretch a momentary Google-side
# gap - or a place indexed a day later - into a month of "nothing here" for everyone
# searching that ~100m cell.
EMPTY_SEARCH_CACHE_TTL = 60 * 10


def _redis_key_for_search(body: dict, with_reviews: bool) -> str:
    """Cache key for a Nearby Search.

    Coordinates are rounded to ~100m so repeated searches around the same spot reuse one
    response. 'with_reviews' is part of the key because the two field masks return
    different payloads (and bill to different SKUs).
    """
    circle = body['locationRestriction']['circle']
    lat = round(circle['center']['latitude'], 3)
    lon = round(circle['center']['longitude'], 3)
    parts = [
        f"{lat}", f"{lon}",
        f"{int(circle['radius'])}",
        ",".join(body['includedPrimaryTypes']),
        ",".join(body.get('excludedPrimaryTypes', [])),
        body.get('languageCode', ''),
        "r" if with_reviews else "n",
    ]
    return "places:nearby:" + "|".join(parts)


def get_cached_search(body: dict, with_reviews: bool):
    """Returns the cached list of places, or None on a miss."""
    try:
        cached = redis_client.get(_redis_key_for_search(body, with_reviews))
    except Exception:
        return None
    if not cached:
        return None
    try:
        return json.loads(cached)
    except (ValueError, TypeError):
        return None


def cache_search(body: dict, with_reviews: bool, places: list) -> None:
    try:
        redis_client.setex(
            _redis_key_for_search(body, with_reviews),
            PLACES_CACHE_TTL if places else EMPTY_SEARCH_CACHE_TTL,
            json.dumps(places),
        )
    except Exception:
        # A cache outage must not take the search down.
        pass


def log_places_usage(category: str, with_reviews: bool) -> None:
    """Counts real Places calls per SKU, so free-tier burn is visible per day.

    Requesting reviews moves the call from the Nearby Search Enterprise SKU to
    Enterprise + Atmosphere; each has its own monthly free allowance.
    """
    sku = "enterprise_atmosphere" if with_reviews else "enterprise"
    day = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        redis_client.incr(f"stats:places:{sku}:{day}")
        redis_client.incr(f"stats:places:category:{day}:{category}")
    except Exception:
        pass


VISITOR_COUNT_KEY = 'stats:visits:total'

# Carries over the total the third-party badge was showing when it was replaced, so the
# footer does not appear to reset to zero. Applied with SETNX, so it is a one-time floor and
# never overwrites a live count.
VISITOR_COUNT_SEED = 2498


def get_visitor_count() -> int:
    """Total visits, counted once per session.

    Streamlit re-executes the whole script on every interaction, so incrementing on each run
    would count a button click or a slider nudge as a new visitor. The count is therefore
    taken once and kept in session state, which doubles as the guard.

    Returns 0 if Redis is unreachable; the caller hides the counter rather than showing zero.
    """
    if 'visit_count' in st.session_state:
        return st.session_state['visit_count']

    try:
        redis_client.setnx(VISITOR_COUNT_KEY, VISITOR_COUNT_SEED)
        count = int(redis_client.incr(VISITOR_COUNT_KEY))
    except Exception:
        # A Redis outage must not break the footer.
        count = 0

    st.session_state['visit_count'] = count
    return count


def format_visitor_count(count: int, lang: str) -> str:
    """Thousands separator matching the locale: 2.498 in Italian, 2,498 in English."""
    grouped = f"{count:,}"
    return grouped.replace(',', '.') if lang == 'it' else grouped


@st.cache_data(ttl=3600)
def get_coordinates(address: str) -> pd.DataFrame:
    key = _redis_key_for_address(address)

    cached = redis_client.get(key)
    if cached:
        data = json.loads(cached)
        return pd.DataFrame({"lat": [data["lat"]], "lon": [data["lon"]]})

    try:
        geolocator = Nominatim(user_agent="choosingclub_webapp", timeout=10)
        location = geolocator.geocode(address)
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as e:
        _log_geocode_usage(address)
        raise ServiceError(f"Nominatim service error: {str(e)}")

    if location is None:
        # Valid call but no results: cache the miss to avoid repeated calls for bad addresses
        miss_data = {"lat": None, "lon": None}
        redis_client.setex(key, 3600, json.dumps(miss_data))
        raise BadAddressError(f"No geocoding results for address: {address}")

    lat = location.latitude
    lon = location.longitude

    redis_client.setex(
        key,
        60 * 60 * 24 * 30,
        json.dumps({"lat": lat, "lon": lon})
    )

    _log_geocode_usage(address)

    return pd.DataFrame({"lat": [lat], "lon": [lon]})


# --- Address autocomplete -----------------------------------------------------------------
#
# The address box asks Google for predictions as the user types, then resolves the picked
# prediction by place id. That removes the mistyped-address failure mode entirely: nothing
# is geocoded from free text unless autocomplete returned nothing at all, in which case
# main.py falls back to get_coordinates above.

AUTOCOMPLETE_URL = 'https://places.googleapis.com/v1/places:autocomplete'
PLACE_DETAILS_URL = 'https://places.googleapis.com/v1/places/{place_id}'

AUTOCOMPLETE_FIELDS = 'suggestions.placePrediction.placeId,suggestions.placePrediction.text'

# 'location' and 'formattedAddress' are both Place Details **Essentials** fields
# (10,000 free/month - the cheapest tier). Resolving a pick must never ask for an
# Enterprise field such as rating or priceLevel, which would bill at 1,000 free/month.
DETAILS_LOCATION_FIELDS = 'location,formattedAddress'

# Predictions are fetched while the user types, so two guards keep the request count down:
# prefixes shorter than this are never sent, and every prefix is cached.
MIN_AUTOCOMPLETE_CHARS = 3
AUTOCOMPLETE_CACHE_TTL = 60 * 60 * 24


def autocomplete_session_token() -> str:
    """The token that ties a burst of keystrokes to one billable autocomplete session.

    Google treats requests sharing a token - plus the Place Details call that resolves the
    pick - as a single session, so the token is created once per lookup and rotated only
    after a pick resolves (see reset_autocomplete_session).
    """
    if not st.session_state.get('ac_token'):
        st.session_state['ac_token'] = str(uuid.uuid4())
    return st.session_state['ac_token']


def reset_autocomplete_session() -> None:
    """Ends the current session so the next address lookup starts a new one."""
    st.session_state['ac_token'] = str(uuid.uuid4())


def _log_autocomplete_usage(kind: str) -> None:
    """Counts autocomplete and detail calls per day, alongside the Nearby Search counters."""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        redis_client.incr(f"stats:places:{kind}:{day}")
    except Exception:
        pass


def autocomplete_address(query: str, lang: str = 'it') -> list:
    """Address and landmark predictions for a partially typed query.

    Returns a list of (label, place_id) pairs - the shape streamlit-searchbox expects: it
    shows the label and hands back the place id. Returns [] rather than raising, because a
    dead autocomplete must leave the box usable; main.py degrades to Nominatim.
    """
    query = (query or '').strip()
    if len(query) < MIN_AUTOCOMPLETE_CHARS:
        return []

    cache_key = f"places:autocomplete:{lang}:{query.lower()[:200]}"
    try:
        cached = redis_client.get(cache_key)
    except Exception:
        cached = None
    if cached:
        try:
            return [tuple(pair) for pair in json.loads(cached)]
        except (ValueError, TypeError):
            pass

    body = {
        'input': query,
        'languageCode': lang,
        'sessionToken': autocomplete_session_token(),
    }
    try:
        resp = requests.post(
            AUTOCOMPLETE_URL,
            headers={
                'X-Goog-Api-Key': str(maps_api_key),
                'X-Goog-FieldMask': AUTOCOMPLETE_FIELDS,
                'Content-Type': 'application/json',
            },
            json=body,
            timeout=10,
        )
    except requests.RequestException:
        _log_autocomplete_usage('autocomplete_error')
        return []

    if resp.status_code != 200:
        _log_autocomplete_usage('autocomplete_error')
        return []

    predictions = []
    for suggestion in resp.json().get('suggestions', []):
        # Query predictions carry no placeId and cannot be resolved, so they are skipped.
        prediction = suggestion.get('placePrediction') or {}
        label = prediction.get('text', {}).get('text')
        place_id = prediction.get('placeId')
        if label and place_id:
            predictions.append((label, place_id))

    _log_autocomplete_usage('autocomplete')
    try:
        redis_client.setex(cache_key, AUTOCOMPLETE_CACHE_TTL, json.dumps(predictions))
    except Exception:
        pass
    return predictions


def resolve_place(place_id: str, lang: str = 'it') -> tuple:
    """Turns a picked prediction into ((lat, lon) frame, formatted address).

    Raises BadAddressError if the id does not resolve - the API answers 400 for an invalid
    place id rather than returning an empty body, so a failure here is loud.
    """
    cache_key = f"places:location:{place_id}"
    try:
        cached = redis_client.get(cache_key)
    except Exception:
        cached = None
    if cached:
        try:
            data = json.loads(cached)
            return pd.DataFrame({"lat": [data['lat']], "lon": [data['lon']]}), data['address']
        except (ValueError, TypeError, KeyError):
            pass

    params = {'languageCode': lang, 'sessionToken': autocomplete_session_token()}
    try:
        resp = requests.get(
            PLACE_DETAILS_URL.format(place_id=place_id),
            headers={
                'X-Goog-Api-Key': str(maps_api_key),
                'X-Goog-FieldMask': DETAILS_LOCATION_FIELDS,
            },
            params=params,
            timeout=10,
        )
    except requests.RequestException as e:
        raise ServiceError(f"Place Details request failed: {e}")

    if resp.status_code != 200:
        raise BadAddressError(f"Place id did not resolve: {place_id}")

    body = resp.json()
    location = body.get('location') or {}
    lat, lon = location.get('latitude'), location.get('longitude')
    if lat is None or lon is None:
        raise BadAddressError(f"No location on place: {place_id}")

    address = body.get('formattedAddress') or ''
    _log_autocomplete_usage('details_essentials')
    try:
        # Place ids may be cached indefinitely, but the coordinates and address they
        # resolve to are Places content, so this stays under the 30-day cap.
        redis_client.setex(cache_key, PLACES_CACHE_TTL,
                           json.dumps({'lat': lat, 'lon': lon, 'address': address}))
    except Exception:
        pass

    # The pick closed this session; the next lookup gets a fresh token.
    reset_autocomplete_session()
    return pd.DataFrame({"lat": [lat], "lon": [lon]}), address


# Places API (New) reports price as an enum string rather than an integer 0-4.
PRICE_LEVELS = {
    'PRICE_LEVEL_FREE': '🆓',
    'PRICE_LEVEL_INEXPENSIVE': '🟩⬜⬜⬜',
    'PRICE_LEVEL_MODERATE': '🟩🟨⬜⬜',
    'PRICE_LEVEL_EXPENSIVE': '🟩🟨🟧⬜',
    'PRICE_LEVEL_VERY_EXPENSIVE': '🟩🟨🟧🟥',
}


def _flatten_html(html: str) -> str:
    """Strip every line's indentation from a block of HTML.

    st.markdown dedents by the *common* indent and then renders what is left as markdown, so
    any line still indented four spaces becomes a literal code block. Composing two snippets
    written at different indent levels - a trip step wrapping a card - is enough to trigger
    that. HTML does not care about leading whitespace, so removing all of it is the fix that
    cannot regress when the source indentation moves again.
    """
    return "\n".join(line.strip() for line in html.splitlines() if line.strip())


def _card_html(metadata: dict, rank: int) -> str:
    """One place card. Shared by the search results and the day-trip timeline, so a change
    to the card markup lands in both."""
    # Rows are built conditionally: a church has no price level and a park has no
    # phone number, so an absent value drops the row instead of printing '❔'.
    score_rows = []
    if metadata.get('score'):
        score_rows.append(f"<li>Choosing Score: {metadata['score']}/100 </li>")
    price_level = PRICE_LEVELS.get(metadata.get('price_level'))
    if price_level:
        score_rows.append(f"<li>Price level: {price_level} </li>")
    if metadata.get('accessible') is not None:
        accessible = "🟢" if metadata['accessible'] else "🔴"
        score_rows.append(f"<li>Wheelchair accessibility: {accessible} </li>")

    contact_rows = []
    if metadata.get('vicinity'):
        contact_rows.append(
            f"<li> <strong> Address: </strong> "
            f"<a href={metadata['google_url']}> {metadata['vicinity']} </a> </li>"
        )
    if metadata.get('phone_number'):
        tel = "".join(metadata['phone_number'].split(" ")[1:])
        contact_rows.append(
            f"<li> <strong> Phone:   </strong> "
            f"<a href=\"tel:{tel}\"> {metadata['phone_number']} </a> </li>"
        )
    if metadata.get('opening_time'):
        contact_rows.append(
            f"<li> <strong> Opening: </strong> <br> {metadata['opening_time']}  </li>"
        )

    website = metadata['website'] if metadata['website'] else ""
    scores_heading = "<strong>Scores</strong>" if score_rows else ""

    return _flatten_html(f"""
        <div class="restaurant-card">
            <div class="grid-container">
                <div class="grid-item">
                    <h1 class="restaurant-name"><a href={website}> {rank}° · {metadata['name']}</a></h1>
                    <div class="restaurant-info"> {scores_heading}
                        <ul class="details">
                            {"".join(score_rows)}
                        </ul>
                    </div>
                </div>
                <div class="grid-item">
                    <div class="restaurant-info">
                        <ul class="details">
                            {"".join(contact_rows)}
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    """)


def create_cards(recommandations_placeids: list, choosing_instance, llm_answer=None):
    cards_html = []
    rank = 0

    for place_id in recommandations_placeids:
        rank += 1

        metadata, _ = choosing_instance.get_metadata_and_reviews(place_id)

        if llm_answer:
            if metadata['name'] not in llm_answer:
                rank -= 1
                continue

        cards_html.append(_card_html(metadata, rank))

    all_cards_html = "\n".join(cards_html)
    return all_cards_html


# ---------------------------------------------------------------------------
# One-day trip: geometry, clock and opening hours
#
# All pure functions - no Streamlit, no network - so they can be exercised without spending
# an API call. The itinerary used to be six hardcoded prose strings; these are what make it
# a real schedule instead.
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6371008.8

# Streets are not straight lines. 1.3 is the usual detour factor for a dense European
# centre and 4.5 km/h an unhurried tourist pace. This is deliberately not a routing API:
# a plan costs no extra quota, and legs are labelled approximate for exactly that reason.
WALK_DETOUR = 1.3
WALK_KMH = 4.5

# Past this a "walk" is really a bus ride, so the scheduler looks for a nearer candidate.
MAX_LEG_M = 2500

WEEK_MINUTES = 7 * 24 * 60


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def walk_leg(origin, destination):
    """Approximate walking distance and time between two (lat, lng) pairs.

    Returns None when either end has no coordinates, so the caller omits the leg rather
    than inventing one.
    """
    if not origin or not destination:
        return None
    if any(v is None for v in tuple(origin) + tuple(destination)):
        return None
    metres = int(round(haversine_m(origin[0], origin[1], destination[0], destination[1])
                       * WALK_DETOUR))
    if metres == 0:
        # Same spot - the village trattoria doing lunch and dinner, or two entrances to one
        # building. There is no walk, and "~0 m · 1 min a piedi" would be a printed fiction.
        return None
    return {'metres': metres,
            'minutes': max(1, int(round(metres / 1000.0 / WALK_KMH * 60)))}


def format_leg(leg, lang: str) -> str:
    if not leg:
        return ""
    metres = leg['metres']
    distance = f"{metres} m" if metres < 1000 else f"{metres / 1000:.1f} km"
    if lang == 'it':
        return f"🚶 ~{distance} · {leg['minutes']} min a piedi"
    return f"🚶 ~{distance} · {leg['minutes']} min walk"


def format_clock(minutes) -> str:
    """Minutes from midnight as HH:MM, wrapping past midnight."""
    return f"{int(round(minutes)) % 1440 // 60:02d}:{int(round(minutes)) % 60:02d}"


def google_weekday(day) -> int:
    """Google numbers days 0 = Sunday; datetime numbers them 0 = Monday."""
    return (day.weekday() + 1) % 7


def _week_spans(periods):
    """Opening periods as (start, end) minute offsets from Sunday 00:00.

    Google's 'periods[].open/close' use day 0 = Sunday. A close earlier than its open wraps
    into the next day. Returns the string 'always' for a place that never closes and [] when
    hours are unknown.

    **A 24/7 place does not come back as an open with no close.** That is how the reference
    describes it, and how `regularOpeningHours` behaves, but `currentOpeningHours` - the only
    hours object in the field mask - instead sends one `truncated` period covering the current
    week: open today 00:00, close the day before, next week, at 23:59. Across 2,981 cached
    places the no-close form appeared *zero* times and the week-long form 264 times, all of
    them always-open: Piazza Navona, the Arco di Costantino, every park in Carpegna. Matched
    on length rather than the `truncated` flag, because a period covering the whole week means
    the same thing however it was encoded.
    """
    spans = []
    for period in periods or []:
        opening = period.get('open') or {}
        if 'day' not in opening:
            continue
        start = opening['day'] * 1440 + opening.get('hour', 0) * 60 + opening.get('minute', 0)
        closing = period.get('close')
        if not closing:
            return 'always'
        end = (closing.get('day', opening['day']) * 1440
               + closing.get('hour', 0) * 60 + closing.get('minute', 0))
        if end <= start:
            end += WEEK_MINUTES
        # A minute short of seven days is the 23:59 close above; a place open that long has
        # no closing day, and treating it as one span starting on a Saturday is what made
        # `hours_window` answer 'closed' for the other six.
        if end - start >= WEEK_MINUTES - 1:
            return 'always'
        spans.append((start, end))
    return spans


def _format_span_end(end: int) -> str:
    """Midnight reads better as 24:00 than as 00:00 at the end of a window."""
    return '24:00' if end % 1440 == 0 else format_clock(end)


def hours_window(periods, weekday: int):
    """The day's opening window as '09:00-19:00', 'closed', or None when hours are unknown.

    'weekday' is Google's numbering, 0 = Sunday. Built from the structured periods, never
    from weekdayDescriptions - those are localised prose and unparseable in general.
    """
    spans = _week_spans(periods)
    if spans == 'always':
        return '00:00-24:00'
    if not spans:
        return None
    today = [(s, e) for s, e in spans if s // 1440 == weekday]
    if not today:
        return 'closed'
    return ", ".join(f"{format_clock(s)}-{_format_span_end(e)}" for s, e in sorted(today))


def is_open_at(periods, weekday: int, minute_of_day):
    """True, False, or None when the place publishes no hours.

    None is a real answer and is treated as such by the callers: an unknown is flagged
    nowhere and hides nothing, because most landmarks and parks publish no hours at all.
    """
    spans = _week_spans(periods)
    if spans == 'always':
        return True
    if not spans:
        return None
    target = weekday * 1440 + int(minute_of_day)
    for moment in (target, target + WEEK_MINUTES):
        if any(start <= moment < end for start, end in spans):
            return True
    return False


# ---------------------------------------------------------------------------
# One-day trip: the LLM planner
# ---------------------------------------------------------------------------

DAY_TRIP_MODEL = "openai/gpt-oss-120b"
DAY_TRIP_MAX_CANDIDATES = 4

# The plan embeds Places content, so Google's 30-day cache cap applies to it transitively -
# this must stay <= PLACES_CACHE_TTL. A week is ample: the searches behind it are cached for
# 30 days anyway, so replanning the same address costs neither a Places call nor a Groq one.
LLM_CACHE_TTL = 60 * 60 * 24 * 7

WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

DAY_TRIP_SYSTEM_PROMPT = """You plan one-day itineraries for Choosing.

You receive candidate stops, one compact JSON object per line:
  id     short candidate id - reuse these verbatim, never invent one
  slot   which part of the day this candidate belongs to
  name   the place name
  score  Choosing Score 0-100, higher is better (absent means unrated)
  hours  opening window for the day being planned (absent means the place publishes none)
  d      metres from the centre of the search area

You also receive the running order: one line per slot with the window it is visited in and
how long the stop lasts. The clock is not yours to set - it is there so you can tell whether
a candidate is actually open when the day reaches it.

Rules:
1. Pick AT MOST ONE candidate per slot, and never use the same place twice.
2. Never pick a candidate that cannot be open during its slot's window. Skip the slot
   instead - a shorter correct day beats a full wrong one.
3. Keep consecutive stops close together: prefer candidates with a similar d, and drop a
   slot rather than send the traveller across the city and back.
   The meal slots are the exception - the traveller has to eat, so fill every one that has
   a usable candidate even when nothing nearby is ideal.
4. Keep the slots in the order you receive them.
5. Do NOT output times or durations. Both are computed from the walking distances and from
   how long each kind of stop is worth - your job is which places, and in which order.

Answer with JSON only - no prose, no code fences:
{"title": "...", "stops": [{"id": "A1", "note": "..."}], "closing": "..."}
  title    one short line naming the day
  note     one sentence, max 20 words, on why this stop earns its place
  closing  one short practical closing line
Write title, note and closing in %(language)s."""


def slot_window(slot: dict) -> tuple:
    """The arrival window a slot is actually visited in, clamped to the standard day.

    A slot may open earlier than the day does (breakfast from 08:00), which is only there so
    the clamp in `schedule_stops` is a no-op at 09:30. Printing that 08:00 in the prompt
    would invite the model to judge a place open in an hour the day never reaches.
    """
    return max(slot['earliest'], DAY_TRIP_START_MINUTES), slot['latest']


def _slot_lines() -> str:
    """The running order, so the model can judge 'open during its slot' for itself."""
    lines = []
    for slot in DAY_TRIP_SLOTS:
        start, end = slot_window(slot)
        meal = " - a meal, do not skip" if slot.get('essential') else ""
        lines.append(f"{slot['key']} {format_clock(start)}-{format_clock(end)}, "
                     f"stay {slot['dwell']} min{meal}")
    return "\n".join(lines)


def _candidate_lines(pool: dict) -> str:
    """One compact line per candidate.

    Short synthetic ids ('A1') rather than 27-character Google place ids, and one already
    resolved opening window rather than the seven localised weekday strings. Both exist to
    keep the prompt small - the free tier is the constraint here, not the model.
    """
    lines = []
    for slot in DAY_TRIP_SLOTS:
        for candidate in pool.get(slot['key'], []):
            entry = {'id': candidate['sid'], 'slot': slot['key'],
                     'name': candidate['metadata']['name'], 'd': candidate['dist_m']}
            if candidate['metadata'].get('score'):
                entry['score'] = candidate['metadata']['score']
            if candidate['hours']:
                entry['hours'] = candidate['hours']
            lines.append(json.dumps(entry, ensure_ascii=False))
    return "\n".join(lines)


def _extract_json(raw):
    """Tolerant parse: the prompt forbids code fences, reasoning models add them anyway."""
    if not raw:
        return None
    text = re.sub(r'```[a-zA-Z]*', '', str(raw)).strip()
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return None


def _parse_plan(raw, by_sid: dict):
    """Validate the model's answer against the pool. Anything unrecognised is dropped."""
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None

    stops, used_places, used_slots = [], set(), set()
    for item in data.get('stops') or []:
        if not isinstance(item, dict):
            continue
        candidate = by_sid.get(str(item.get('id', '')).strip())
        if candidate is None:
            continue  # a hallucinated id, or one from another plan
        # 'reuse' is set by build_day_trip_pool only where a meal slot has nothing else to
        # offer, so it is the one way a place may appear twice in a day.
        if candidate['place_id'] in used_places and not candidate.get('reuse'):
            continue
        if candidate['slot'] in used_slots:
            continue
        used_places.add(candidate['place_id'])
        used_slots.add(candidate['slot'])
        slot = slot_by_key(candidate['slot']) or {}
        note = str(item.get('note')).strip() if item.get('note') else None
        # How long to stay comes from the slot, not from the model: asked for it, the model
        # answers 60 minutes for a fountain and 60 for the Colosseum. The slot durations at
        # least distinguish a 90-minute museum from a 45-minute viewpoint.
        stops.append({'slot': candidate['slot'], 'place_id': candidate['place_id'],
                      'note': note or None, 'dwell': slot.get('dwell', 60)})

    if not stops:
        return None

    # Rule 3's exception is a request too. Asked to keep the day tight, the model will
    # happily return a Rome itinerary with no dinner in it - so a meal slot that has an
    # unused candidate is filled here, best-scoring first, with no note rather than an
    # invented one. The clamp in schedule_stops still drops it if it cannot be reached.
    for slot in DAY_TRIP_SLOTS:
        if not slot.get('essential') or slot['key'] in used_slots:
            continue
        for candidate in by_sid.values():
            if candidate['slot'] != slot['key']:
                continue
            if candidate['place_id'] in used_places and not candidate.get('reuse'):
                continue
            used_places.add(candidate['place_id'])
            used_slots.add(slot['key'])
            stops.append({'slot': slot['key'], 'place_id': candidate['place_id'],
                          'note': None, 'dwell': slot['dwell']})
            break

    # Rule 4 is a request, not a guarantee, so the order is enforced here.
    order = [s['key'] for s in DAY_TRIP_SLOTS]
    stops.sort(key=lambda s: order.index(s['slot']))
    return {
        'title': str(data['title']).strip() if data.get('title') else None,
        'closing': str(data['closing']).strip() if data.get('closing') else None,
        'stops': stops,
    }


def _redis_key_for_plan(place_ids, lang: str, weekday) -> str:
    """Hashed, unlike places:nearby:, because the candidate id set is long.

    The start time and the half-day flag used to be part of this key. Dropping them is most
    of the point of the fixed day: the same address on the same weekday is now one cache
    entry instead of one per (start time x pace) the traveller happened to dial in.
    """
    payload = "|".join([",".join(sorted(place_ids)), lang, str(int(weekday))])
    return f"llm:daytrip:{lang}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def get_cached_plan(key: str):
    try:
        cached = redis_client.get(key)
    except Exception:
        return None
    if not cached:
        return None
    try:
        return json.loads(cached)
    except (ValueError, TypeError):
        return None


def cache_plan(key: str, plan: dict) -> None:
    if not plan or not plan.get('stops'):
        # Never pin an empty answer. This model returning empty content is a known failure
        # mode, and caching it would stretch a momentary outage into a week-long one.
        return
    try:
        redis_client.setex(key, LLM_CACHE_TTL, json.dumps(plan))
    except Exception:
        # A cache outage must not take planning down.
        pass


def log_llm_usage(kind: str) -> None:
    """Groq burn per day, so the LLM free tier is as visible as the Places SKUs already are."""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        redis_client.incr(f"stats:llm:{kind}:{day}")
    except Exception:
        pass


def _plan_day_trip_llm(pool: dict, by_sid: dict, lang: str, weekday: int):
    """One Groq call. Returns None on any failure, which hands over to the fallback."""
    language = 'Italian' if lang == 'it' else 'English'
    user_message = (
        f"Day: {WEEKDAY_NAMES[int(weekday) % 7]}\n"
        f"The day runs from {format_clock(DAY_TRIP_START_MINUTES)} to "
        f"{format_clock(DAY_TRIP_END_MINUTES)}.\n\n"
        f"Running order:\n{_slot_lines()}\n\n"
        f"Candidates:\n{_candidate_lines(pool)}"
    )
    try:
        client = Groq(api_key=groq_api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": DAY_TRIP_SYSTEM_PROMPT % {'language': language}},
                {"role": "user", "content": user_message},
            ],
            model=DAY_TRIP_MODEL,
            # A reasoning model shares this budget with its reasoning, so it needs real
            # headroom: too tight and it returns empty content with no error at all.
            max_completion_tokens=1500,
            reasoning_effort='low',
            temperature=0.2,
        )
        raw = chat_completion.choices[0].message.content
    except Exception as e:
        # There is no retry: the fallback is deterministic and instant, so a Groq 429 costs
        # the traveller a nicer narrative, not the plan.
        print(f"day trip planner unavailable: {e}")
        return None
    log_llm_usage('daytrip')
    return _parse_plan(raw, by_sid)


def _plan_day_trip_fallback(pool: dict) -> dict:
    """Best-scoring open candidate per slot, in slot order.

    This is what runs when Groq is down, rate-limited, returns empty content, or when there
    is no GROQ key at all - the mode must never depend on the LLM being reachable.
    """
    stops, used = [], set()
    for slot in DAY_TRIP_SLOTS:
        for candidate in pool.get(slot['key'], []):
            if candidate['place_id'] in used and not candidate.get('reuse'):
                continue
            if candidate['hours'] == 'closed':
                continue
            stops.append({'slot': slot['key'], 'place_id': candidate['place_id'],
                          'note': None, 'dwell': slot['dwell']})
            used.add(candidate['place_id'])
            break
    return {'title': None, 'closing': None, 'stops': stops}


def plan_day_trip(pool: dict, lang: str, weekday: int) -> dict:
    """Sequence the candidate pool into an itinerary.

    One LLM call per plan, cached in Redis on the candidate set - so a rerun of the same
    search (Streamlit reruns the whole script on every widget interaction) is free.
    """
    by_sid = {c['sid']: c for candidates in pool.values() for c in candidates}
    if not by_sid:
        return {'title': None, 'closing': None, 'stops': [], 'source': 'empty'}

    cache_key = _redis_key_for_plan([c['place_id'] for c in by_sid.values()], lang, weekday)
    cached = get_cached_plan(cache_key)
    if cached:
        log_llm_usage('daytrip_cache_hit')
        return dict(cached, source='cache')

    try:
        plan = _plan_day_trip_llm(pool, by_sid, lang, weekday)
    except Exception as e:
        # The boundary: nothing the planner does may take the page down, because the
        # fallback below is always available and always sufficient.
        print(f"day trip planner failed: {e}")
        plan = None

    if plan:
        cache_plan(cache_key, plan)
        return dict(plan, source='llm')
    return dict(_plan_day_trip_fallback(pool), source='fallback')


# ---------------------------------------------------------------------------
# One-day trip: the schedule
# ---------------------------------------------------------------------------

def _nearest_alternative(candidates: list, origin, used: set, current_leg: dict):
    """The closest unused candidate in the same slot, if any beats the current leg."""
    best = None
    for candidate in candidates:
        if candidate['place_id'] in used or candidate['hours'] == 'closed':
            continue
        leg = walk_leg(origin, (candidate['metadata']['lat'], candidate['metadata']['lng']))
        if not leg or leg['metres'] >= current_leg['metres']:
            continue
        if best is None or leg['metres'] < best[1]['metres']:
            best = (candidate, leg)
    return best


def schedule_stops(plan_stops: list, pool: dict, weekday: int) -> list:
    """Attach the clock, the walking leg and an opening-hours check to each stop.

    Times are computed here rather than asked of the LLM. A reasoning model at low effort
    gets arithmetic chains wrong, and a computed clock can never contradict the walking
    distances printed next to it. The day always starts at DAY_TRIP_START_MINUTES: the
    result is a running order, and a traveller who sets off an hour later reads it an hour
    later - which is cheaper than making every cache key carry a start time.
    """
    # Keyed on (slot, place) rather than place alone: a village meal may reuse the place its
    # twin slot took, and looking that up by place id would collapse the two entries and lose
    # whichever slot's 'reuse' flag decides it is allowed.
    by_place = {(c['slot'], c['place_id']): c for candidates in pool.values() for c in candidates}
    clock = DAY_TRIP_START_MINUTES
    previous = None
    used = set()
    scheduled = []

    for entry in plan_stops:
        candidate = by_place.get((entry.get('slot'), entry.get('place_id')))
        slot = slot_by_key(entry.get('slot'))
        # A plan can come from cache while the pool - or DAY_TRIP_SLOTS itself - has moved
        # on, so both ends are looked up rather than trusted. Renaming a slot key must
        # invalidate the stop, not raise on a week's worth of cached plans.
        if candidate is None or slot is None:
            continue
        if candidate['place_id'] in used and not candidate.get('reuse'):
            continue
        position = (candidate['metadata']['lat'], candidate['metadata']['lng'])
        leg = walk_leg(previous, position)

        note = entry.get('note')
        if leg and leg['metres'] > MAX_LEG_M and previous:
            nearer = _nearest_alternative(pool.get(entry.get('slot'), []), previous, used, leg)
            if nearer:
                candidate, leg = nearer
                position = (candidate['metadata']['lat'], candidate['metadata']['lng'])
                # The note was written about the place we just replaced - it names it, and
                # would caption a different restaurant. Code chose this one, so it goes out
                # unannotated, the same as a refilled meal or a filler park.
                note = None

        arrival = clock + (leg['minutes'] if leg else 0)
        # Clamped forward into the slot's window, never backwards: nobody has dinner at
        # 15:00, and a slot whose window has already passed is dropped rather than faked -
        # which is how a morning that overran quietly loses the green break instead of
        # pushing the whole evening past midnight.
        earliest, latest = slot.get('earliest'), slot.get('latest')
        if earliest is not None and arrival < earliest:
            arrival = earliest
        if latest is not None and arrival > latest:
            continue

        dwell = int(entry.get('dwell') or slot.get('dwell') or 60)
        open_at = is_open_at(candidate['metadata'].get('opening_periods'), weekday, arrival)
        scheduled.append({
            'slot': slot,
            'metadata': candidate['metadata'],
            'place_id': candidate['place_id'],
            'arrival': arrival,
            'depart': arrival + dwell,
            'dwell': dwell,
            'leg': leg,
            'note': note,
            'hours': candidate['hours'],
            # None (no published hours) is not a warning: most landmarks publish none.
            'closed_warning': open_at is False,
        })
        used.add(candidate['place_id'])
        clock = arrival + dwell
        previous = position

    return scheduled


# A day that lost its museum and its aperitivo has hours of nothing in it. The nature search
# has already been paid for and its unused candidates cost neither a call nor a token, so the
# spare ones fill the holes - a park is the one category that suits any hour and any gap.
DAY_TRIP_FILLER_SLOT = 'nature'
DAY_TRIP_GAP_MINUTES = 90        # dead time worth filling; below this the day just breathes
DAY_TRIP_MIN_FILLER_DWELL = 30   # shorter than this is a detour, not a stop
DAY_TRIP_MAX_FILLERS = 2         # three green breaks in a day is not a plan, it is padding


def _best_filler(spare: list, origin, destination, window: int, clock: int, weekday: int,
                 direct_m: int = 0):
    """The least-detour spare park that fits the slack and is open when the day gets there.

    Distance is judged as the *extra* walking the stop costs, not leg by leg: the traveller
    was going to walk `direct_m` between these two stops anyway, so a park just off that line
    is nearly free while one that doubles the walk is not. The walk in is separately bounded,
    because however short the detour reads on paper, nobody hikes 3 km to a filler.
    """
    dwell_cap = (slot_by_key(DAY_TRIP_FILLER_SLOT) or {}).get('dwell', 60)
    best = None
    for candidate in spare:
        position = (candidate['metadata']['lat'], candidate['metadata']['lng'])
        leg_in = walk_leg(origin, position)
        leg_out = walk_leg(position, destination)
        if leg_in and leg_in['metres'] > MAX_LEG_M:
            continue
        detour = sum(leg['metres'] for leg in (leg_in, leg_out) if leg) - direct_m
        if detour > MAX_LEG_M:
            continue
        travel = sum(leg['minutes'] for leg in (leg_in, leg_out) if leg)
        dwell = min(dwell_cap, window - travel)
        if dwell < DAY_TRIP_MIN_FILLER_DWELL:
            continue
        arrival = clock + (leg_in['minutes'] if leg_in else 0)
        if is_open_at(candidate['metadata'].get('opening_periods'), weekday, arrival) is False:
            continue
        if best is None or detour < best[0]:
            best = (detour, candidate, leg_in, leg_out, dwell)
    return best[1:] if best else None


def fill_gaps_with_nature(stops: list, pool: dict, weekday: int,
                          max_fillers: int = DAY_TRIP_MAX_FILLERS) -> list:
    """Put a spare park in the holes a thin day leaves.

    Fillers ignore the nature slot's own window - a park at 09:30 is perfectly good, and the
    windows exist to order a full day, not to forbid an empty morning - but never the opening
    hours. They only ever consume slack: every existing arrival stays exactly where
    `schedule_stops` put it, so nothing is pushed past the end of the day, and the stop after
    a filler simply has a shorter walk in.
    """
    slot = slot_by_key(DAY_TRIP_FILLER_SLOT)
    if not stops or slot is None:
        return stops

    used = {stop['place_id'] for stop in stops}
    spare = [c for c in pool.get(DAY_TRIP_FILLER_SLOT, [])
             if c['place_id'] not in used and c['hours'] != 'closed'
             and c['metadata'].get('lat') is not None]
    if not spare:
        return stops

    filled, added = [], 0
    clock, previous = DAY_TRIP_START_MINUTES, None
    for stop in stops:
        window = stop['arrival'] - clock
        pick = None
        if added < max_fillers and window >= DAY_TRIP_GAP_MINUTES:
            pick = _best_filler(spare, previous,
                                (stop['metadata']['lat'], stop['metadata']['lng']),
                                window, clock, weekday,
                                direct_m=stop['leg']['metres'] if stop['leg'] else 0)
        if pick:
            candidate, leg_in, leg_out, dwell = pick
            arrival = clock + (leg_in['minutes'] if leg_in else 0)
            filled.append({
                'slot': slot,
                'metadata': candidate['metadata'],
                'place_id': candidate['place_id'],
                'arrival': arrival,
                'depart': arrival + dwell,
                'dwell': dwell,
                'leg': leg_in,
                'note': None,
                'hours': candidate['hours'],
                'closed_warning': False,  # _best_filler only ever returns open candidates
                # Marks a stop the planner did not choose: the thin-day notice counts real
                # stops, so padding the day must not talk the app out of being honest.
                'filler': True,
            })
            spare = [c for c in spare if c['place_id'] != candidate['place_id']]
            added += 1
            stop = dict(stop, leg=leg_out)
        filled.append(stop)
        clock = stop['depart']
        previous = (stop['metadata']['lat'], stop['metadata']['lng'])

    return filled


# ---------------------------------------------------------------------------
# One-day trip: rendering
# ---------------------------------------------------------------------------

def create_trip_cards(stops: list, lang: str) -> str:
    """The itinerary as a timeline: slot and clock, the walk in from the previous stop, an
    opening-hours warning where one applies, and the same card the search results use."""
    closed_note = "⚠️ Potrebbe essere chiuso a quest'ora, controlla gli orari" if lang == 'it' \
        else "⚠️ It may be closed at this time, check the opening hours"
    stay_label = "min qui" if lang == 'it' else "min here"

    blocks = []
    previous = None
    for rank, stop in enumerate(stops, start=1):
        meta_bits = []
        if stop['leg']:
            meta_bits.append(format_leg(stop['leg'], lang))
        # Clamping a stop forward into its window can leave real dead time. Showing it beats
        # printing two times that silently do not add up.
        if previous is not None:
            gap = stop['arrival'] - previous['depart'] - (stop['leg']['minutes'] if stop['leg'] else 0)
            if gap >= 45:
                meta_bits.append(f"🕰️ {gap // 60}h{gap % 60:02d} libere prima" if lang == 'it'
                                 else f"🕰️ {gap // 60}h{gap % 60:02d} free before this")
        meta_bits.append(f"⏱️ {stop['dwell']} {stay_label}")
        if stop['closed_warning']:
            meta_bits.append(closed_note)

        note = f"<div class=\"trip-note\">{stop['note']}</div>" if stop.get('note') else ""
        blocks.append(_flatten_html(f"""
            <div class="trip-step">
                <div class="trip-heading">
                    {slot_label(stop['slot'], lang)} · <strong>{format_clock(stop['arrival'])}</strong>
                </div>
                <div class="trip-meta">{" · ".join(meta_bits)}</div>
                {note}
            </div>
        """) + "\n" + _card_html(stop['metadata'], rank))
        previous = stop
    return "\n".join(blocks)


# Degrees of longitude across the map at zoom 0, for a ~700px wide chart with a margin:
# 360 * 700 / (256 * 1.3). Deck.gl has no fitBounds from Python, so the zoom is derived.
ZOOM_FIT_DEGREES = 757.0


def day_trip_deck(stops: list, centre_lat: float, centre_lng: float, lang: str = 'en'):
    """Numbered pins in visiting order, plus the line joining them.

    pydeck ships with Streamlit and its default basemap needs no Mapbox token, so the map
    adds no dependency and no billable request - unlike the Static Maps or Embed APIs.
    """
    points = [{
        'lat': stop['metadata']['lat'],
        'lng': stop['metadata']['lng'],
        'number': str(rank),
        'name': stop['metadata']['name'],
        'when': format_clock(stop['arrival']),
        'slot': slot_label(stop['slot'], lang),
    } for rank, stop in enumerate(stops, start=1)
        if stop['metadata'].get('lat') is not None and stop['metadata'].get('lng') is not None]

    if not points:
        return None

    lats = [p['lat'] for p in points] + [centre_lat]
    lngs = [p['lng'] for p in points] + [centre_lng]
    # The itinerary's own extent is what matters here, not the search radius.
    span = max(max(lats) - min(lats),
               (max(lngs) - min(lngs)) * math.cos(math.radians(centre_lat)),
               0.002)

    layers = [
        pdk.Layer(
            'ScatterplotLayer',
            data=[{'lat': centre_lat, 'lng': centre_lng, 'name': '', 'number': '', 'slot': '',
                   'when': ''}],
            get_position='[lng, lat]',
            get_fill_color=[120, 120, 120, 160],
            radius_min_pixels=5, radius_max_pixels=7, pickable=False,
        ),
        pdk.Layer(
            'PathLayer',
            data=[{'path': [[p['lng'], p['lat']] for p in points]}],
            get_path='path',
            get_color=[255, 130, 40, 200],
            width_min_pixels=3, pickable=False,
        ),
        pdk.Layer(
            'ScatterplotLayer',
            data=points,
            get_position='[lng, lat]',
            get_fill_color=[214, 39, 40, 230],
            radius_min_pixels=13, radius_max_pixels=18, pickable=True,
        ),
        pdk.Layer(
            'TextLayer',
            data=points,
            get_position='[lng, lat]',
            get_text='number',
            get_size=13,
            get_color=[255, 255, 255],
            get_alignment_baseline="'center'",
            pickable=False,
        ),
    ]

    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=(max(lats) + min(lats)) / 2,
            longitude=(max(lngs) + min(lngs)) / 2,
            zoom=max(10.0, min(16.0, math.log2(ZOOM_FIT_DEGREES / span))),
        ),
        tooltip={'html': '<b>{number}. {name}</b><br/>{slot} · {when}'},
        map_style=None,
    )


def promptLLM(context: str, preferences: str, lang: str):
    client = Groq(
    api_key=groq_api_key,
    )
    if lang == 'en':
        chat_completion = client.chat.completions.create(
            messages=[
                {
                "role": "system",
                "content": """
                Welcome to Choosing: the advanced Restaurant Recommender System!
                Your goal is to craft tailored restaurant recommendations by aligning user preferences with restaurant reviews.

                You will read user <preferences> from a normal text and restaurant reviews <context> from a dictionary with this structure:
                {
                'restaurant1': ['review1','review2','review3',...],
                'restaurant2': ['review4','review5','review6',...],
                ...
                }

                Return your answer in a formatted and readable markdown and using max 260 words.
                Best of luck with your personalized suggestions!
                """
                },
                {
                "role": "user",
                "content": f"""
                Hello!
                Find the top restaurants based on reviews you will read in <context> considering my <preferences>.

                To produce your answer, follow these steps:
                1) read all restaurant reviews from <context> and COUNT the number of reviews that are specifically mentioning my <preferences>.
                2) if you don't find any relevant review (COUNT=0) just write this default message: Among the top 7 restaurants in the selected area, none seem to reflect your preferences. Please try another search.
                3) else
                    3.1) Count the number of relevant reviews per restaurant. More corresponding reviews suggest a higher likelihood that the restaurant is recommendable! Exclude restaurants with no relevant reviews.
                    3.2) Analyze the sentiment of the reviews to craft your recommendations. Give high priority to my <preferences>. Always remember that I am looking for tailored recommendations, not generic ones!
                    
                    Your answer should highlight:
                    - The restaurant name.
                    - A brief explanation of why you consider the restaurant a good fit for <preferences>.
                    - A list of specific dishes (single names only) found in reviews that potentially match <preferences> (leave empty if unsure).
                    - Your confidence level about your answer, in percentage.
                    Discard all the recommanded restaurants with a confidence level below 60%.

                <preferences>
                "{preferences}"
                </preferences>

                <context>
                {context}
                </context>
         
                """
                }
            ],
            model="openai/gpt-oss-120b",
            reasoning_effort='low',
            temperature=0.1,
            max_completion_tokens=768
        )
    else:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                "role": "system",
                "content": """
                Benvenuto in Choosing: l'avanzato sistema di raccomandazione per ristoranti!
                Il tuo obiettivo è di suggerire i migliori ristoranti agli utenti allineando le loro preferenze con le recensioni dei ristoranti.

                Leggerai le <preferenze> degli utenti da un normale testo e il <contesto> delle recensioni dei ristoranti da un dizionario con questa struttura:
                {
                'ristorante1': ['recensione1','recensione2','recensione3',...],
                'ristorante2': ['recensione4','recensione5','recensione6',...],
                ...
                }

                Restituisci in output la tua risposta in un formato markdown leggibile e chiaro, con lunghezza massima di 260 parole.
                Buona fortuna con i tuoi consigli!
                """
                },
                {
                "role": "user",
                "content": f"""
                Trova i ristoranti le cui recensioni siano allineate con queste mie preferenze:
                <preferenze>
                "{preferences}"
                </preferenze>

                Recensioni dei ristoranti:
                <contesto>
                {context}
                </contesto>

                Prova a ragionare seguendo questi passaggi:
                1) Per ogni ristorante in <contesto>, escludi tutte le recensioni che non hanno corrispondenze dirette con le mie <preferenze>.
                2) Conta il numero di recensioni rimanenti per ristorante. Più recensioni corrispondenti suggeriscono una più alta probabilità che quel ristorante sia da consigliare! Escludi i ristoranti senza recensioni rimanenti.
                3) Analizza il sentiment delle recensioni rimanenti per creare le tue raccomandazioni. Dai alta priorità alle mie <preferenze>. Ricordati sempre che sto cercando raccomandazioni personalizzate, non generiche!

                La tua risposta dovrà evidenziare:
                - Il nome del ristorante.
                - La spiegazione del posizionamento in classifica che hai assegnato a questo ristorante in funzione delle <preferenze>.
                - L'elenco dei piatti specifici (solo nomi singoli) trovati nelle recensioni che corrispondono alle <preferenze> (lascia vuoto se non sei sicuro).
                - Il tuo livello di confidenza riguardo la tua risposta, in percentuale.
                
                Se non c'è nessun ristorante in linea con le mie <preferenze>, rispondi solo con il seguente messaggio di default:
                - Tra i 7 migliori ristoranti della zona selezionata, nessuno sembra rispecchiare le tue <preferenze>. Prova un'altra ricerca.
                """
                }
            ],
            model="openai/gpt-oss-120b",
            temperature=0.1,
            max_completion_tokens=768,
            reasoning_effort='low'
        )
    return chat_completion.choices[0].message.content
