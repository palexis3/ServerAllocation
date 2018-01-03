import os
import time
import re
from slackclient import SlackClient


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
serverbot_id = None
user_id = None

# constants
RTM_READ_DELAY = 1
SERVER_COMMAND = "allocate"
FREE_COMMAND = "free"
MENTION_REGEX = "^<@(|[WU].+)>(.*)"
STAGING_SERVERS = ["release", "core", "platform", "qa", "collaboration"]


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot parse_bot_commands
        If a bot command is found, this function returns a tuple of command and channel.
        If it's not found, then this function return None, None
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == serverbot_id:
                return message, event["channel"]
    return None, None


def parse_direct_mention(message_text):
    """
        Finds a direct mention in message text and returns the user ID which was mentioned.
        If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def find_vacant_server():
    """
        Finds a server that is currently not in use. Returns None if all servers are being occupied
    """
    return None

def contactServerConsumers():
    """
        Contacts all users of current servers and asks them if they're done with the current allocated server
    """

def getUserServer(user_id):
    """
        Finds the server that this user is currently using
    """
    return None

def updateUser(command, user_id):
    """
        Updates the User and Server they're currently using based on their command
    """


def handle_command(command, channel):

    """
        Executes bot command if the command is known
    """

    command = command.lower()
    default_response = "Not sure what you mean by %s. Try using 'allocate' and 'free' commands" % command
    response = None
    default_time = 4

    if user_id is not None:
        print("There is a user_id %s" % user_id)

    # This is where you start to implement more commands!
    if command.startswith(SERVER_COMMAND):
        arr = command.split(" ")
        num = arr[1] if len(arr) > 1 else None
        if num is not None:
            default_time = int(num[0])
        vacant_server = find_vacant_server()
        if vacant_server is None:
            contactServerConsumers()
            vacant_server = find_vacant_server()
            if vacant_server is None:
                response = "All servers are currently occupied."
        else:
            updateServer(vacant_server, user_id)
            response = "You have allocated %s.staging for %shrs" % (vacant_server, default_time)
    elif command.startswith(FREE_COMMAND):
        user_server = getUserServer(user_id)
        if user_server is None:
            response = "You were never assigned a server"
        else:
            response = "You have freed %s.staging" % user_server

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Server Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        client = slack_client.api_call("auth.test")
        if client["user"] == "bot":
            serverbot_id = client["user_id"]
        else:
            user_id = client["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
