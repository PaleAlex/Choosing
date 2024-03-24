#imports
from choosing import *
import module as myfunc
import streamlit as st
from PIL import Image
#from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="Choosing: enjoy your best meal",
                   page_icon="🔍",
                   menu_items={
                       'Get Help': "mailto:aless.ciocchetti@gmail.com",
                       'Report a bug': 'mailto:aless.ciocchetti@gmail.com',
                       'About': ""
                        }
                   )

# Set the background image
css_style = """
<style>
[data-testid="stAppViewContainer"] > .main {
    background-image: url("https://images.unsplash.com/photo-1707209856575-a80b9dff5524?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D");
    background-size: 100vw 100vh;
    background-position: center;  
    background-repeat: no-repeat;
}

:root {
    font-size: 20px;
}

.restaurant-card {
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    border: 1px solid rgba(255, 255, 255, .25);
    background-color: rgba(255, 255, 255, 0.45);
    box-shadow: 0 0 10px 1px rgba(0, 0, 0, 0.25);
}

.restaurant-name {
    font-size: 30px;
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
    .restaurant-name {
        font-size: 24px; /* Adjust heading size for smaller screens */
    }
    .restaurant-info, .details li {
        font-size: 14px; /* Adjust text size for better fit */
    }
}

/*
iframe {
    display: none !important;
    background-color: transparent;
}

.__web-inspector-hide-shortcut__ {
    display: none !important;
    background-color: transparent;
}

@media only screen and (max-width: 768px) {
    .stCheckbox {
        display: none;
    }
}
*/

</style>
"""

st.markdown(css_style, unsafe_allow_html=True)

col1, col2, col3 = st.columns([9,1.5,1.5])

with col1:
    image = Image.open('logo.png')
    st.image(image, use_column_width=True)

def get_index_for_selectbox(last_selection:str, mapping:dict):
    return sorted(list(mapping.values()), reverse=True).index(last_selection)

with col2:
    keywords = {"🍴": "restaurant", "🍺": "pub", "🍕": "pizzeria"}

    if "keyword" not in st.query_params:
        st.query_params['keyword'] = 'restaurant'
        #st.rerun()

    def set_keyword() -> None:
        if "selected_keyword" in st.session_state:
            st.query_params['keyword'] = keywords.get(st.session_state["selected_keyword"])
    
    st.write("")
    index = get_index_for_selectbox(st.query_params['keyword'], keywords)
    option_keyword = st.selectbox(
        label="None",
        options=keywords,
        on_change=set_keyword,
        key="selected_keyword",
        index=index,
        label_visibility='hidden'
        )

with col3:
    languages = {"🇮🇹": "it", "🇬🇧": "en"}

    if "lang" not in st.query_params:
        st.query_params['lang'] = 'it'
        #st.rerun()

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

if 'address' not in st.session_state:
    st.session_state['address'] = ""
if 'latlon' not in st.session_state:
    st.session_state['latlon'] = None

#default_radius_value = 0.5

with map_expander:  
    # try:
    #     my_loc = get_geolocation()
    #     def fill_text_input():
    #         current_gps_coordinates = myfunc.get_current_gps_coordinates(my_loc) 
    #         if current_gps_coordinates[1]:
    #             st.session_state['text_input'] = current_gps_coordinates[1]
    #         else:
    #             st.session_state['text_input'] = 'POSITION NOT FOUND'
    # except TypeError:
    #     my_loc = None

    addresstextinput_placeholder = '🔍 Digita un indirizzo o un punto di riferimento (e.g. Piazza del Colosseo, Roma)' \
                                     if st.query_params['lang']=='it' else \
                                     "🔍 Write an address or a landmark (e.g. Colosseum, Rome)"
    
    address = st.text_input(label='Cosa vuoi cercare', key='text_input', placeholder=addresstextinput_placeholder, label_visibility='collapsed')
    
    #current_position_label = "📍Oppure cerca vicino a te" if st.query_params['lang']=='it' else '📍 Or find near to you'
    #current_position_status = True if my_loc is None else False
    #current_position_help = "Allow for geolocation first!" if my_loc is None else None

    # if st.checkbox(current_position_label, disabled=current_position_status, help=current_position_help, on_change=fill_text_input):
    #     current_gps_coordinates = myfunc.get_current_gps_coordinates(my_loc)
    #     st.session_state['latlon'] = current_gps_coordinates[0]
    #     st.session_state['address'] = 'current'
    #     default_radius_value = current_gps_coordinates[2]/1000 if current_gps_coordinates[2] else None
    # elif address:

    
    st.session_state['address'] = address
    
    if st.session_state['address'] != "":
        try:
            st.session_state['latlon'] = myfunc.get_coordinates(st.session_state['address'])
            colcol1, colcol2 = st.columns([8,4])

            with colcol2:
                radius_label = "**Raggio [km]**" if st.query_params['lang']=='it' else "**Radius [km]**"
                radius = st.number_input(radius_label, min_value=0.5, step=0.5, key='radius_input')*1000 #value=default_radius_value

                specific_request_label = "Opzionale: descrivimi cosa ti piacerebbe mangiare! 😉 (*Powered by LLM*)" \
                                         if st.query_params['lang']=='it' else \
                                         "Optional: tell me what do you want to eat! 😉 (*Powered by LLM*)"
                
                specific_request_placeholder = 'Vorrei mangiare pasta fresca fatta in casa' \
                                                if st.query_params['lang']=='it' else \
                                                'I want to eat handmade pasta like Lasagna or Tagliatelle'
                
                specific_request_status = False if st.query_params['keyword']=='restaurant' else True
                specific_request_help = 'Disponibile solo per la ricerca di ristoranti'\
                                        if st.query_params['lang']=='it' else \
                                        'Available only for restaurant recommandation'

                specific_request = st.text_area(specific_request_label, max_chars=80, key="prompt_text_area", placeholder=specific_request_placeholder, help=specific_request_help, disabled=specific_request_status)
                
                search_button_label = "Trova" if st.query_params['lang']=='it' else 'Find'
                search_button = st.button(f"{search_button_label} {[k for k, v in keywords.items() if v == st.query_params['keyword']][0]}")
            
            with colcol1:
                if radius < 2000:
                    zoom=13
                else:
                    zoom = 11
                st.map(st.session_state['latlon'], zoom = zoom, size=radius) 

        except TypeError:
            address_error = "C'è qualcosa che non va nell'indirizzo che hai scritto. Prova a correggerlo facendo riferimento allo standard di Google Maps" \
                            if st.query_params['lang']=='it' else \
                            "There's something wrong in your address. Try to write it better using the Google Maps standard"
            st.error(address_error)
            st.session_state['address'] = ""
            st.session_state['latlon'] = None
    

