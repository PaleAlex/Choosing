from config import groq_api_key, maps_api_key, redis_client
import streamlit as st
import numpy as np
import pandas as pd
from groq import Groq
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
from datetime import datetime
import json

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

@st.cache_data(ttl=3600)
def get_coordinates(address: str) -> pd.DataFrame:
    key = _redis_key_for_address(address)

    # 1) Check Redis first
    cached = redis_client.get(key)
    if cached:
        data = json.loads(cached)
        return pd.DataFrame({"lat": [data["lat"]], "lon": [data["lon"]]})

    # 2) Call Nominatim
    try:
        geolocator = Nominatim(user_agent="choosingclub_webapp", timeout=10)
        location = geolocator.geocode(address)
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as e:
        _log_geocode_usage(address)   # Service problems: quota, timeout, unavailable
        raise ServiceError(f"Nominatim service error: {str(e)}")

    if location is None:
        # Valid call but no results: cache the miss to avoid repeated calls for bad addresses
        miss_data = {"lat": None, "lon": None}
        redis_client.setex(key, 3600, json.dumps(miss_data))  # 1h TTL for misses
        raise BadAddressError(f"No geocoding results for address: {address}")

    lat = location.latitude
    lon = location.longitude

    # 3) Cache hit in Redis (30 days TTL)
    redis_client.setex(
        key,
        60 * 60 * 24 * 30,  # 30 days
        json.dumps({"lat": lat, "lon": lon})
    )
    
    # 4) Log the actual Nominatim call
    _log_geocode_usage(address)

    return pd.DataFrame({"lat": [lat], "lon": [lon]})


def create_cards(recommandations_placeids: list, choosing_instance, llm_answer=None):
    # store card HTML content
    cards_html = []
    price_levels = {
        0: '❔',
        1:'🟩⬜⬜⬜',
        2:'🟩🟨⬜⬜',
        3:'🟩🟨🟧⬜',
        4:'🟩🟨🟧🟥',
    }
    
    rank = 0
    
    for place_id in recommandations_placeids:
        rank += 1

        metadata, _ = choosing_instance.get_metadata_and_reviews(place_id)
        
        price_level = metadata['price_level']
        viz_price_level = price_levels[price_level]

        if llm_answer:
            if metadata['name'] not in llm_answer:
                rank -= 1
                continue

        card_html = f"""                              
            <div class="restaurant-card">
                <div class="grid-container">
                    <div class="grid-item">
                        <h1 class="restaurant-name"><a href={metadata['website'] if metadata['website'] else ""}> {rank}° · {metadata['name']}</a></h1>
                        <p class="restaurant-info"> <strong>Scores</strong>
                            <ul class="details">
                                <li>Choosing Score: {metadata['score'] if metadata['score'] else "❔"}/100 </li>
                                <li>Price level: {viz_price_level} </li>
                                <li>Wheelchair accessibility: {"🟢" if metadata['accessible'] else "🔴"} </li>
                            </ul>
                        </p>
                    </div>
                    <div class="grid-item">
                        <p class="restaurant-info">
                            <ul class="details">
                                <li> <strong> Address: </strong> <a href={metadata['google_url']}> {metadata['vicinity']} </a> </li>
                                <li> <strong> Phone:   </strong> <a href="tel:{"".join(metadata['phone_number'].split(" ")[1:]) if metadata['phone_number'] else ""}">
                                                                    {metadata['phone_number'] if metadata['phone_number'] else "❔"}
                                                                    </a> </li>
                                <li> <strong> Opening: </strong> <br> {metadata['opening_time'] if metadata['opening_time'] else "❔"}  </li>
                            </ul>                        
                        </p>  
                    </div>
                </div>
            </div>
        """

        cards_html.append(card_html)

    all_cards_html = "\n".join(cards_html)
    return all_cards_html


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
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=768
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
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=1024
        )
    return chat_completion.choices[0].message.content


# def extract_dict_from_llm_answer(llm_answer):
#     start_index = llm_answer.find('{')
#     end_index = llm_answer.rfind('}')
    
#     if start_index == -1 or end_index == -1:
#         return llm_answer  # Return an empty dictionary if no valid dictionary found
    
#     dict_str = llm_answer[start_index:end_index+1]
    
#     try:
#         extracted_dict = ast.literal_eval(dict_str)
#         if isinstance(extracted_dict, dict):
#             return extracted_dict
#         else:
#             return {}  # Return an empty dictionary if the extracted content is not a dictionary
#     except (SyntaxError, ValueError):
#         return llm_answer # Return an empty dictionary in case of any errors
