from config import maps_api_key
from module import *

import numpy as np
import requests
import re

SEARCH_NEARBY_URL = 'https://places.googleapis.com/v1/places:searchNearby'

# Places API (New) returns only the fields listed in X-Goog-FieldMask, so every field the
# cards need is requested here and arrives with the search itself - no per-place Details
# call. 'reviews' is added only when the LLM path needs it, because it moves the request
# from the Nearby Search Enterprise SKU to the pricier Enterprise + Atmosphere one.
BASE_FIELDS = [
    'places.id',
    'places.displayName',
    'places.location',
    'places.shortFormattedAddress',
    'places.rating',
    'places.userRatingCount',
    'places.priceLevel',
    'places.googleMapsUri',
    'places.websiteUri',
    'places.internationalPhoneNumber',
    'places.currentOpeningHours',
    'places.accessibilityOptions',
]

MAX_RESULTS = 20
TOP_N = 7
MIN_SCORE = 12
SCORE_CAP = 20

# The floor for a thin area. Because the score is `rating * ln(sqrt(n))`, lowering it trades
# fame for quality rather than quality for nothing: 12 -> 10 admits 4.8 stars from 65 reviews
# instead of 149, and 4.5 from 86 instead of 208, while a 3-star place still needs ~786
# reviews to appear at all. It keeps out the 1- and 3-review entries that a blanket
# relaxation would have let in.
#
# A day-trip search uses it outright - it needs several candidates per slot. An ordinary
# search only drops to it when MIN_SCORE left SPARSE_RESULTS or fewer places on the page,
# which is the case where a nearly empty result is the worse answer.
SPARSE_MIN_SCORE = 10
SPARSE_RESULTS = 2


def _remove_special_chars(text: str) -> str:
    """Strip the narrow (u202f) and thin (u2009) spaces Google puts in opening hours."""
    return re.sub(r'[  ]', '', text)