if search_button:

    ch = Choosing('id', radius, st.query_params['keyword'], st.query_params['lang'], st.session_state['latlon'].values[0])
    title_string = "#### 🎉 Ecco cosa ha trovato per te Choosing!" if st.query_params['lang']=='it' else "#### 🎉 Here is what Choosing has found for you!"
    st.write(title_string)   
    
    if specific_request=="" or st.query_params['keyword'] != 'restaurant':
        spinner_label_1 = 'Sto cercando...' if st.query_params['lang']=='it' else "I am searching..."

        with st.spinner(spinner_label_1):
            recommandations_placeids = ch.formatted_df_to_dict.keys()
            if len(recommandations_placeids)<7 and st.query_params['keyword'] == 'restaurant':
                warning_label = "Non sono stato bravo a trovare molti suggerimenti. Prova a modificare l'indirizzo e cerca di nuovo" \
                                if st.query_params['lang']=='it' else \
                                "I couldn't give you enough recommandations. Try to change the address and search again"
                st.warning(warning_label, icon='😖')

            all_cards_html = create_cards(recommandations_placeids, ch)
        st.markdown(all_cards_html, unsafe_allow_html=True)
    
    elif specific_request!="" and st.query_params['keyword'] == 'restaurant':

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
            LLM_matched_places = myfunc.promptLLM(context=context, preferences=specific_request, lang=st.query_params['lang'])
            #formatted_LLM_matched_places = extract_dict_from_llm_answer(LLM_matched_places)
            if len(LLM_matched_places)<100:
                LLM_warning_label = "Non sono stato bravo a trovare molti suggerimenti in base alle tue richieste specifiche. Prova a chiedermi qualcos'altro" \
                                    if st.query_params['lang']=='it' else \
                                    "I couldn't found enough recommandations based on your specific requests. Try asking me something else"
                st.warning(LLM_warning_label, icon='😖')
                info_label = "**Tutti i ristoranti valutati: \n**" if st.query_params['lang']=='it' else "**All considered restaurants: \n**"
                st.write(info_label)
                all_cards_html = create_cards(recommandations_placeids, ch)
            else:
                st.markdown(LLM_matched_places)
                all_cards_html = create_cards(recommandations_placeids, ch, LLM_matched_places)
        
        st.markdown(all_cards_html, unsafe_allow_html=True)

#FOOTER
footer="""
<style>
    .footer {
    position: fixed;
    left: 25%;
    bottom: 5px;
    width: 50%;
    text-align: center;
    background-color: white;
    border-radius: 10px;
    padding: 10px;
    }
    @media (max-width: 1000px) {
        .to_hide {
            display: none; /* Hide the footer on screens smaller than 768px (typical mobile devices) */
        }
    }

    a {
    margin-right: 15px;

    img {
        max-width: 100%;
        height: auto;
     }
    
</style>

<div class="footer">
    <small>
    <a href="https://www.linkedin.com/in/ac-palealex/", target="_blank", class="to_hide"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)"/></a>
    <a href="https://www.buymeacoffee.com/palealex", target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png"/></a>
    <img src="https://api.visitorbadge.io/api/visitors?path=https%3A%2F%2Fchoosing.club%2F&label=Visitors&labelColor=%23ff8a65&countColor=%23d9e3f0" />
    </small>
</div>
"""
st.markdown(footer,unsafe_allow_html=True)

