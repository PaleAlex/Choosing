#imports
from choosing import *
import module as myfunc
import streamlit as st
from PIL import Image
from streamlit_searchbox import st_searchbox
from datetime import date, timedelta

st.set_page_config(page_title="Choosing: enjoy your best meal",
                   page_icon="🔍",
                   # Default is 'centered', which squeezes the cards into a narrow column.
                   layout="wide",
                   menu_items={
                       'Get Help': "mailto:aless.ciocchetti@gmail.com",
                       'Report a bug': 'mailto:aless.ciocchetti@gmail.com',
                       'About': ""
                        }
                   )

# Set the background image
css_style = """
<style>
/* '.main' is the pre-1.4x class name; current versions expose the main area as
   [data-testid="stMain"]. Both are listed so the background survives either DOM. */
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"] {
    background-image: url("https://images.unsplash.com/photo-1707209856575-a80b9dff5524?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D");
    background-size: 100vw 100vh;
    background-position: center;  
    background-repeat: no-repeat;
}

:root {
    font-size: 20px;
}

/* layout='wide' fills the whole viewport, which leaves the cards absurdly stretched on a
   large monitor. This keeps the extra room but stops it running away. */
[data-testid="stMainBlockContainer"] {
    max-width: 1400px;
    padding-left: 3rem;
    padding-right: 3rem;
}

.restaurant-card {
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    border: 1px solid rgba(255, 255, 255, .25);
    background-color: rgba(255, 255, 255, 0.45);
    box-shadow: 0 0 10px 1px rgba(0, 0, 0, 0.25);
}

/* Streamlit 1.40 styled headings with a bare `h1` selector, which a single class beat.
   Newer versions style them with generated class selectors instead, so a lone
   `.restaurant-name` no longer wins and the titles render at the framework's h1 size.
   Qualifying by tag and parent keeps this authoritative regardless of the generated
   class name; the padding reset removes the vertical space Streamlit adds to headings. */
.restaurant-card h1.restaurant-name {
    font-size: 30px !important;
    font-weight: 700;
    line-height: 1.3;
    padding: 0 !important;
    margin: 0 0 10px 0;
}

.restaurant-info {
    margin-bottom: 10px;
    word-wrap: break-word; /* Ensure text does not overflow */
}

.details {
    list-style-type: none;
    padding: 0; /* Remove default padding */
}

.grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-gap: 5px; /* Add some space between columns */
}

/* One-day trip: the band above each card carrying the slot, the clock and the walk in.
   Sits directly on the background rather than in its own card, so a stop reads as
   'heading then card' instead of as two stacked panels. */
.trip-step {
    margin: 0 0 8px 4px;
}

.trip-step .trip-heading {
    font-size: 20px;
    line-height: 1.3;
}

.trip-step .trip-meta {
    font-size: 15px;
    opacity: 0.85;
}

.trip-step .trip-note {
    font-size: 15px;
    font-style: italic;
    margin-top: 2px;
}

.grid-item {
    padding: 10px;
}

@media (max-width: 768px) {
    .grid-container {
        grid-template-columns: 1fr; /* On smaller screens, switch to a single column layout */
    }
}

@media (max-width: 375px) {
    :root {
        font-size: 16px; /* Adjust font size for smaller screens */
    }
    /* Must match the specificity of the rule above, or it will not apply. */
    .restaurant-card h1.restaurant-name {
        font-size: 24px !important; /* Adjust heading size for smaller screens */
    }
    .restaurant-info, .details li {
        font-size: 14px; /* Adjust text size for better fit */
    }
}

/* Removed: `.st-emotion-cache-1pibh61.e1nzilvr3 { display: none }`. Both were generated
   emotion class names from an older Streamlit; 'e1nzilvr*' no longer exists at all, so the
   rule had stopped matching anything. Never target a generated class - it is not an API. */

</style>
"""

st.markdown(css_style, unsafe_allow_html=True)

# Query-param defaults are set before the columns because the category labels below are
# localised, so they need 'lang' to already be resolved.
if "lang" not in st.query_params:
    st.query_params['lang'] = 'it'
if "keyword" not in st.query_params:
    st.query_params['keyword'] = 'restaurants'

# Accept the ?keyword= values used before the category rework, so shared links keep working.
if myfunc.is_day_trip(st.query_params['keyword']):
    # Canonicalised here, so the selectbox index lookup and every later comparison
    # see one form regardless of how the link was written.
    st.query_params['keyword'] = myfunc.DAY_TRIP_KEYWORD
