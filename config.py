from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Access the env variables
maps_api_key = os.getenv('GOOGLE_MAPS')
groq_api_key = os.getenv('GROQ')
