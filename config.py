import os
from google.cloud import storage
api_key = os.environ['API_KEY_MAPS']
PATH = os.path.join(os.getcwd(), 'skilled-bonus-284420-d6d56288fa20.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = PATH
storage_client = storage.Client(PATH)
bucket = storage_client.get_bucket('choosing-storage')
#root = "root_user"