else:
    st.query_params['keyword'] = myfunc.normalize_category(st.query_params['keyword'])

# The category selector carries readable labels now, so it needs more room than the
# emoji-only box it replaces.
col1, col2, col3 = st.columns([6,4,1.2])

with col1:
    image = Image.open('logo.png')
    st.image(image, width='stretch')

def get_index_for_selectbox(last_selection:str, mapping:dict):
    return sorted(list(mapping.values()), reverse=True).index(last_selection)

with col2:
    # Every Places category, plus the day-trip planner, which is a composite of several
    # searches rather than a category of its own.
    category_keys = list(myfunc.CATEGORIES.keys()) + [myfunc.DAY_TRIP_KEYWORD]

    def set_keyword() -> None:
        if "selected_keyword" in st.session_state:
            st.query_params['keyword'] = st.session_state["selected_keyword"]

    # Captured rather than read inside format_keyword: Streamlit may call a format_func
    # outside a script run, where st.query_params is not available.
    current_lang = st.query_params['lang']

    def format_keyword(key: str) -> str:
        if key == myfunc.DAY_TRIP_KEYWORD:
            return "🧙‍♂️ Itinerario di un giorno" if current_lang == 'it' else "🧙‍♂️ One-day trip"
        return myfunc.category_label(key, current_lang)

    st.write("")
    option_keyword = st.selectbox(
        label="None",
        options=category_keys,
        format_func=format_keyword,
        on_change=set_keyword,
        key="selected_keyword",
        index=category_keys.index(st.query_params['keyword']),
        label_visibility='hidden'
        )

with col3:
    languages = {"🇮🇹": "it", "🇬🇧": "en"}

    def set_language() -> None:
        if "selected_language" in st.session_state:
            st.query_params['lang'] = languages.get(st.session_state["selected_language"])
    
    st.write("")
    index = get_index_for_selectbox(st.query_params['lang'], languages)
    option_lang = st.selectbox(
        label="None",
        options=languages,
        on_change=set_language,
        key="selected_language",
        index=index,
        label_visibility='hidden'
        )


expander_label = "Dove vuoi cercare?" if st.query_params['lang']=='it' else 'Where do you want to search?'
map_expander = st.expander(label=expander_label, expanded=True)
search_button = False
day_trip_button = False

if 'address' not in st.session_state:
    st.session_state['address'] = ""
if 'latlon' not in st.session_state:
    st.session_state['latlon'] = None
if 'resolved_pick' not in st.session_state:
    st.session_state['resolved_pick'] = None

