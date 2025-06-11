import tweepy
import requests
import json
import os # Dodano import os do odczytu zmiennych środowiskowych
from datetime import datetime
import logging
from tweepy import OAuth1UserHandler, API

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


OUTLIGHT_API_URL = "https://outlight.fun/api/tokens/most-called?timeframe=1d"

def get_top_tokens():
    """Pobiera dane z API outlight.fun i zwraca top 3 tokeny, licząc tylko kanały z win_rate > 30%"""
    try:
        response = requests.get(OUTLIGHT_API_URL, verify=False)
        response.raise_for_status()
        data = response.json()

        tokens_with_filtered_calls = []
        for token in data:
            channel_calls = token.get('channel_calls', [])
            # Licz tylko kanały z win_rate > 30%
            calls_above_30 = [call for call in channel_calls if call.get('win_rate', 0) > 30]
            count_calls = len(calls_above_30)
            if count_calls > 0:
                token_copy = token.copy()
                token_copy['filtered_calls'] = count_calls
                tokens_with_filtered_calls.append(token_copy)

        # Sortuj po liczbie filtered_calls malejąco
        sorted_tokens = sorted(tokens_with_filtered_calls, key=lambda x: x.get('filtered_calls', 0), reverse=True)
        top_3 = sorted_tokens[:3]
        return top_3
    except Exception as e:
        logging.error(f"Unexpected error in get_top_tokens: {e}")
        return None

def format_tweet(top_3_tokens):
    """Format tweet with top 3 tokens (tylko calls z win_rate > 30%)"""
    tweet = f"🚀Top 3 Most Called Tokens (1d)\n\n"
    medals = ['🥇', '🥈', '🥉']
    for i, token in enumerate(top_3_tokens, 0):
        calls = token.get('filtered_calls', 0)
        symbol = token.get('symbol', 'Unknown')
        address = token.get('address', 'No Address Provided')
        medal = medals[i] if i < len(medals) else f"{i+1}."
        tweet += f"{medal}${symbol}\n"
        tweet += f"{address}\n"
        tweet += f"{calls} calls\n\n"
    tweet = tweet.rstrip('\n')
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
        me_response = client.get_me()
        if not me_response or not me_response.data:
            logging.error("Could not retrieve authenticated user data from Twitter.")
            exit(1)
        me_data = me_response.data
        logging.info(f"Successfully authenticated with Twitter as @{me_data.username}")

        # Klient v1.1 do uploadu grafiki
        auth_v1 = OAuth1UserHandler(API_KEY_ENV, API_SECRET_ENV, ACCESS_TOKEN_ENV, ACCESS_TOKEN_SECRET_ENV)
        api_v1 = API(auth_v1)
    except Exception as e:
        logging.error(f"Error creating Twitter client or authenticating: {e}")
        exit(1)

    try:
        # Pobierz top 3 tokeny
        top_3 = get_top_tokens()
        if not top_3:
            logging.error("Failed to fetch data from API or no data to process. Exiting.")
            exit(1)

        # Utwórz główny tweet
        main_tweet_text = format_tweet(top_3)
        logging.info("Prepared main tweet:\n" + "="*20 + f"\n{main_tweet_text}\n" + "="*20)

        # --- Dodanie grafiki do głównego tweeta ---
        image_path = os.path.join("images", "msgtwt.png")
        if not os.path.isfile(image_path):
            logging.error(f"Image file not found: {image_path}. Sending tweet without image.")
            media_id = None
        else:
            try:
                media = api_v1.media_upload(image_path)
                media_id = media.media_id
                logging.info(f"Image uploaded successfully. Media ID: {media_id}")
            except Exception as e:
                logging.error(f"Error uploading image: {e}. Sending tweet without image.")
                media_id = None

        # Wyślij główny tweet z grafiką (jeśli się udało)
        if media_id:
            main_tweet_response = client.create_tweet(text=main_tweet_text, media_ids=[media_id])
        else:
            main_tweet_response = client.create_tweet(text=main_tweet_text)
        main_tweet_id = main_tweet_response.data['id']
        logging.info(f"Main tweet sent successfully! Tweet ID: {main_tweet_id}, Link: https://twitter.com/{me_data.username}/status/{main_tweet_id}")
        
        # Przygotuj i wyślij odpowiedź z linkiem
        link_tweet_text = format_link_tweet()
        logging.info("Prepared link tweet (reply):\n" + "="*20 + f"\n{link_tweet_text}\n" + "="*20)

        # --- Dodanie grafiki do odpowiedzi ---
        reply_image_path = os.path.join("images", "msgtwtft.png")
        if not os.path.isfile(reply_image_path):
            logging.error(f"Reply image file not found: {reply_image_path}. Sending reply without image.")
            reply_media_id = None
        else:
            try:
                reply_media = api_v1.media_upload(reply_image_path)
                reply_media_id = reply_media.media_id
                logging.info(f"Reply image uploaded successfully. Media ID: {reply_media_id}")
            except Exception as e:
                logging.error(f"Error uploading reply image: {e}. Sending reply without image.")
                reply_media_id = None

        if reply_media_id:
            link_tweet_response = client.create_tweet(
                text=link_tweet_text,
                in_reply_to_tweet_id=main_tweet_id,
                media_ids=[reply_media_id]
            )
        else:
            link_tweet_response = client.create_tweet(
                text=link_tweet_text,
                in_reply_to_tweet_id=main_tweet_id
            )
        link_tweet_id = link_tweet_response.data['id']
        logging.info(f"Link tweet sent as reply! Tweet ID: {link_tweet_id}, Link: https://twitter.com/{me_data.username}/status/{link_tweet_id}")
        
    except tweepy.TweepyException as e:
        logging.error(f"Twitter API error during tweet process: {e}")
        exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred in the main task: {e}")
        exit(1)

    logging.info("X Bot (single run) finished successfully.")

if __name__ == "__main__":
    main()
