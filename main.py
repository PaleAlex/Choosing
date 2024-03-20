#imports
from choosing import *
import module as myfunc
import streamlit as st
from PIL import Image

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
}

.details {
list-style-type: none;
}

.grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-gap: 5px; /* Add some space between columns */

    @media (max-width: 768px) {
        grid-template-columns: 1fr; /* On smaller screens, switch to a single column layout */
    }
}

.grid-item {
    padding: 10px;
}

</style>
"""

st.markdown(css_style, unsafe_allow_html=True)

col1, col2, col3 = st.columns([9,1.5,1.5])

with col1:
    image = Image.open('logo.png')
    st.image(image, width=450)

with col2:
    keywords = {"🍴": "restaurant", "🍺": "pub", "🍕": "pizzeria"}

    if "keyword" not in st.query_params:
        st.query_params['keyword'] = 'restaurant'
        #st.rerun()

    def set_keyword() -> None:
        if "selected_keyword" in st.session_state:
            st.query_params['keyword'] = keywords.get(st.session_state["selected_keyword"])
    
    st.write("")
    option_keyword = st.selectbox(
        label="None",
        options=keywords,
        on_change=set_keyword,
        key="selected_keyword",
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
    option_lang = st.selectbox(
        label="None",
        options=languages,
        on_change=set_language,
        key="selected_language",
        label_visibility='hidden'
        )


map_container = st.container(border=True)
search_button = False

if 'address' not in st.session_state:
    st.session_state['address'] = ""
if 'latlon' not in st.session_state:
    st.session_state['latlon'] = None

with map_container:
    def clear_text_input():
        st.session_state['text_input'] = myfunc.get_current_gps_coordinates()[1]
    
    address_textinput_label = "Dove vuoi cercare?" if st.query_params['lang']=='it' else 'Where do you want to search?'
    addresstextinput_placeholder = '🔍 Digita un indirizzo o un punto di riferimento (e.g. Piazza del Colosseo, Roma)' \
                                     if st.query_params['lang']=='it' else \
                                     "🔍 Write an address or a landmark (e.g. Colosseum, Rome)"
    
    address = st.text_input(f'**{address_textinput_label}**', key='text_input', help=None, placeholder=addresstextinput_placeholder)
    markdown_label = "oppure" if st.query_params['lang']=='it' else "otherwise"
    st.markdown(f"""<small>{markdown_label}</small>""", unsafe_allow_html=True)

    current_position_label = "📍 Cerca vicino a te" if st.query_params['lang']=='it' else '📍 Find near to you'
    
    if st.button(current_position_label, on_click=clear_text_input):
        st.session_state['latlon'] = myfunc.get_current_gps_coordinates()[0]
        st.session_state['address'] = 'current'

    elif address:
        st.session_state['latlon'] = myfunc.get_coordinates(address)
        st.session_state['address'] = address
    
    if st.session_state['address'] != "":
        try:
            colcol1, colcol2 = st.columns([8,4])

            with colcol2:
                radius_label = "**Raggio [km]**" if st.query_params['lang']=='it' else "**Radius [km]**"
                radius = st.number_input(radius_label, min_value=0.5, step=0.5, key='radius_input')

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
                st.map(st.session_state['latlon'], zoom = 13, size=radius*1000) 

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
    
    if specific_request=="":
        spinner_label = 'Sto cercando...' if st.query_params['lang']=='it' else "I am searching..."

        with st.spinner(spinner_label):
            recommandations_placeids = ch.formatted_df_to_dict.keys()
            if len(recommandations_placeids)<7:
                warning_label = "Non sono stato bravo a trovare molti suggerimenti. Prova a modificare l'indirizzo e cerca di nuovo" \
                                if st.query_params['lang']=='it' else \
                                "I couldn't give you enough recommandations. Try to change the address and search again"
                st.warning(warning_label, icon='😖')

            all_cards_html = create_cards(recommandations_placeids, ch, score_type='normal')
        

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
    <img src="https://www.cutercounter.com/hits.php?id=hexpapxk&nd=4&style=66" border="0" alt="user counter"/>users
    </small>
</div>
"""
st.markdown(footer,unsafe_allow_html=True)