class Choosing():

    def __init__(self, call_id: str, radius: float, keyword: str, lang: str, coordinates: list,
                 with_reviews: bool = False, min_score: float = MIN_SCORE):
        self.maps_api_key = maps_api_key
        self.call_id = call_id
        self.radius = radius
        self.keyword = normalize_category(keyword)
        self.lang = lang
        self.coordinates = coordinates
        self.with_reviews = with_reviews
        # The day-trip pool passes SPARSE_MIN_SCORE outright; every other search starts at
        # MIN_SCORE and drops to it only when the page comes back all but empty. See
        # first_seven_best_suggestions for why a thin area needs the lower one.
        self.min_score = min_score
        self.places_by_id = {}
        self.first_seven_best_suggestions()

    def _field_mask(self) -> str:
        fields = list(BASE_FIELDS)
        if self.with_reviews:
            fields.append('places.reviews')
        return ','.join(fields)

    def _search_nearby(self) -> list:
        """One call to Places API (New). Returns the raw list of place objects."""
        category = CATEGORIES[self.keyword]

        body = {
            'includedPrimaryTypes': category['types'],
            'maxResultCount': MAX_RESULTS,
            'languageCode': self.lang,
            'locationRestriction': {
                'circle': {
                    'center': {'latitude': self.coordinates[0], 'longitude': self.coordinates[1]},
                    # A circle here is a hard restriction, so the radius slider stays exact.
                    'radius': float(self.radius),
                }
            },
        }
        # Keeps chains out of a broad "restaurants nearby" search. Server-side and
        # language-independent, unlike matching names against 'Donald'.
        if category.get('exclude'):
            body['excludedPrimaryTypes'] = category['exclude']

        cached = get_cached_search(body, self.with_reviews)
        if cached is not None:
            return cached

        resp = requests.post(
            SEARCH_NEARBY_URL,
            headers={
                'X-Goog-Api-Key': str(self.maps_api_key),
                'X-Goog-FieldMask': self._field_mask(),
                'Content-Type': 'application/json',
            },
            json=body,
            timeout=15,
        )
        jj = resp.json()
        if resp.status_code != 200:
            raise PlacesApiError(jj.get('error', {}).get('message', 'Places API request failed'))

        places = jj.get('places', [])
        cache_search(body, self.with_reviews, places)
        log_places_usage(self.keyword, self.with_reviews)
        return places

    def _metadata_from_place(self, place: dict) -> dict:
        """Flatten one Places API (New) place into the dict shape the cards expect."""
        location = place.get('location', {})

        hours = place.get('currentOpeningHours', {})
        opening = hours.get('weekdayDescriptions', None)
        if opening:
            opening_time = "<br>".join(_remove_special_chars(s) for s in opening)
        else:
            opening_time = None

        return {
            'name': place.get('displayName', {}).get('text', None),
            'lat': location.get('latitude', None),
            'lng': location.get('longitude', None),
            'rating': place.get('rating', None),
            'n_rating': place.get('userRatingCount', None),
            'price_level': place.get('priceLevel', None),
            'vicinity': place.get('shortFormattedAddress', None),
            'google_url': place.get('googleMapsUri', None),
            'website': place.get('websiteUri', None),
            'phone_number': place.get('internationalPhoneNumber', None),
            'opening_time': opening_time,
            # 'currentOpeningHours' also carries structured periods next to the localised
            # weekdayDescriptions above. The day-trip planner needs machine-readable windows,
            # and keeping these costs nothing: same field mask, same call, same SKU. Parsing
            # the localised strings instead would break in every language.
            'opening_periods': hours.get('periods', None),
            'open_now': hours.get('openNow', None),
            'accessible': place.get('accessibilityOptions', {}).get('wheelchairAccessibleEntrance', None),
            'category': self.keyword,
            'score': None,
        }

    @staticmethod
    def _reviews_from_place(place: dict) -> list:
        """Reviews nest one level deeper than in the legacy API: reviews[].text.text"""
        extracted = []
        for r in place.get('reviews', []):
            language = r.get('originalText', {}).get('languageCode') or r.get('languageCode')
            if not language:
                continue
            text = r.get('text', {}).get('text', '') or ''
            author = r.get('authorAttribution', {}).get('displayName', '')
            extracted.append({
                'id': str(author).replace(' ', '').lower() + str(r.get('publishTime', '')),
                'language': language,
                'text': text.replace('\n', '').replace('\\', ''),
                'time': r.get('publishTime', ''),
            })
        return extracted

    def first_seven_best_suggestions(self) -> dict:
        """The top seven, best score first. Unrated places only when nothing is rated.

        `MIN_SCORE` reads like a quality floor but is really a review-count floor: since the
        score is `rating * ln(sqrt(n))`, clearing 12 needs ~208 reviews at 4.5 stars and ~404
        at 4.0. That is the right filter in a city, where the alternative is junk in the top
        7. In a small town it empties whole categories - Castelluccio has a 4.8-star viewpoint
        with 75 reviews and nothing else, and the floor threw it away along with the rest.

        The floor is therefore lowered in a thin area rather than removed. Because the score
        multiplies the rating by the weight of evidence behind it, a lower floor admits
        places that are good but not famous, not places that are bad: in Castelluccio
        SPARSE_MIN_SCORE recovers the 4.8-star viewpoint (75 reviews, 10.4) and the 4.4-star
        trattoria (95 reviews, 10.0), while the 5-star-from-1-review and 4-star-from-3-reviews
        entries stay out at 0.0 and 2.2. Nothing is ever admitted just to fill the page - a
        missing suggestion is recoverable, a bad one is not.

        Two ways in: a day-trip search passes `min_score` outright, and any search that comes
        back with SPARSE_RESULTS or fewer places retries at the lower floor. The retry is
        free - same response, same SKU, no second call - and cannot reorder a healthy result,
        because a page that already had three or more places never reaches it.
        """
        places = self._search_nearby()

        entries = []
        for place in places:
            place_id = place.get('id')
            if not place_id:
                continue

            metadata = self._metadata_from_place(place)
            rating = metadata['rating']
            n_rating = metadata['n_rating']

            if rating is None or not n_rating:
                metadata['rating'] = "❔"
                metadata['n_rating'] = "❔"
                metadata['score'] = None
                raw_score = None
            else:
                raw_score = rating * np.log(0.001 + np.sqrt(n_rating))
                try:
                    metadata['score'] = int(round(min(raw_score, SCORE_CAP) / SCORE_CAP * 100))
                except ValueError:
                    metadata['score'] = 0

            self.places_by_id[place_id] = {
                'metadata': metadata,
                'reviews': self._reviews_from_place(place),
            }
            entries.append({'place_id': place_id, 'score': metadata['score'],
                            'raw': raw_score})

        # Ranked on the *rounded* score, and `sorted` is stable, so the ~10k-review places
        # that all saturate at 100 stay in the order Google returned them. Ranking on the
        # raw float instead would reshuffle the top 7 of every city search.
        def above(floor):
            return sorted((e for e in entries
                           if e['raw'] is not None and e['raw'] >= floor),
                          key=lambda e: e['score'], reverse=True)[:TOP_N]

        unrated = [e for e in entries if e['raw'] is None]  # in the order Google ranked them

        possibilities = above(self.min_score)
        if len(possibilities) <= SPARSE_RESULTS and self.min_score > SPARSE_MIN_SCORE:
            # Two suggestions is not a page. Retrying the same response at the lower floor
            # is free, and everything it adds was already good enough to be worth showing.
            possibilities = above(SPARSE_MIN_SCORE)
        if not possibilities:
            # Unrated places are all-or-nothing: one place above the floor hides every '❔'
            # one. Unchanged from before the floor became a parameter.
            possibilities = unrated[:TOP_N]

        kept = {entry['place_id'] for entry in possibilities}
        self.places_by_id = {k: v for k, v in self.places_by_id.items() if k in kept}

        self.formatted_df_to_dict = {
            entry['place_id']: self.places_by_id[entry['place_id']]['metadata']
            for entry in possibilities
        }
        return self.formatted_df_to_dict

    def get_metadata_and_reviews(self, place_id: str) -> tuple:
        """Reads from the single search response - no HTTP call, so cards are free."""
        entry = self.places_by_id[place_id]
        return entry['metadata'], entry['reviews']

    def build_dataset(self):
        dataset = dict()
        for place_id in self.formatted_df_to_dict.keys():
            metadata, reviews = self.get_metadata_and_reviews(place_id)
            restaurant_name = metadata['name']
            formatted_reviews = [r['text'] for r in reviews]
            dataset[restaurant_name] = formatted_reviews
        return dataset


