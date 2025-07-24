import discord
from discord.ext import tasks
import tweepy
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("discord_token")
TWITTER_BEARER_TOKEN = os.getenv("twitter_bearer_token")
DISCORD_CHANNEL_ID = int(os.getenv("discord_channel_id"))
TWITTER_USERNAME = os.getenv("twitter_username")

intents = discord.Intents.default()
intents.message_content = True

class TweetBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        self.last_tweet_id = self.load_last_tweet_id()

    def load_last_tweet_id(self):
        """Load the last posted tweet ID from file"""
        try:
            if os.path.exists('last_tweet_id.json'):
                with open('last_tweet_id.json', 'r') as f:
                    data = json.load(f)
                    return data.get('last_tweet_id')
        except Exception as e:
            print(f"Error loading last tweet ID: {e}")
        return None

    def save_last_tweet_id(self, tweet_id):
        """Save the last posted tweet ID to file"""
        try:
            with open('last_tweet_id.json', 'w') as f:
                json.dump({'last_tweet_id': tweet_id}, f)
        except Exception as e:
            print(f"Error saving last tweet ID: {e}")

    async def is_tweet_already_posted(self, channel, tweet_id):
        """Check if a tweet was already posted in the channel"""
        try:
            async for message in channel.history(limit=50):
                if message.author == self.user and f"/status/{tweet_id}" in message.content:
                    return True
        except Exception as e:
            print(f"Error checking channel history: {e}")
        return False

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
        

        if not self.check_tweets.is_running():
            self.check_tweets.start()

    @tasks.loop(minutes=120) 
    async def check_tweets(self):
        try:
            channel = self.get_channel(DISCORD_CHANNEL_ID)
            if not channel:
                print(f"Could not find channel with ID {DISCORD_CHANNEL_ID}")
                return

            user = self.twitter_client.get_user(username=TWITTER_USERNAME)
            if not user.data:
                print(f"Could not find Twitter user: {TWITTER_USERNAME}")
                return

            tweets = self.twitter_client.get_users_tweets(
                user.data.id, 
                max_results=5,
                tweet_fields=['created_at']
            )

            if tweets and tweets.data:
                for tweet in reversed(tweets.data):
                    should_post = self.last_tweet_id is None or tweet.id > self.last_tweet_id
                    
                    if should_post:
                        already_posted = await self.is_tweet_already_posted(channel, tweet.id)
                        if already_posted:
                            print(f"Tweet {tweet.id} already found in channel, skipping")
                            continue
                    
                    if should_post:
                        tweet_url = f"https://x.com/{TWITTER_USERNAME}/status/{tweet.id}"
                        await channel.send(f"New tweet from @{TWITTER_USERNAME}:\n{tweet_url}")
                        self.last_tweet_id = tweet.id
                        self.save_last_tweet_id(tweet.id)  
                        print(f"Posted tweet: {tweet.id}")
                        
                        await asyncio.sleep(1)

        except tweepy.TooManyRequests:
            print("Twitter API rate limit exceeded. Waiting longer...")
            await asyncio.sleep(500)  
        except tweepy.Unauthorized:
            print("Twitter API unauthorized. Check your bearer token.")
        except Exception as e:
            print(f"Error fetching tweets: {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.wait_until_ready()

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.lower() == '!ping':
            await message.channel.send('Pong! Bot is working!')

client = TweetBot(intents=intents)

if __name__ == "__main__":
    try:
        client.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Invalid Discord token!")
    except Exception as e:
        print(f"An error occurred: {e}")