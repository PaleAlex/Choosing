from dotenv import load_dotenv
import os
import redis

# Load environment variables from .env file
load_dotenv()

# Access the env variables
maps_api_key = os.getenv('GOOGLE_MAPS')
groq_api_key = os.getenv('GROQ')
redis_password = os.getenv('REDIS_PASSWORD')

redis_client = redis.Redis(
    host='redis-13928.c73.us-east-1-2.ec2.cloud.redislabs.com',
    port=13928,
    username="default",
    password=redis_password,
    decode_responses=True
)
