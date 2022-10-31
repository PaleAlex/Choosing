import os
from google.cloud import storage

api_key = os.getenv("GOOGLE_MAPS")
#PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PATH = os.path.join(os.getcwd(), 'google-credentials.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = PATH
storage_client = storage.Client(PATH)
bucket = storage_client.get_bucket('choosing-storage')
#root = "root_user"