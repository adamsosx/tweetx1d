import tweepy
import requests
import json
import os # Dodano import os do odczytu zmiennych środowiskowych
from datetime import datetime
import logging

LOG_FILENAME = 'bot.log' # Możesz rozważyć zmianę nazwy pliku logu, jeśli chcesz
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME),
        logging.StreamHandler() # Dodatkowo loguje do konsoli, przydatne w GitHub Actions
    ]
)

API_KEY_ENV = os.getenv("TWITTER_API_KEY")
API_SECRET_ENV = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN_ENV = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET_ENV = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")


RADAR_API_URL = "https://radar.fun/api/tokens/most-called?timeframe=1d"

def get_top_tokens():
    """Pobiera dane z API radar.fun i zwraca top 3 tokeny"""
    logging.info(f"Fetching top tokens from {RADAR_API_URL}")
    try:
        response = requests.get(RADAR_API_URL, verify=False, timeout=30) # Dodano timeout
        response.raise_for_status()  # Wywoła wyjątek dla kodów błędu HTTP (4xx lub 5xx)
        data = response.json()
        
        if not isinstance(data, list):
            logging.error(f"Unexpected data format from API. Expected list, got {type(data)}.")
            return None

        sorted_tokens = sorted(data, key=lambda x: x.get('unique_channels', 0), reverse=True)
        
        top_3 = sorted_tokens[:3]
        logging.info(f"Successfully fetched and sorted top {len(top_3)} tokens.")
        return top_3
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from radar.fun API (RequestException): {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from radar.fun API: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred in get_top_tokens: {e}")
        return None

def format_tweet(top_3_tokens):
    """Format tweet with top 3 tokens"""
    tweet = "Top3 Most Called Tokens (1d)\n\n" # Zmieniono z 6h na 1d, aby pasowało do RADAR_API_URL
    
    for i, token in enumerate(top_3_tokens, 1):
        calls = token.get('unique_channels', 0) 
        symbol = token.get('symbol', 'Unknown')
        address = token.get('address', 'No Address Provided') 
        
        # Format: "1. $symbol"
        tweet += f"{i}. ${symbol}\n"
        
        # Format: "   {address}"
        tweet += f"   {address}\n"
        
        # Format: "   X calls" with two newlines after
        tweet += f"   {calls} calls\n\n"
    
    tweet += "Source 👇" # Zmieniono, aby pasowało do formatu drugiego skryptu
    
    return tweet

def format_link_tweet():
    """Format the link tweet"""
    return "🔗 https://outlight.fun/\n#SOL #Outlight"

def main():
    logging.info("Starting X Bot (single run for scheduled task)...")
    
    if not all([API_KEY_ENV, API_SECRET_ENV, ACCESS_TOKEN_ENV, ACCESS_TOKEN_SECRET_ENV]):
        logging.error("Twitter API credentials not found in environment variables. Exiting.")
        print("Error: Twitter API credentials (TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET) must be set as environment variables.")
        exit(1) # Zakończ z błędem

    try:
        client = tweepy.Client(
            consumer_key=API_KEY_ENV,
            consumer_secret=API_SECRET_ENV,
            access_token=ACCESS_TOKEN_ENV,
            access_token_secret=ACCESS_TOKEN_SECRET_ENV
        )
        me_response = client.get_me() # Zmieniono nazwę zmiennej, aby uniknąć konfliktu z modułem
        if not me_response or not me_response.data:
            logging.error("Could not retrieve authenticated user data from Twitter.")
            exit(1)
        me_data = me_response.data
        logging.info(f"Successfully authenticated with Twitter as @{me_data.username}")
    except Exception as e:
        logging.error(f"Error creating Twitter client or authenticating: {e}")
        exit(1) # Zakończ z błędem

    try:
        # Pobierz top 3 tokeny
        top_3 = get_top_tokens()
        if not top_3:
            logging.error("Failed to fetch data from API or no data to process. Exiting.")
            exit(1) # Zakończ z błędem

        # Utwórz główny tweet
        main_tweet_text = format_tweet(top_3)
        logging.info("Prepared main tweet:\n" + "="*20 + f"\n{main_tweet_text}\n" + "="*20)

        # Wyślij główny tweet
        logging.info("Sending main tweet...")
        main_tweet_response = client.create_tweet(text=main_tweet_text)
        main_tweet_id = main_tweet_response.data['id']
        logging.info(f"Main tweet sent successfully! Tweet ID: {main_tweet_id}, Link: https://twitter.com/{me_data.username}/status/{main_tweet_id}")
        
        # Przygotuj i wyślij odpowiedź z linkiem
        link_tweet_text = format_link_tweet()
        logging.info("Prepared link tweet (reply):\n" + "="*20 + f"\n{link_tweet_text}\n" + "="*20)
        
        logging.info("Sending link tweet as reply...")
        link_tweet_response = client.create_tweet(
            text=link_tweet_text,
            in_reply_to_tweet_id=main_tweet_id
        )
        link_tweet_id = link_tweet_response.data['id']
        logging.info(f"Link tweet sent as reply! Tweet ID: {link_tweet_id}, Link: https://twitter.com/{me_data.username}/status/{link_tweet_id}")
        
    except tweepy.TweepyException as e:
        logging.error(f"Twitter API error during tweet process: {e}")
        # Można dodać bardziej szczegółową obsługę błędów Tweepy, np. duplikaty
        exit(1) # Zakończ z błędem
    except Exception as e:
        logging.error(f"An unexpected error occurred in the main task: {e}")
        exit(1) # Zakończ z błędem

    logging.info("X Bot (single run) finished successfully.")

if __name__ == "__main__":
    main()