with map_expander:  

    addresstextinput_placeholder = '🔍 Digita un indirizzo o un punto di riferimento (e.g. Piazza del Colosseo, Roma)' \
                                     if st.query_params['lang']=='it' else \
                                     "🔍 Write an address or a landmark (e.g. Colosseum, Rome)"
    
    def address_suggestions(query: str) -> list:
        """Feeds the searchbox. Values are prefixed so the pick tells us how to resolve it."""
        options = [(label, f"id:{place_id}") for label, place_id
                   in myfunc.autocomplete_address(query, st.query_params['lang'])]
        if not options and len((query or '').strip()) >= myfunc.MIN_AUTOCOMPLETE_CHARS:
            # Autocomplete returned nothing (no match, or the API is unavailable). Offering
            # the raw text keeps the box from becoming a dead end - Nominatim handles it.
            options = [(f"📍 {query.strip()}", f"raw:{query.strip()}")]
        return options

    picked = st_searchbox(
        address_suggestions,
        placeholder=addresstextinput_placeholder,
        # No label: the placeholder carries the instruction, as the old text input did
        # with label_visibility='collapsed'.
        label=None,
        key='address_searchbox',
        # Default is 150ms, which fires a request on nearly every keystroke.
        debounce=450,
        edit_after_submit='current',
    )

    if st.session_state['address'] != "" or picked:
        try:
            # The searchbox keeps returning the same pick on every rerun (radius change,
            # button press), so it is resolved once and then read from session state.
            if picked and picked != st.session_state.get('resolved_pick'):
                if picked.startswith('id:'):
                    # A real prediction: exact coordinates by place id, nothing geocoded.
                    st.session_state['latlon'], st.session_state['address'] = \
                        myfunc.resolve_place(picked[len('id:'):], st.query_params['lang'])
                else:
                    st.session_state['address'] = picked[len('raw:'):]
                    st.session_state['latlon'] = myfunc.get_coordinates(st.session_state['address'])
                st.session_state['resolved_pick'] = picked

            colcol1, colcol2 = st.columns([8,4])

            with colcol2:
                radius_label = "**Raggio [km]**" if st.query_params['lang']=='it' else "**Radius [km]**"
                radius = st.number_input(radius_label, min_value=0.5, max_value=4.0, step=0.5, key='radius_input')*1000

                if st.query_params['keyword'] != myfunc.DAY_TRIP_KEYWORD:
                    specific_request_label = "Opzionale: descrivimi cosa ti piacerebbe mangiare! 😉 (*Powered by LLM*)" \
                                            if st.query_params['lang']=='it' else \
                                            "Optional: tell me what do you want to eat! 😉 (*Powered by LLM*)"
                    
                    specific_request_placeholder = 'Vorrei mangiare pasta fresca fatta in casa' \
                                                    if st.query_params['lang']=='it' else \
                                                    'I want to eat handmade pasta like Lasagna or Tagliatelle'
                    
                    specific_request_status = False if st.query_params['keyword']=='restaurants' else True

                    if st.query_params['keyword']=='restaurants':
                        specific_request_help = None
                    else:
                        specific_request_help = 'Disponibile solo per la ricerca di ristoranti'\
                                                if st.query_params['lang']=='it' else \
                                                'Available only for restaurant recommandation'

                    specific_request = st.text_area(specific_request_label, max_chars=100, key="prompt_text_area", placeholder=specific_request_placeholder, help=specific_request_help, disabled=specific_request_status)
                    
                    search_button_label = "Trova" if st.query_params['lang']=='it' else 'Find'
                    search_button = st.button(f"{search_button_label} {myfunc.CATEGORIES[st.query_params['keyword']]['emoji']}")
                
                else:
                    # The date is the only question left. A start time and a half-day flag
                    # used to be asked for too; both were preferences the traveller can act
                    # on without the app - the itinerary is a running order, and leaving an
                    # hour later just means reading it an hour later. The date is different:
                    # opening hours are per weekday, so it is what keeps the plan out of a
                    # museum that shuts on Mondays.
                    trip_when_label = "Che giorno?" if st.query_params['lang']=='it' else "Which day?"

                    # Bounded to the coming week on purpose: 'currentOpeningHours' returns
                    # this week's hours, holiday closures included, so a date further out
                    # would be scheduled against hours that do not describe it.
                    trip_date = st.date_input(trip_when_label, value=date.today(),
                                             min_value=date.today(),
                                             max_value=date.today() + timedelta(days=6),
                                             key='trip_date_input', format="DD/MM/YYYY")

                    # The frame is stated rather than made adjustable, so nobody has to press
                    # the button to find out what kind of day they are about to be given.
                    trip_frame_caption = (
                        f"🕘 Giornata tipo: dalle **{myfunc.format_clock(myfunc.DAY_TRIP_START_MINUTES)}** "
                        f"alle **{myfunc.format_clock(myfunc.DAY_TRIP_END_MINUTES)}** circa. "
                        "Gli orari sono indicativi: adattali come preferisci."
                        if st.query_params['lang']=='it' else
                        f"🕘 A standard day: **{myfunc.format_clock(myfunc.DAY_TRIP_START_MINUTES)}** to about "
                        f"**{myfunc.format_clock(myfunc.DAY_TRIP_END_MINUTES)}**. "
                        "Times are indicative - take them at your own pace."
                    )
                    st.caption(trip_frame_caption)

                    day_trip_button_label = "🧙‍♂️ Crea l'itinerario" if st.query_params['lang']=='it' \
                                            else "🧙‍♂️ Plan my day"
                    day_trip_button = st.button(day_trip_button_label, type='primary')

            with colcol1:
                if radius < 2000:
                    zoom = 13
                else:
                    zoom = 11
                st.map(st.session_state['latlon'], zoom = zoom, size=radius) 

        except BadAddressError:
            address_error = "C'è qualcosa che non va nell'indirizzo che hai scritto. Prova a correggerlo facendo riferimento allo standard di Google Maps" \
                            if st.query_params['lang']=='it' else \
                            "There's something wrong in your address. Try to write it better using the Google Maps standard"
            st.error(address_error)
            st.session_state['address'] = ""
            st.session_state['latlon'] = None
            # Clear the memo so picking the same entry again retries instead of silently
            # reusing the failed resolution.
            st.session_state['resolved_pick'] = None
        
        except ServiceError:
            service_error = "Superato il limite di chiamate del servizio, riprova più tardi :)" \
                            if st.query_params['lang']=='it' else \
                            "Service call limit exceeded, please try again later :)"
            st.error(service_error)
        
        except Exception as e:
            generic_error = "Ops, qualcosa è andato storto. Riprova più tardi :)" \
                            if st.query_params['lang']=='it' else \
                            "Ops, something went wrong. Please try again later :)"
            st.error(generic_error)
            print(e)

