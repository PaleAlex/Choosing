import numpy as np
import pandas as pd
#from groq import Groq
import geocoder

def get_coordinates(address: str) -> pd.DataFrame:
    g = geocoder.osm(address)
    lat = g.latlng[0]
    long = g.latlng[1]
    latlon = pd.DataFrame({
        "lat": [lat],
        "lon": [long]
    })
    return latlon

def get_current_gps_coordinates():
    g = geocoder.ip('me') #this function is used to find the current information using IPAdd
    address = g.address

    g = geocoder.osm(address)
    lat = g.latlng[0]
    long = g.latlng[1]
    latlon = pd.DataFrame({
        "lat": [lat],
        "lon": [long]
    })
    return latlon, address


def create_cards(recommandations_placeids: list, choosing_instance, score_type: str = 'normal'):
    # store card HTML content
    cards_html = []
    price_levels = {
        0: '❔',
        1:'🟩⬜⬜⬜',
        2:'🟩🟨⬜⬜',
        3:'🟩🟨🟧⬜',
        4:'🟩🟨🟧🟥',
    }
    
    for n, place_id in enumerate(recommandations_placeids):

        metadata, _ = choosing_instance.get_metadata_and_reviews(place_id)
        
        price_level = metadata['price_level']
        viz_price_level = price_levels[price_level]

        if score_type == 'normal':
            score = np.round(metadata['score'], 2)
        elif score_type == 'augmented':
            pass
        
        card_html = f"""                              
            <div class="restaurant-card">
                <div class="grid-container">
                    <div class="grid-item">
                        <h1 class="restaurant-name">{n+1}° · {metadata['name']}</h1>
                        <p class="restaurant-info"> <strong>Scores</strong>
                            <ul class="details">
                                <li>Choosing Score: {score} </li>
                                <li>Price level: {viz_price_level} </li> 
                            </ul>
                        </p>
                    </div>
                    <div class="grid-item">
                        <p class="restaurant-info">
                            <ul class="details">
                                <li> <strong> Address: </strong> <a href='https://www.google.com/maps/place/{metadata['vicinity'].replace("/","")}'> {metadata['vicinity']} </a> </li>
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