def build_day_trip_pool(radius: float, lang: str, coordinates: list, weekday: int,
                        per_slot: int = DAY_TRIP_MAX_CANDIDATES) -> dict:
    """Candidates for every slot of a day trip, keyed by slot.

    Cost is one Nearby Search per *distinct* category - 7 for the nine slots of a day, all
    served by the 30-day search cache on a repeat. Two slots sharing a category
    ('landmarks', 'restaurants') are filled from that one search and given interleaved,
    disjoint slices, so neither slot gets the leftovers and no place can fill both. That
    replaces the ad-hoc `.remove()` calls the old inline version used.

    A place that publishes hours and is shut on `weekday` never enters the pool. Asking the
    model not to pick it was the old defence, and a model's compliance is not a guarantee;
    dropping it here also spends the per-slot budget on places the traveller can enter.
    Unknown hours are NOT a closure - most landmarks and parks publish none.

    A category that returns nothing leaves its slots empty rather than failing the plan:
    a small town with one landmark should still get an itinerary. For the same reason the
    searches use SPARSE_MIN_SCORE rather than MIN_SCORE, and a meal slot left empty by the
    split may reuse the place its twin took - one trattoria in the village is lunch *and*
    dinner, which beats no dinner. Neither lowers the bar on quality: an unfillable slot is
    left unfilled, and `main.py` says so.
    """
    slots = day_trip_slots()

    searched = {}
    for category in day_trip_categories():
        searched[category] = list(
            Choosing('trip', radius, category, lang, coordinates,
                     min_score=SPARSE_MIN_SCORE).formatted_df_to_dict.items()
        )

    def usable(items, letter, slot, reuse=False):
        candidates = []
        for place_id, metadata in items:
            if metadata.get('lat') is None or metadata.get('lng') is None:
                continue  # the whole feature is geographic; a stop with no position is useless
            window = hours_window(metadata.get('opening_periods'), weekday)
            if window == 'closed':
                continue
            candidates.append({
                # A short synthetic id keeps the prompt small: 27-char place ids across ~28
                # candidates would cost more tokens than the rest of the payload.
                'sid': f"{letter}{len(candidates) + 1}",
                'place_id': place_id,
                'slot': slot['key'],
                'metadata': metadata,
                'hours': window,
                'dist_m': int(round(haversine_m(coordinates[0], coordinates[1],
                                                metadata['lat'], metadata['lng']))),
                # Set only on the scarcity path below, and the only thing that lets a place
                # appear twice in one day - the planner and the scheduler both dedupe on it.
                'reuse': reuse,
            })
            if len(candidates) >= per_slot:
                break
        return candidates

    pool = {}
    for index, slot in enumerate(slots):
        sharing = [s for s in slots if s['category'] == slot['category']]
        stride, offset = len(sharing), sharing.index(slot)
        letter = chr(ord('A') + index)
        found = searched.get(slot['category'], [])

        candidates = usable(found[offset::stride], letter, slot)
        if not candidates and slot.get('essential') and found:
            # The village case: fewer places than slots sharing the category, so the split
            # gave this meal nothing. Repeating the one restaurant is a worse day than two
            # different ones and a much better day than skipping dinner.
            candidates = usable(found, letter, slot, reuse=True)
        pool[slot['key']] = candidates

    return pool