if search_button:

    # Reviews are only requested when the LLM will actually read them: they push the call
    # onto the pricier Enterprise + Atmosphere SKU, and each SKU has its own free tier.
    needs_reviews = bool(specific_request) and st.query_params['keyword'] == 'restaurants'

    try:
        ch = Choosing('id', radius, st.query_params['keyword'], st.query_params['lang'], st.session_state['latlon'].values[0], with_reviews=needs_reviews)
    except PlacesApiError as e:
        places_error = "Il servizio di ricerca non è disponibile in questo momento. Riprova più tardi :)" \
                       if st.query_params['lang']=='it' else \
                       "The search service is unavailable right now. Please try again later :)"
        st.error(places_error)
        print(e)
        st.stop()

    title_string = "#### 🎉 Ecco cosa ha trovato per te Choosing!" if st.query_params['lang']=='it' else "#### 🎉 Here is what Choosing has found for you!"
    st.write(title_string)   
    
    if specific_request=="" or st.query_params['keyword'] != 'restaurants':
        spinner_label_1 = 'Sto cercando...' if st.query_params['lang']=='it' else "I am searching..."

        with st.spinner(spinner_label_1):
            recommandations_placeids = ch.formatted_df_to_dict.keys()
            if len(recommandations_placeids)<7 and st.query_params['keyword'] == 'restaurants':
                warning_label = "Non sono stato bravo a trovare molti suggerimenti. Prova a modificare l'indirizzo e cerca di nuovo" \
                                if st.query_params['lang']=='it' else \
                                "I couldn't give you enough recommandations. Try to change the address and search again"
                st.warning(warning_label, icon='😖')

            all_cards_html = myfunc.create_cards(recommandations_placeids, ch)
        st.markdown(all_cards_html, unsafe_allow_html=True)
    
    elif specific_request!="" and st.query_params['keyword'] == 'restaurants':

        best_places_to_be_analyzed = ch.formatted_df_to_dict
        recommandations_placeids = best_places_to_be_analyzed.keys()

        if len(recommandations_placeids)<7:
            warning_label = "Non sono stato bravo a trovare molti suggerimenti. Prova a modificare l'indirizzo o aumentare il raggio di ricerca" \
                            if st.query_params['lang']=='it' else \
                            "I couldn't found enough recommandations. Try to change the address or the radius and search again"
            st.warning(warning_label, icon='😖')

        spinner_label_2 = 'Leggendo recensioni...' if st.query_params['lang']=='it' else "Reading reviews..."
        spinner_label_3 = 'Personalizzando i consigli...' if st.query_params['lang']=='it' else "Creating personalized recommandations..."
        
        with st.spinner(spinner_label_2):
            context = ch.build_dataset()
        with st.spinner(spinner_label_3):
            #st info for Choosing virtual assistant generating text
            LLM_matched_places = myfunc.promptLLM(context=context, preferences=specific_request, lang=st.query_params['lang'])
            print(f"LLM_matched_places: {LLM_matched_places}")
            #formatted_LLM_matched_places = extract_dict_from_llm_answer(LLM_matched_places)
            # A reasoning model can return empty content with no error at all, so the falsy
            # case is checked first - len(None) would be a traceback in the user's face.
            if not LLM_matched_places or len(LLM_matched_places)<150:
                LLM_warning_label = "Non sono stato bravo a trovare suggerimenti in base alle tue richieste specifiche. Prova a chiedermi qualcos'altro" \
                                    if st.query_params['lang']=='it' else \
                                    "I couldn't found recommandations based on your specific requests. Try asking me something else"
                st.warning(LLM_warning_label, icon='😖')
                info_label = "**Top ristoranti nella zona:** \n" if st.query_params['lang']=='it' else "**Top restaurants in the area:** \n"
                st.write(info_label)
                all_cards_html = myfunc.create_cards(recommandations_placeids, ch)
                st.markdown(all_cards_html, unsafe_allow_html=True)
            else:
                st.markdown(f"""{LLM_matched_places} *""")
                all_cards_html = myfunc.create_cards(recommandations_placeids, ch, LLM_matched_places)
                st.markdown(all_cards_html, unsafe_allow_html=True)
                
                st.write("")
                
                LLM_advisor_label = """* Il testo è stato generato dall'assistente virtuale AI di Choosing.
                                         L'assistente virtuale cerca tra i top 7 ristoranti della zona selezionata e seleziona tra quelli i più vicini
                                         alle preferenze espresse dall'utente.""" \
                                    if st.query_params['lang']=='it' else \
                                    """* The text has been generated by Choosing's AI virtual assistant.
                                         The virtual assistant searches among the top 7 restaurants in the selected area and choose from
                                         those the closest to the user's preferences."""
                

                st.markdown(f"""<i><small>{LLM_advisor_label}</small></i>""", unsafe_allow_html=True)

