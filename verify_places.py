"""Regression checks for the Places API (New) integration.

Run with:  python verify_places.py

These hit the live Places API, so each run costs a handful of calls against the monthly
free tier. Run it after touching CATEGORIES, the field mask, or the response mapping.

The checks that matter most and why:

  * language bias - searching the Italian word "ristorante" abroad returns Italian
    restaurants (~95% in Paris). Category types are language-independent and return local
    places instead (~10%). This is the whole reason categories are types and never text,
    so the differential is asserted rather than assumed.
  * type hierarchy - primary types have parents: 'bar' is a parent of 'pub', and
    'dessert_shop' is a parent of 'ice_cream_shop'. Adding either to a group silently
    merges two categories, so 'aperitivo' and 'pastry' are checked for leakage.
  * type validity - an invalid type name is not an error, it just returns nothing. Every
    type in CATEGORIES is queried individually so a typo fails loudly here.
  * autocomplete SKU - resolving a picked address asks Place Details for 'location' and
    'formattedAddress' only, which keeps it in the Essentials tier (10,000 free/month).
    Adding one Enterprise field there would move it to a 1,000/month allowance, so the
    mask is asserted rather than trusted.
  * day-trip cost - a plan is one Nearby Search per distinct category (7 for nine slots),
    never one per slot, and the structured opening periods it schedules against must keep
    arriving with the search rather than needing a call of their own.
  * day-trip frame - the day is fixed at 09:30-23:30, and the slot windows are the only
    thing holding that end. `latest + dwell` per slot is checked without spending a call.
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import choosing  # noqa: E402
import module  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
API_KEY = os.getenv('GOOGLE_MAPS')

ROME = [41.9028, 12.4964]
PARIS = [48.8566, 2.3522]
ITALIAN_CUISINE = {'italian_restaurant', 'pizza_restaurant'}

failures = []


def check(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + (f'   {detail}' if detail else ''))
    if not ok:
        failures.append(name)


def _raw_search(payload, endpoint='searchNearby', fields='places.displayName,places.primaryType'):
    resp = requests.post(
        f'https://places.googleapis.com/v1/places:{endpoint}',
        headers={'X-Goog-Api-Key': API_KEY, 'X-Goog-FieldMask': fields,
                 'Content-Type': 'application/json'},
        json=payload, timeout=15,
    )
    return resp.status_code, resp.json()


def test_every_type_is_valid():
    print('\nevery type in CATEGORIES resolves')
    all_types = sorted({t for c in module.CATEGORIES.values() for t in c['types']})
    invalid = []
    for place_type in all_types:
        code, body = _raw_search({
            'includedPrimaryTypes': [place_type], 'maxResultCount': 1, 'languageCode': 'it',
            'locationRestriction': {'circle': {
                'center': {'latitude': ROME[0], 'longitude': ROME[1]}, 'radius': 3000.0}},
        })
        if code != 200:
            invalid.append((place_type, body.get('error', {}).get('message', '')[:80]))
    check(f'{len(all_types)} types valid', not invalid, str(invalid) if invalid else '')


def test_every_category_returns_results():
    print('\nevery category returns results in Rome and Paris')
    for key in module.CATEGORIES:
        counts = []
        for label, coords in (('Rome', ROME), ('Paris', PARIS)):
            instance = choosing.Choosing('verify', 3000, key, 'it', coords)
            counts.append(len(instance.formatted_df_to_dict))
        check(f'{key}', all(c > 0 for c in counts), f'rome={counts[0]} paris={counts[1]}')


def test_no_language_bias():
    """Free text carries cuisine bias; category types do not. Assert the gap."""
    print('\nlanguage bias: free text vs category types, Paris')
    centre = {'latitude': PARIS[0], 'longitude': PARIS[1]}

    _, text_body = _raw_search({
        'textQuery': 'ristorante', 'languageCode': 'it', 'pageSize': 20,
        'locationBias': {'circle': {'center': centre, 'radius': 1500.0}},
    }, endpoint='searchText')
    _, type_body = _raw_search({
        'includedPrimaryTypes': module.CATEGORIES['restaurants']['types'],
        'excludedPrimaryTypes': module.CATEGORIES['restaurants']['exclude'],
        'maxResultCount': 20, 'languageCode': 'it',
        'locationRestriction': {'circle': {'center': centre, 'radius': 1500.0}},
    })

    def italian_share(body):
        places = body.get('places', [])
        if not places:
            return 1.0
        return sum(1 for p in places if p.get('primaryType') in ITALIAN_CUISINE) / len(places)

    free_text = italian_share(text_body)
    by_type = italian_share(type_body)
    check('category types carry less cuisine bias than free text', by_type < free_text,
          f'free text {free_text:.0%} vs types {by_type:.0%}')


def test_category_hierarchy_leaks():
    print('\ntype hierarchy does not merge categories')
    _, body = _raw_search({
        'includedPrimaryTypes': module.CATEGORIES['aperitivo']['types'],
        'maxResultCount': 20, 'languageCode': 'it',
        'locationRestriction': {'circle': {
            'center': {'latitude': ROME[0], 'longitude': ROME[1]}, 'radius': 2000.0}},
    })
    pubs = [p['displayName']['text'] for p in body.get('places', [])
            if p.get('primaryType') in ('pub', 'irish_pub', 'sports_bar')]
    check('aperitivo excludes pubs', not pubs, str(pubs[:3]) if pubs else '')

    _, body = _raw_search({
        'includedPrimaryTypes': module.CATEGORIES['pastry']['types'],
        'maxResultCount': 20, 'languageCode': 'it',
        'locationRestriction': {'circle': {
            'center': {'latitude': ROME[0], 'longitude': ROME[1]}, 'radius': 2000.0}},
    })
    gelato = [p['displayName']['text'] for p in body.get('places', [])
              if p.get('primaryType') == 'ice_cream_shop']
    check('pastry excludes gelaterie', not gelato, str(gelato[:3]) if gelato else '')


def test_field_mapping():
    print('\nresponse maps onto the card fields')
    instance = choosing.Choosing('verify', 1000, 'restaurants', 'it', ROME)
    ids = list(instance.formatted_df_to_dict.keys())
    check('results returned', bool(ids), f'n={len(ids)}')
    metadata, _ = instance.get_metadata_and_reviews(ids[0])
    for field in ('name', 'lat', 'lng', 'rating', 'n_rating', 'price_level', 'vicinity',
                  'google_url', 'website', 'phone_number', 'opening_time', 'opening_periods',
                  'open_now', 'accessible', 'score'):
        check(f'field {field}', field in metadata)
    check('price level is an enum string',
          any(str(instance.get_metadata_and_reviews(i)[0]['price_level']).startswith('PRICE_LEVEL')
              for i in ids))


def test_reviews_only_when_requested():
    """Reviews move the call to the pricier SKU, so they must be opt-in."""
    print('\nreviews are opt-in')
    lean = choosing.Choosing('verify', 1000, 'restaurants', 'it', ROME, with_reviews=False)
    rich = choosing.Choosing('verify', 1000, 'restaurants', 'it', ROME, with_reviews=True)
    lean_count = sum(len(lean.get_metadata_and_reviews(i)[1]) for i in lean.formatted_df_to_dict)
    rich_count = sum(len(rich.get_metadata_and_reviews(i)[1]) for i in rich.formatted_df_to_dict)
    check('lean mask carries no reviews', lean_count == 0, f'{lean_count}')
    check('rich mask carries reviews', rich_count > 0, f'{rich_count}')
    check('build_dataset yields review text', any(rich.build_dataset().values()))


def test_one_call_per_search():
    """The point of the migration: cards must not trigger per-place requests."""
    print('\none HTTP call per search')
    calls = []
    original_post = requests.post
    # The cache is bypassed so the count reflects the code path, not whether this exact
    # search happens to be warm in Redis.
    original_cache = choosing.get_cached_search

    def counting(*args, **kwargs):
        calls.append(1)
        return original_post(*args, **kwargs)

    requests.post = counting
    choosing.get_cached_search = lambda *args, **kwargs: None
    try:
        instance = choosing.Choosing('verify', 1500, 'gelato', 'it', ROME)
        module.create_cards(list(instance.formatted_df_to_dict.keys()), instance)
    finally:
        requests.post = original_post
        choosing.get_cached_search = original_cache
    check('exactly 1 request for search plus all cards', len(calls) == 1, f'n={len(calls)}')


def test_cache_prevents_repeat_calls():
    print('\nRedis cache serves a repeated search')
    calls = []
    original_post = requests.post

    def counting(*args, **kwargs):
        calls.append(1)
        return original_post(*args, **kwargs)

    choosing.Choosing('verify', 1700, 'nature', 'it', ROME)  # warm the cache
    requests.post = counting
    try:
        choosing.Choosing('verify', 1700, 'nature', 'it', ROME)
    finally:
        requests.post = original_post
    check('second identical search makes no request', len(calls) == 0, f'n={len(calls)}')


def test_non_food_cards_degrade():
    print('\nnon-food cards omit rows they have no data for')
    instance = choosing.Choosing('verify', 2000, 'worship', 'it', ROME)
    html = module.create_cards(list(instance.formatted_df_to_dict.keys()), instance)
    check('cards rendered', html.count('restaurant-card') == len(instance.formatted_df_to_dict))
    check('no price row', 'Price level' not in html)
    check('no placeholder question marks', '❔' not in html)


def test_legacy_keyword_aliases():
    print('\nlegacy ?keyword= values still resolve')
    for old, expected in (('cocktail', 'aperitivo'), ('point+of+interest', 'landmarks'),
                          ('restaurants', 'restaurants'), ('museum', 'museum'),
                          ('pizzeria', 'pizzeria'), ('nonsense', 'restaurants')):
        got = module.normalize_category(old)
        check(f'{old} -> {expected}', got == expected, f'got {got}')


def test_autocomplete_predictions():
    print('\naddress autocomplete returns resolvable predictions')
    preds = module.autocomplete_address('piazza del colosseo ro', 'it')
    check('predictions returned', bool(preds), f'n={len(preds)}')
    check('every prediction is (label, place_id)',
          all(isinstance(p, tuple) and len(p) == 2 and all(p) for p in preds))

    # Every keystroke would otherwise be a billable request.
    check('prefix below the minimum is never sent',
          module.autocomplete_address('co', 'it') == [])
    check('empty input is never sent', module.autocomplete_address('', 'it') == [])

    english = module.autocomplete_address('eiffel tower', 'en')
    check('works in english too', bool(english), f'n={len(english)}')


def test_autocomplete_resolves_to_coordinates():
    print('\na picked prediction resolves by place id')
    preds = module.autocomplete_address('colosseo roma', 'it')
    frame, address = module.resolve_place(preds[0][1], 'it')
    lat, lon = frame.values[0]
    check('frame has the lat/lon columns the map and Choosing expect',
          list(frame.columns) == ['lat', 'lon'])
    # The Colosseum, so a generous box still proves it resolved to the right city.
    check('coordinates land on the picked place', 41.87 < lat < 41.91 and 12.47 < lon < 12.51,
          f'{lat:.4f},{lon:.4f}')
    check('formatted address returned', bool(address), address[:40])

    try:
        module.resolve_place('ChIJ_not_a_real_place_id', 'it')
        check('invalid place id raises', False, 'no exception')
    except module.BadAddressError:
        # The API answers 400 for a bad id rather than an empty body, so this is loud.
        check('invalid place id raises BadAddressError', True)


def test_autocomplete_details_stay_on_essentials():
    """Resolving a pick must not drag in an Enterprise field and burn the 1,000 free tier."""
    print('\nplace-details mask stays in the Essentials SKU')
    mask = module.DETAILS_LOCATION_FIELDS
    pricier = ['rating', 'userRatingCount', 'priceLevel', 'reviews', 'currentOpeningHours',
               'internationalPhoneNumber', 'websiteUri', 'accessibilityOptions']
    leaked = [f for f in pricier if f in mask]
    check('mask holds no Pro/Enterprise/Atmosphere field', not leaked, str(leaked) if leaked else mask)


def test_autocomplete_cache_prevents_repeat_calls():
    print('\nautocomplete caches each prefix')
    calls = []
    original_post = requests.post

    def counting(*args, **kwargs):
        calls.append(1)
        return original_post(*args, **kwargs)

    module.autocomplete_address('trastevere roma', 'it')  # warm the cache
    module.requests.post = counting
    try:
        module.autocomplete_address('trastevere roma', 'it')
    finally:
        module.requests.post = original_post
    check('repeated prefix makes no request', len(calls) == 0, f'n={len(calls)}')


def test_opening_periods_present():
    """The day-trip planner needs machine-readable hours, and they must come free.

    'currentOpeningHours' was already in the field mask for the weekdayDescriptions the
    cards print; the same object carries structured periods. If Google ever stopped
    returning them the planner would silently treat every place as 'hours unknown', so the
    presence of open.day/open.hour is asserted rather than assumed.
    """
    print('\nstructured opening periods arrive with the search')
    instance = choosing.Choosing('verify', 1000, 'restaurants', 'it', ROME)
    periods = [m.get('opening_periods') for m in instance.formatted_df_to_dict.values()]
    with_periods = [p for p in periods if p]
    check('some places carry periods', bool(with_periods), f'{len(with_periods)}/{len(periods)}')
    if with_periods:
        first = with_periods[0][0]
        check('period has open.day and open.hour',
              'day' in first.get('open', {}) and 'hour' in first.get('open', {}), str(first))
        # A window the planner can print and reason about, in any language.
        windows = [module.hours_window(p, 1) for p in with_periods]
        check('periods resolve to a readable window',
              any(w and w not in ('closed',) for w in windows), str(windows[:3]))


def test_always_open_places_are_open_every_day():
    """Pure check, no API: a 24/7 place must not read as closed six days out of seven.

    `currentOpeningHours` does not describe an always-open place as an open with no close -
    that is `regularOpeningHours`. It sends one truncated period covering the current week,
    open today 00:00 and closing the day before, next week, at 23:59. Matched by the start
    day alone, that span belongs to exactly one weekday and `hours_window` called every other
    day 'closed', which is how `build_day_trip_pool` came to drop every park around Carpegna
    and every piazza in Rome from any plan not dated to a Saturday.
    """
    print('\nan always-open place is open on every day of the week')

    # The exact shape Google returns, verbatim from a Carpegna 'nature' search.
    truncated = [{'open': {'day': 6, 'hour': 0, 'minute': 0, 'truncated': True},
                  'close': {'day': 5, 'hour': 23, 'minute': 59, 'truncated': True}}]
    windows = {d: module.hours_window(truncated, d) for d in range(7)}
    check('open on all seven days', all(w == '00:00-24:00' for w in windows.values()),
          str(windows))
    check('and open at any hour of them',
          all(module.is_open_at(truncated, d, h * 60) is True
              for d in range(7) for h in (0, 9, 14, 23)))

    # The documented no-close form must keep working, and a real closure must survive.
    no_close = [{'open': {'day': 0, 'hour': 0, 'minute': 0}}]
    check('the documented always-open form still reads as open',
          all(module.hours_window(no_close, d) == '00:00-24:00' for d in range(7)))

    monday_only = [{'open': {'day': 1, 'hour': 9}, 'close': {'day': 1, 'hour': 19}}]
    check('a place shut on Tuesday is still shut on Tuesday',
          module.hours_window(monday_only, 2) == 'closed'
          and module.hours_window(monday_only, 1) == '09:00-19:00')
    # Six days and change is a genuine weekly closure, not the truncated-week encoding.
    almost = [{'open': {'day': 0, 'hour': 6}, 'close': {'day': 6, 'hour': 22}}]
    check('a long-but-real window is not promoted to always-open',
          module.hours_window(almost, 3) == 'closed', str(module.hours_window(almost, 3)))


def test_day_trip_pool_one_call_per_category():
    """A plan costs one Nearby Search per distinct category - never one per slot."""
    print('\nday-trip pool makes one call per distinct category')
    calls = []
    original_post = requests.post
    original_cache = choosing.get_cached_search

    def counting(*args, **kwargs):
        calls.append(1)
        return original_post(*args, **kwargs)

    requests.post = counting
    choosing.get_cached_search = lambda *args, **kwargs: None
    try:
        pool = choosing.build_day_trip_pool(2000, 'it', ROME, weekday=1)
    finally:
        requests.post = original_post
        choosing.get_cached_search = original_cache

    expected = len(module.day_trip_categories())
    check(f'{expected} categories -> {expected} requests', len(calls) == expected, f'n={len(calls)}')
    check('every slot present in the pool',
          set(pool) == {s['key'] for s in module.day_trip_slots()})
    # Two landmark slots and two restaurant slots share their searches, so the nine slots of
    # a day still come from 7 calls. This is what keeps a richer plan from costing more.
    check('a day serves 9 slots from 7 calls',
          len(module.day_trip_slots()) == 9 and len(module.day_trip_categories()) == 7,
          f'{len(module.day_trip_slots())} slots, {len(module.day_trip_categories())} categories')


def test_day_trip_pool_slots_disjoint():
    """Slots sharing a category must not offer the same place - the old code deduped by hand."""
    print('\nday-trip slots never share a place')
    pool = choosing.build_day_trip_pool(2000, 'it', ROME, weekday=1)
    seen = {}
    clashes = []
    for slot_key, candidates in pool.items():
        for candidate in candidates:
            if candidate['place_id'] in seen:
                clashes.append((candidate['metadata']['name'], seen[candidate['place_id']], slot_key))
            seen[candidate['place_id']] = slot_key
    check('no place appears in two slots', not clashes, str(clashes[:3]) if clashes else '')

    shared = [s['key'] for s in module.DAY_TRIP_SLOTS if s['category'] == 'landmarks']
    check('both landmark slots got candidates',
          all(pool.get(k) for k in shared),
          str({k: len(pool.get(k, [])) for k in shared}))
    check('every candidate has coordinates and a short id',
          all(c['metadata']['lat'] is not None and c['sid'] for cs in pool.values() for c in cs))
    check('candidates capped per slot',
          all(len(cs) <= module.DAY_TRIP_MAX_CANDIDATES for cs in pool.values()),
          str({k: len(v) for k, v in pool.items()}))
    # A place shut on the planned day never reaches the model: the prompt asked it to skip
    # them, and a request is not a guarantee.
    check('no candidate is closed on the planned day',
          all(c['hours'] != 'closed' for cs in pool.values() for c in cs))


def test_day_trip_plan_survives_without_llm():
    """The plan must not depend on Groq being reachable."""
    print('\nday-trip plan falls back when the LLM fails')
    pool = choosing.build_day_trip_pool(2000, 'it', ROME, weekday=1)

    original_llm = module._plan_day_trip_llm
    original_cached = module.get_cached_plan
    module.get_cached_plan = lambda *a, **k: None  # a warm cache would hide the fallback
    try:
        for label, stub in (('empty content', lambda *a, **k: None),
                            ('an exception', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('429')))):
            module._plan_day_trip_llm = stub
            plan = module.plan_day_trip(pool, 'it', 1)
            stops = module.schedule_stops(plan['stops'], pool, 1)
            check(f'{label} still yields a schedule', bool(stops),
                  f"source={plan['source']} stops={len(stops)}")
            check(f'{label} times move forward',
                  all(b['arrival'] >= a['depart'] - 1 for a, b in zip(stops, stops[1:])))
            # The frame is fixed, so it is checkable: the day opens at 09:30 and nothing
            # can be scheduled past 23:30, however many slots survived the clamping.
            check(f'{label} starts the day at 09:30',
                  stops[0]['arrival'] == module.DAY_TRIP_START_MINUTES,
                  module.format_clock(stops[0]['arrival']))
            check(f'{label} ends within the day',
                  stops[-1]['depart'] <= module.DAY_TRIP_END_MINUTES,
                  module.format_clock(stops[-1]['depart']))
    finally:
        module._plan_day_trip_llm = original_llm
        module.get_cached_plan = original_cached


def test_day_trip_meals_are_never_dropped():
    """Pure check, no API: a model answer missing a meal is repaired, not published.

    Asked to keep the day tight, the model really does return Rome itineraries with no
    dinner in them - so the prompt asks, and `_parse_plan` enforces.
    """
    print('\nday-trip meals survive a model that skips them')
    by_sid = {}
    for index, slot in enumerate(module.DAY_TRIP_SLOTS):
        for rank in range(2):
            sid = f'{chr(ord("A") + index)}{rank + 1}'
            by_sid[sid] = {'sid': sid, 'slot': slot['key'], 'place_id': f'{sid}-place',
                           'hours': None, 'dist_m': 100 * rank,
                           'metadata': {'name': sid, 'lat': 41.9, 'lng': 12.5}}

    # Everything but the meals, which is the shape the model actually returned.
    kept = [s['key'] for s in module.DAY_TRIP_SLOTS if not s.get('essential')]
    raw = json.dumps({'title': 'x', 'closing': 'y', 'stops': [
        {'id': sid, 'note': 'n'} for sid, c in by_sid.items()
        if c['slot'] in kept and sid.endswith('1')]})

    plan = module._parse_plan(raw, by_sid)
    meals = {s['key'] for s in module.DAY_TRIP_SLOTS if s.get('essential')}
    planned = [s['slot'] for s in plan['stops']]
    check('every meal is back in the plan', meals <= set(planned), str(planned))
    check('the meals it added carry no invented note',
          all(s['note'] is None for s in plan['stops'] if s['slot'] in meals))
    check('no place is used twice',
          len({s['place_id'] for s in plan['stops']}) == len(plan['stops']))
    order = [s['key'] for s in module.DAY_TRIP_SLOTS]
    check('the refilled plan is still in slot order',
          planned == sorted(planned, key=order.index), str(planned))

    # A meal with nothing to offer stays dropped: an empty slot must not invent a stop.
    without_dinner = {k: v for k, v in by_sid.items() if v['slot'] != 'dinner'}
    plan = module._parse_plan(raw, without_dinner)
    check('a meal with no candidate is left out',
          'dinner' not in [s['slot'] for s in plan['stops']])


def test_sparse_results_drop_to_the_lower_floor():
    """Pure check, no API: MIN_SCORE is a review-count floor, fatal in a thin area.

    `rating * ln(sqrt(n))` needs ~208 reviews at 4.5 stars to clear 12, so a village's best
    places sit below it and the search comes back all but empty. The floor then drops to
    SPARSE_MIN_SCORE - lowered, never removed. Because the score weighs the rating by the
    evidence behind it, that buys back good-but-not-famous places and still refuses the 1-
    and 3-review entries: a missing suggestion is recoverable, a bad one is not.

    Two ways down: a day-trip search asks for the lower floor outright, and any search left
    with SPARSE_RESULTS or fewer places retries at it. A page that already has three or more
    must never be diluted.
    """
    print('\na nearly empty page drops to the lower score floor')
    good = {'id': 'viewpoint', 'displayName': {'text': 'Pian Perduto'}, 'rating': 4.8,
            'userRatingCount': 75, 'location': {'latitude': 42.8, 'longitude': 13.2}}
    village = [
        good,
        {'id': 'thin', 'displayName': {'text': 'Panorama'}, 'rating': 5.0,
         'userRatingCount': 16, 'location': {'latitude': 42.8, 'longitude': 13.2}},
        {'id': 'noise', 'displayName': {'text': 'Quarto San Lorenzo'}, 'rating': 5.0,
         'userRatingCount': 1, 'location': {'latitude': 42.8, 'longitude': 13.2}},
        {'id': 'mediocre', 'displayName': {'text': 'Piccolo Ristoro'}, 'rating': 4.0,
         'userRatingCount': 3, 'location': {'latitude': 42.8, 'longitude': 13.2}},
    ]

    def famous(n):
        return [{'id': f'big{i}', 'displayName': {'text': f'Big {i}'}, 'rating': 4.6,
                 'userRatingCount': 4000 + i,
                 'location': {'latitude': 41.9, 'longitude': 12.5}} for i in range(n)]

    def kept(places, **kwargs):
        original = choosing.Choosing._search_nearby
        choosing.Choosing._search_nearby = lambda self: places
        try:
            instance = choosing.Choosing('t', 2000, 'nature', 'it', [42.8, 13.2], **kwargs)
        finally:
            choosing.Choosing._search_nearby = original
        return [m['name'] for m in instance.formatted_df_to_dict.values()]

    village_kept = kept(village)
    check('an all-but-empty page retries at the lower floor',
          village_kept == ['Pian Perduto'], str(village_kept))
    check('16 reviews is not enough evidence yet', 'Panorama' not in village_kept)
    check('the 1- and 3-review entries stay out, empty page or not',
          not {'Quarto San Lorenzo', 'Piccolo Ristoro'} & set(village_kept))

    # The boundary. SPARSE_RESULTS places above 12 still retries; one more does not, and the
    # good-but-not-famous place is then held back rather than diluting a healthy page.
    at_threshold = kept(famous(choosing.SPARSE_RESULTS) + [good])
    check(f'{choosing.SPARSE_RESULTS} results still retry',
          'Pian Perduto' in at_threshold, str(at_threshold))
    above_threshold = kept(famous(choosing.SPARSE_RESULTS + 1) + [good])
    check(f'{choosing.SPARSE_RESULTS + 1} results are left alone',
          'Pian Perduto' not in above_threshold, str(above_threshold))

    # A day-trip search asks for the low floor outright - it needs candidates per slot, not
    # a full page - but a busy area fills up above 12 anyway, so nothing changes there.
    busy_kept = kept(village + famous(8), min_score=choosing.SPARSE_MIN_SCORE)
    check('a busy area is unaffected by the lower floor',
          all(n.startswith('Big') for n in busy_kept) and len(busy_kept) == 7, str(busy_kept))

    # Ranking is on the *rounded* score and the sort is stable, so saturated places keep
    # Google's order. Ranking on the raw float instead reshuffled 26 of 84 real city
    # searches when this was written - a silent change to the main product.
    saturated = [
        {'id': 'first', 'displayName': {'text': 'First'}, 'rating': 4.6,
         'userRatingCount': 8000, 'location': {'latitude': 41.9, 'longitude': 12.5}},
        {'id': 'second', 'displayName': {'text': 'Second'}, 'rating': 5.0,
         'userRatingCount': 50000, 'location': {'latitude': 41.9, 'longitude': 12.5}},
    ] + famous(3)  # enough to clear the floor, so the sparse retry stays out of the way
    tied = kept(saturated)
    check('and a tie keeps the order Google returned', tied[:2] == ['First', 'Second'],
          str(tied))


def test_day_trip_village_reuses_its_only_restaurant():
    """Pure check, no API: one trattoria in town must still be lunch AND dinner.

    The interleaved split that keeps lunch and dinner distinct in a city hands the single
    restaurant to lunch and leaves dinner empty. A repeated meal is a worse day than two
    different ones and a much better day than no dinner.
    """
    print('\na village with one restaurant still gets dinner')
    only = {'the-trattoria': {'name': 'Trattoria', 'lat': 42.8, 'lng': 13.2, 'score': 60,
                              'opening_periods': None}}

    class OneRestaurantTown:
        def __init__(self, call_id, radius, category, lang, coordinates, **kwargs):
            self.formatted_df_to_dict = dict(only) if category == 'restaurants' else {}

    original = choosing.Choosing
    choosing.Choosing = OneRestaurantTown
    try:
        pool = choosing.build_day_trip_pool(2000, 'it', [42.8, 13.2], weekday=1)
    finally:
        choosing.Choosing = original

    check('lunch takes the only restaurant', len(pool['lunch']) == 1)
    check('dinner gets it too, flagged as a reuse',
          len(pool['dinner']) == 1 and pool['dinner'][0]['reuse'] is True,
          str([(c['place_id'], c['reuse']) for c in pool['dinner']]))
    check('the lunch copy is not flagged', pool['lunch'][0]['reuse'] is False)
    check('a meal with no places at all stays empty', not pool['breakfast'])

    plan = module._plan_day_trip_fallback(pool)
    stops = module.schedule_stops(plan['stops'], pool, 1)
    served = [s['slot']['key'] for s in stops]
    check('both meals are scheduled', served == ['lunch', 'dinner'], str(served))
    check('and they are the same place',
          len({s['place_id'] for s in stops}) == 1)
    check('no invented walk between the two sittings', all(s['leg'] is None for s in stops),
          str([s['leg'] for s in stops]))


def test_day_trip_fills_gaps_with_spare_parks():
    """Pure check, no API: dead time gets a park, and only where a park belongs.

    A day that lost its museum and its aperitivo has hours of nothing in it. The nature
    search is already paid for, so its unused candidates fill the holes - but only within
    slack, never past a closure, and never as a hike.
    """
    print('\nspare parks fill the holes a thin day leaves')

    def park(pid, lat, hours=None):
        return {'sid': pid, 'place_id': pid, 'slot': 'nature', 'hours': hours, 'dist_m': 0,
                'reuse': False,
                'metadata': {'name': pid, 'lat': lat, 'lng': 12.5, 'opening_periods': None}}

    def stop(key, lat, arrival, dwell, leg=None):
        return {'slot': module.slot_by_key(key), 'place_id': key, 'arrival': arrival,
                'depart': arrival + dwell, 'dwell': dwell, 'leg': leg, 'note': None,
                'hours': None, 'closed_warning': False,
                'metadata': {'name': key, 'lat': lat, 'lng': 12.5, 'opening_periods': None}}

    pool = {'nature': [park('near1', 41.9025), park('far', 41.9500),
                       park('closed', 41.9026, hours='closed'), park('near2', 41.9024),
                       park('near3', 41.9023)]}
    stops = [stop('lunch', 41.9000, 12 * 60, 75),
             stop('dinner', 41.9050, 19 * 60, 90, leg=module.walk_leg((41.9000, 12.5),
                                                                      (41.9050, 12.5)))]
    out = module.fill_gaps_with_nature(stops, pool, 1)

    fillers = [s for s in out if s.get('filler')]
    real = [s for s in out if not s.get('filler')]
    check('both holes got a park', len(fillers) == 2, str([s['place_id'] for s in fillers]))
    check('never more than the cap', len(fillers) <= module.DAY_TRIP_MAX_FILLERS)
    check('a closed park is never used', 'closed' not in [s['place_id'] for s in fillers])
    check('a park 5 km away is never used', 'far' not in [s['place_id'] for s in fillers])
    check('the planned stops did not move',
          [(s['place_id'], s['arrival'], s['depart']) for s in real]
          == [('lunch', 720, 795), ('dinner', 1140, 1230)],
          str([(s['place_id'], s['arrival']) for s in real]))
    check('the day stays in order',
          all(a['arrival'] <= b['arrival'] for a, b in zip(out, out[1:])),
          str([module.format_clock(s['arrival']) for s in out]))
    check('a filler always leaves before the next stop is due',
          all(a['depart'] + (b['leg']['minutes'] if b['leg'] else 0) <= b['arrival']
              for a, b in zip(out, out[1:])))
    check('fillers carry no invented note', all(s['note'] is None for s in fillers))
    check('every stop is a different place',
          len({s['place_id'] for s in out}) == len(out))

    # No slack, no filler: a day that is already full must come back untouched. Note it has
    # to start at 09:30 - an itinerary whose first stop is at noon has a morning hole in it.
    packed = [stop('breakfast', 41.9000, module.DAY_TRIP_START_MINUTES, 45),
              stop('lunch', 41.9010, 10 * 60 + 30, 75)]
    check('a day with no dead time is left alone',
          module.fill_gaps_with_nature(packed, pool, 1) == packed)
    check('and the cap can turn it off entirely',
          module.fill_gaps_with_nature(stops, pool, 1, max_fillers=0) == stops)


def test_day_trip_swapped_stop_drops_its_note():
    """Pure check, no API: the long-leg repair must not keep the old place's caption.

    The note is written by the model about a specific place, and it names it. When
    `schedule_stops` swaps that place out for a nearer one, keeping the sentence prints a
    card for one restaurant under a line recommending another - seen in Carpegna, where the
    dinner pick sat in the next village. Code chose the replacement, so it goes out
    unannotated, the same as a refilled meal or a filler park.
    """
    print('\na stop swapped for a nearer one loses the note written about the other place')

    def candidate(pid, lat):
        return {'sid': pid, 'place_id': pid, 'slot': 'dinner', 'hours': None, 'dist_m': 0,
                'reuse': False,
                'metadata': {'name': pid, 'lat': lat, 'lng': 12.5, 'opening_periods': None}}

    # 'far' is ~5.5 km from the lunch stop, over MAX_LEG_M; 'near' is ~1.1 km.
    pool = {'lunch': [candidate('lunchplace', 41.9000) | {'slot': 'lunch'}],
            'dinner': [candidate('far', 41.9500), candidate('near', 41.9100)]}
    plan = [{'slot': 'lunch', 'place_id': 'lunchplace', 'note': 'pranzo', 'dwell': 75},
            {'slot': 'dinner', 'place_id': 'far', 'note': 'Cena alla Locanda del Torrione',
             'dwell': 90}]
    stops = module.schedule_stops(plan, pool, 1)
    dinner = [s for s in stops if s['slot']['key'] == 'dinner']

    check('the far dinner was swapped for the nearer one',
          [s['place_id'] for s in dinner] == ['near'], str([s['place_id'] for s in dinner]))
    check('and it carries no note about the place it replaced',
          all(s['note'] is None for s in dinner), str([s['note'] for s in dinner]))
    check('a stop that was not swapped keeps its note',
          [s['note'] for s in stops if s['slot']['key'] == 'lunch'] == ['pranzo'])

    # No swap available: the original place stays, and so does the sentence about it.
    only_far = {'lunch': pool['lunch'], 'dinner': [candidate('far', 41.9500)]}
    kept = [s for s in module.schedule_stops(plan, only_far, 1)
            if s['slot']['key'] == 'dinner']
    check('with nothing nearer to swap in, the note survives',
          [(s['place_id'], s['note']) for s in kept]
          == [('far', 'Cena alla Locanda del Torrione')], str(kept))


def test_day_trip_windows_fit_the_day():
    """Pure check, no API: no reachable schedule may run past the end of the standard day.

    The slot windows are the only thing bounding the clock - `schedule_stops` clamps arrival
    into `[earliest, latest]` and adds `dwell`, so `latest + dwell` is the hard end of each
    slot. Adding a stop with a late window is exactly how a 23:30 day quietly becomes a
    01:00 one, which is why this is asserted rather than trusted to review.
    """
    print('\nday-trip slot windows fit inside the standard day')
    overruns = [(s['key'], module.format_clock(s['latest'] + s['dwell']))
                for s in module.DAY_TRIP_SLOTS
                if s['latest'] + s['dwell'] > module.DAY_TRIP_END_MINUTES]
    check('every slot ends by 23:30', not overruns, str(overruns))
    check('the day opens before the first slot closes',
          all(s['latest'] > module.DAY_TRIP_START_MINUTES for s in module.DAY_TRIP_SLOTS),
          str([s['key'] for s in module.DAY_TRIP_SLOTS
               if s['latest'] <= module.DAY_TRIP_START_MINUTES]))
    # Windows in visiting order: a slot that closes before the previous one opens could
    # never be reached, and would silently never appear in a plan.
    out_of_order = [(a['key'], b['key']) for a, b in
                    zip(module.DAY_TRIP_SLOTS, module.DAY_TRIP_SLOTS[1:])
                    if b['latest'] < a['earliest']]
    check('slot windows advance through the day', not out_of_order, str(out_of_order))


if __name__ == '__main__':
    test_every_type_is_valid()
    test_every_category_returns_results()
    test_no_language_bias()
    test_category_hierarchy_leaks()
    test_field_mapping()
    test_reviews_only_when_requested()
    test_one_call_per_search()
    test_cache_prevents_repeat_calls()
    test_non_food_cards_degrade()
    test_legacy_keyword_aliases()
    test_autocomplete_predictions()
    test_autocomplete_resolves_to_coordinates()
    test_autocomplete_details_stay_on_essentials()
    test_autocomplete_cache_prevents_repeat_calls()
    test_opening_periods_present()
    test_always_open_places_are_open_every_day()
    test_day_trip_pool_one_call_per_category()
    test_day_trip_pool_slots_disjoint()
    test_day_trip_plan_survives_without_llm()
    test_day_trip_meals_are_never_dropped()
    test_sparse_results_drop_to_the_lower_floor()
    test_day_trip_village_reuses_its_only_restaurant()
    test_day_trip_fills_gaps_with_spare_parks()
    test_day_trip_swapped_stop_drops_its_note()
    test_day_trip_windows_fit_the_day()

    print()
    if failures:
        print(f'{len(failures)} FAILED: {failures}')
        sys.exit(1)
    print('all checks passed')
