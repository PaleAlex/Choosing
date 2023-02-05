import config
from module import *
import numpy as np
import requests
import json
from datetime import datetime
import geocoder


class Choosing():

    def __init__(self, username, meal, city, province, state, epp, border="comune"):
        self.username = username
        self.meal = meal
        self.city = city
        self.province = province
        self.state = state
        self.epp = epp
        self.border = border

    def coord(self):
        g = geocoder.osm(f'{self.city}, {self.province}, {self.state}')
        json_info = g.json
        if self.border == 'comune':
            lat = json_info['lat']
            long = json_info['lng']
            return [lat, long]
        else:
            lat = np.random.uniform(low=json_info['bbox']['southwest'][0], high=json_info['bbox']['northeast'][0], size=1)[0]
            long = np.random.uniform(low=json_info['bbox']['southwest'][1], high=json_info['bbox']['northeast'][1], size=1)[0]
            return [round(lat, 7), round(long, 7)]

    def read_temp(self):
        try:
            temp = read_usertemp(self.username)
            return temp
        except:
            return pd.DataFrame(columns=["place_id", "name", "lat", "lng", "rating", "n_rating", "vicinity"])

    def random_restaurants(self, radius=3500, keyword='restaurant'):
        if len(self.read_temp()) == 0:
            api_key = config.api_key
            possibilities = []
            coordinates = self.coord()
            url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location='+str(coordinates[0])+'%2C'+str(coordinates[1])+'&radius='+str(radius)+'&keyword='+str(keyword)+'&key='+str(api_key)
            respon = requests.get(url)
            jj = json.loads(respon.text)
            self.results = jj['results']
            for result in self.results:
                place_id = result['place_id']
                name = result['name']
                lat = result['geometry']['location']['lat']
                lng = result['geometry']['location']['lng']
                rating = result['rating']
                n_rating = result['user_ratings_total']
                vicinity = result['vicinity']
                if 0 in [rating, n_rating]:
                    continue
                data = [place_id, name, lat, lng, rating, n_rating, vicinity]
                possibilities.append(data)
            possibilities = sorted(possibilities, key=lambda x: x[4] * np.log(0.001+np.sqrt(x[5])), reverse=True)[:8]
            df = pd.DataFrame(data=possibilities, columns=["place_id", "name", "lat", "lng", "rating", "n_rating", "vicinity"])
            df.to_csv(f"user_temps/temp_{self.username}.csv", encoding="utf-8")
            filename = f"user_temps/temp_{self.username}.csv"
            upload(filename)
            return df
        else:
            df = self.read_temp()
            return df

    def random_choice(self, choice=0):
        posss = self.random_restaurants()
        selected = [posss.iloc[choice, 1], posss.iloc[choice, 6]]
        lat = posss.iloc[choice, 2]
        lng = posss.iloc[choice, 3]
        to_append = pd.DataFrame(columns=['name', 'vicinity'])
        to_append.loc[0] = selected
        to_append["pr"] = self.province
        to_append["added"] = datetime.date(datetime.now())
        to_append["user"] = self.username
        return to_append, pd.DataFrame(data = {'lat': [lat], 'lon': [lng]})

    def inv_index(self):
        ii = {}

        final = read_final().reset_index(drop= True)

        final_w_meal = final[ (final["what"].isin(self.meal) )]

        for us in set(final_w_meal["user"]):
            ii_user = {}
            final_w_meal_user = final_w_meal[final_w_meal["user"] == us]

            for r in range(len(final_w_meal_user)):
                if self.border == 'comune': #distinzione è nella ricerca, se match è in un ristorante in provincia o in comune. da capire meglio
                    try:
                        cit = final_w_meal_user.iloc[r, 1].split(",")[2].strip().capitalize()

                        if cit == self.city:
                            ii_user[(final_w_meal_user.iloc[r, 0], final_w_meal_user.iloc[r, 1])] = list(final_w_meal_user.iloc[r, [5, 7]])
                    except:
                        prov = final_w_meal_user.iloc[r, 2].upper()

                        if prov == self.province:
                            ii_user[(final_w_meal_user.iloc[r, 0], final_w_meal_user.iloc[r, 1])] = list(final_w_meal_user.iloc[r, [5, 7]])
                else:
                    prov = final_w_meal_user.iloc[r, 2].upper()

                    if prov == self.province:
                        ii_user[(final_w_meal_user.iloc[r, 0], final_w_meal_user.iloc[r, 1])] = list(final_w_meal_user.iloc[r, [5, 7]])

            ii[us] = ii_user

        return ii

    def common_users(self):
        self.index = self.inv_index()
        self.main = set(self.index[self.username].keys())
        comparison = {}

        for k in self.index.keys():
            comp = set(self.index[k].keys())
            inters = self.main & comp
            if len(inters)>0 and len(comp)>len(inters):
                comparison[k] = len(inters)

        return sorted(comparison.items(), key=lambda x: x[1], reverse=True)

    def similarity_score(self):
        cusers = self.common_users()
        scores = {}

        for el in cusers:
            comp = set(self.index[el[0]].keys())
            inters = self.main & comp
            main_rate = np.array([])
            other_rate = np.array([])
            for i in inters:
                main_rate = np.append(main_rate, self.index[self.username][i][0])
                other_rate = np.append(other_rate, self.index[el[0]][i][0])

            scores[el[0]] = np.linalg.norm(main_rate-other_rate)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def matched_suggests(self):
        #qui ci sarà da implementare lo stesso la funzione con il temp
        scores = self.similarity_score()
        alls = list()
        for el in scores:
            other = sorted(self.index[el[0]].items(), key=lambda x: x[1][0]/np.log(10 + x[1][1]), reverse=True)
            for i in other:
                if i[0] in self.main or i[1][0] < 7.5 or not self.epp[0] <= i[1][1] <= self.epp[1]:
                    continue
                alls.append(i)
        return alls

    def matched_choice(self, choice=0):
        als = self.matched_suggests()
        selected = [als[choice][0][0], als[choice][0][1]]
        to_append = pd.DataFrame(columns=['name', 'vicinity'])
        to_append.loc[0] = selected
        to_append["pr"] = self.province
        to_append["added"] = datetime.date(datetime.now())
        to_append["user"] = self.username
        return to_append