elif day_trip_button:
    lang = st.query_params['lang']
    weekday = myfunc.google_weekday(trip_date)

    trip_title = "#### 🎉 Il tuo itinerario!" if lang=='it' else "#### 🎉 Your one-day trip!"
    st.write(trip_title)

    try:
        spinner_label_4 = 'Cercando i migliori posti...' if lang=='it' else "Looking for the best places..."
        with st.spinner(spinner_label_4):
            # One Places call per distinct category, all cached for 30 days.
            pool = build_day_trip_pool(radius, lang, st.session_state['latlon'].values[0],
                                       weekday)

        spinner_label_5 = 'Pianificando il tuo itinerario...' if lang=='it' else "Planning your trip..."
        with st.spinner(spinner_label_5):
            # The LLM only orders and annotates the pool; the clock comes from the walking
            # distances, so the times can never contradict the map.
            plan = myfunc.plan_day_trip(pool, lang, weekday)
            stops = myfunc.schedule_stops(plan['stops'], pool, weekday)
            # Spare parks go into whatever dead time is left. They cost no call and no token,
            # and they only consume slack, so the schedule above them does not move.
            stops = myfunc.fill_gaps_with_nature(stops, pool, weekday)

        if not stops:
            warning_label = "Non sono stato bravo a trovare abbastanza posti per un itinerario. Prova a modificare l'indirizzo o ad aumentare il raggio di ricerca" \
                            if lang=='it' else \
                            "I couldn't find enough places for an itinerary. Try another address or a larger radius"
            st.warning(warning_label, icon='😖')
        else:
            # An honest header for a thin area, naming what is missing. Two stops five hours
            # apart otherwise render exactly like a full day, and the traveller has no way to
            # tell whether the place is quiet or the search was too narrow. Saying it beats
            # padding the day with places nobody would recommend.
            # Counted on the stops the planner actually chose: two parks dropped into the
            # holes make the day pleasanter, not fuller, and must not silence this.
            if len([s for s in stops if not s.get('filler')]) < myfunc.DAY_TRIP_THIN_STOPS:
                filled = {s['slot']['key'] for s in stops}
                missing = ", ".join(myfunc.slot_label(s, lang)
                                    for s in myfunc.DAY_TRIP_SLOTS if s['key'] not in filled)
                thin_label = f"Qui non ho trovato posti abbastanza buoni per: {missing}. " \
                             "Meglio una tappa in meno che un consiglio mediocre — prova ad " \
                             "allargare il raggio o a partire da un indirizzo più centrale." \
                             if lang=='it' else \
                             f"Around here I found nothing good enough for: {missing}. " \
                             "Better one stop fewer than a poor recommendation — try a larger " \
                             "radius, or a more central address."
                st.info(thin_label, icon='🤏')

            if plan.get('title'):
                st.write(f"**{plan['title']}**")

            deck = myfunc.day_trip_deck(stops, st.session_state['latlon']['lat'].values[0],
                                        st.session_state['latlon']['lon'].values[0], lang)
            if deck:
                st.pydeck_chart(deck)

            total_m = sum(s['leg']['metres'] for s in stops if s['leg'])
            total_min = sum(s['leg']['minutes'] for s in stops if s['leg'])
            # The span is printed from the schedule, not from the frame: a day whose slots
            # were dropped for closures really does end earlier, and saying 23:30 anyway
            # would be the one number on the page that is not computed.
            span = f"{myfunc.format_clock(stops[0]['arrival'])} → {myfunc.format_clock(stops[-1]['depart'])}"
            summary = f"🚶 **{total_m/1000:.1f} km** a piedi in totale ({total_min} min) · " \
                      f"{len(stops)} tappe · **{span}**" \
                      if lang=='it' else \
                      f"🚶 **{total_m/1000:.1f} km** of walking in total ({total_min} min) · " \
                      f"{len(stops)} stops · **{span}**"
            st.markdown(summary)

            st.markdown(myfunc.create_trip_cards(stops, lang), unsafe_allow_html=True)

            if plan.get('closing'):
                st.write(f"*{plan['closing']}*")

            # Walking times are estimates from straight-line distance, not a routing
            # service, so the estimate is labelled rather than presented as a fact.
            final_advisory = """*Gli orari sono stimati: le distanze a piedi sono approssimate e non tengono conto del percorso reale.
                                Controlla gli orari di apertura e prenota le visite ai musei. Quando puoi, muoviti a piedi, in bici o con i mezzi pubblici.*""" \
                             if lang=='it' else \
                             """*Times are estimates: walking distances are approximate and do not follow the real street layout.
                                Check the opening hours and book your museum visits. Whenever you can, walk, cycle or use public transport.*"""
            st.write(final_advisory)

    except PlacesApiError as e:
        places_error = "Il servizio di ricerca non è disponibile in questo momento. Riprova più tardi :)" \
                       if lang=='it' else \
                       "The search service is unavailable right now. Please try again later :)"
        st.error(places_error)
        print(e)





