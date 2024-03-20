import config
from module import *

import numpy as np
import requests
import json
import re


class Choosing():
    
    def __init__(self, call_id : str, radius: float, keyword: str, lang: str, coordinates: list):
        self.maps_api_key = config.maps_api_key
        self.call_id = call_id
        self.radius = radius
        self.keyword = keyword
        self.lang = lang
        self.coordinates = coordinates
        self.first_seven_best_suggestions()
        

    def first_seven_best_suggestions(self) -> dict:
            
        possibilities = []
        url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location='+str(self.coordinates[0])+'%2C'+str(self.coordinates[1])+'&radius='+str(self.radius)+'&keyword='+str(self.keyword)+'&key='+str(self.maps_api_key)
        resp = requests.get(url)
        jj = json.loads(resp.text)
        results = jj['results']
        for result in results:
            place_id = result['place_id']
            name = result['name']
            lat = result['geometry']['location']['lat']
            lng = result['geometry']['location']['lng']
            rating = result['rating']
            n_rating = result['user_ratings_total']
            price_level = result.get('price_level', 0)
            vicinity = result['vicinity']
            score = rating * np.log(0.001 + np.sqrt(n_rating))
            
            if 0 in [rating, n_rating]:
                continue
            elif any(word in name for word in ('Donald', 'Roadhouse', 'Burger King', 'Piadineria', 'Salumeria')):
                continue
            elif self.keyword == 'restaurant' and 'Pizzeria' in name:
                continue
            
            data = [place_id, name, lat, lng, rating, n_rating, price_level, vicinity, score]
            possibilities.append(data)


        # Sort the list based on the newly added score
        possibilities = sorted(possibilities, key=lambda x: x[-1], reverse=True)[:7]

        df = pd.DataFrame(data=possibilities, columns=["place_id", "name", "lat", "lng", "rating", "n_rating", 'price_level', "vicinity", "score"])

        self.formatted_df_to_dict = df.set_index("place_id", drop=True).T.to_dict()
        return self.formatted_df_to_dict
        

    def get_metadata_and_reviews(self, place_id:str) -> dict:

        url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={str(place_id)}&language={self.lang}&key={str(self.maps_api_key)}'
        resp = requests.get(url)
        jj = json.loads(resp.text)

        metadata = self.formatted_df_to_dict[place_id]
        address_components = jj.get('result', {}).get('address_components', [])
        metadata['city'] = address_components[2]['long_name'] if len(address_components) > 2 else None

        weekday_opening = jj.get('result', {}).get('current_opening_hours', {}).get('weekday_text', None)
        def remove_special_chars(text):
            return re.sub(r'[\u202f\u2009]', '', text)
        try:
            formatted_weekday_opening = [remove_special_chars(string) for string in weekday_opening]
            metadata['opening_time'] = "<br>".join(formatted_weekday_opening)
        except TypeError:
            metadata['opening_time'] = None


        metadata['phone_number'] = jj.get('result', {}).get('international_phone_number', None)

        reviews = jj.get('result', {}).get('reviews', [])

        extracted_review_info = [
            {
            'id': str(r['author_name']).replace(' ', '').lower()+str(r['time']),
            'language' : r['original_language'],
            'text' : r['text'].replace('\n', '').replace('\\',''),
            'time': r['time']
            }
            for r in reviews]

        return metadata, extracted_review_info
    
    def build_dataset(self):
        dataset = dict()
        for place_id in self.formatted_df_to_dict.keys():
            metadata, reviews  = self.get_metadata_and_reviews(place_id)
            restaurant_name = metadata['name']
            formatted_reviews = [r['text'] for r in reviews]
            dataset[restaurant_name] = formatted_reviews
        return dataset




