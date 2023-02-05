import os
from google.cloud import storage
from google.oauth2 import service_account
import json

api_key = os.environ.get("GOOGLE_MAPS")
#root = "root_user"

json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

# generate json - if there are errors here remove newlines in .env
json_data = json.loads(json_str)
# the private_key needs to replace \n parsed as string literal with escaped newlines
json_data['private_key'] = json_data['private_key'].replace('\\n', '\n')

# use service_account to generate credentials object
credentials = service_account.Credentials.from_service_account_info(
    json_data)

# pass credentials AND project name to new client object (did not work wihout project name)
storage_client = storage.Client(credentials=credentials)

bucket = storage_client.get_bucket('choosing-storage')