#FOOTER
footer="""
<style>
    /* Centred with left/right + auto margins rather than the original left:25%/width:50%.
       Those percentages resolve against the containing block, which is the viewport only
       while no ancestor sets transform/filter/will-change - so a layout change could shift
       the box sideways and push the last badge out of view. This centres either way. */
    .footer {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 5px;
    width: auto;
    max-width: 50%;
    margin: 0 auto;
    text-align: center;
    background-color: white;
    border-radius: 10px;
    padding: 10px;
    }
    @media (max-width: 1000px) {
        /* Only badges carrying .to_hide go away (the YouTube one), not the whole footer. */
        .footer .to_hide {
            display: none;
        }
        /* Half the viewport is too narrow for the remaining badges on a small screen. */
        .footer {
            max-width: 90%;
        }
    }

    /* Scoped to .footer: this was a bare `a` selector with an unclosed brace, so the
       margin applied to every link on the page, card titles included. */
    .footer a {
        margin-right: 15px;
    }

    /* Deliberately `.footer a img`, not `.footer img`: in the original this rule was nested
       inside the `a` block, so it never applied to the visitor counter, which was the one
       image not wrapped in a link. Widening it changed that element's sizing. */
    .footer a img {
        max-width: 100%;
        height: auto;
    }

    /* Replaces the third-party visitor badge, which was an <img> from api.visitorbadge.io -
       a tracker-shaped request that ad blockers routinely drop, leaving a broken-image icon.
       Styled to match the badge it stands in for. */
    .footer .visits {
        display: inline-block;
        vertical-align: middle;
        padding: 4px 10px;
        border-radius: 6px;
        /* The green of the logo wordmark (sampled from logo.png, 80% of its pixels). */
        background-color: #24A19C;
        color: #ffffff;
        font-size: 14px;
        font-weight: 600;
        white-space: nowrap;
    }
</style>
"""

visitor_count = myfunc.get_visitor_count()
visitors_label = "Ricerche" if st.query_params['lang'] == 'it' else "Searches"
# A zero means Redis was unreachable, so the counter is omitted rather than claiming no visitors.
visits_html = (
    f'<span class="visits">👀 {visitors_label}: '
    f'{myfunc.format_visitor_count(visitor_count, st.query_params["lang"])}</span>'
    if visitor_count else ''
)

footer += f"""
<div class="footer">
    <small>
    <a href="https://www.youtube.com/@choosingclub" target="_blank" class="to_hide"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white"/></a>
    <a href="https://www.buymeacoffee.com/palealex" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png"/></a>
    {visits_html}
    </small>
</div>
"""
st.markdown(footer,unsafe_allow_html=True)

