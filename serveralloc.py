import os
import time
import re
from slackclient import SlackClient
from datetime import datetime
from datetime import timedelta
from Person import Person
import threading

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
serverbot_id = None
user_id = None
non_vacant_servers = []
users_dict = {}
users_timer_dict = {}

# constants
RTM_READ_DELAY = 1
SERVER_COMMAND = "allocate"
FREE_COMMAND = "free"
MENTION_REGEX = "^<@(|[WU].+)>(.*)"
# "core", "platform", "qa", "collaboration", "mobile"
STAGING_SERVERS = ["release"]


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot parse_bot_commands
        If a bot command is found, this function returns a tuple of command and channel.
        If it's not found, then this function return None, None
    """
    for event in slack_events:
        if event["type"] == "message" and "user" in event:
            s_id, message = parse_direct_mention(event["text"])
            if s_id == serverbot_id:
                return message, event["channel"], event["user"]
    return None, None, None


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
    for server in STAGING_SERVERS:
        if server not in non_vacant_servers:
            return server
    return None



def contactServerConsumers(user, channel, command):
    """
        Contacts all users of current servers and asks them if they're done with the current allocated server
    """
    for user_id in users_dict.keys():
        server = users_dict.get(user_id).getUserServer()
        message = "Hello, are you done with %s.staging?" % server
        send_message(user_id, message, None, channel)




def send_message(user_id, response, default_response, channel):
    """
        Contacts a user with particular message
    """
    if channel is not None:
        slack_client.api_call(
        "chat.postEphemeral",
        channel=channel,
        text=response or default_response,
        user=user_id
        )


def send_channel_message(channel, channel_message):
    """
        Sends a response to the channel
    """
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=channel_message
    )


def getUserServer(user_id):
    """
        Finds the server that this user is currently using
    """
    if user_id in users_dict:
        return users_dict.get(user_id).getUserServer()
    return None


def removeUserServer(user_id):
    """
        Removes this user with the server that they're currently attached to
    """
    if user_id in users_dict:
        server = users_dict.get(user_id).getUserServer()
        non_vacant_servers.remove(server)
        del users_dict[user_id]

    if user_id in users_timer_dict:
        timer = users_timer_dict.get(user_id)
        timer.cancel()
        del users_timer_dict[user_id]


def updateUserServer(server, user_id, server_time):
    """
        Sets this server as occupied and updates the respective user's info
    """
    now = datetime.now()
    run_at = now + timedelta(hours=server_time)
    delay = (run_at - now).total_seconds()

    # Setup a scheduler to remove a user based on timing
    timer = threading.Timer(delay, removeUserServer(user_id))
    timer.start()

    non_vacant_servers.append(server)
    users_dict[user_id] = Person(user_id, server)
    users_timer_dict[user_id] = timer


def handle_commands(command, channel, user_id):
    """
        Executes bot command if the command is known
    """
    command = command.lower()
    default_response = "Not sure what you mean by %s. Try using 'allocate' and 'free' commands." % command
    response = None
    server_time = 4

    if command.startswith(SERVER_COMMAND):
        arr = command.split(" ")
        num = arr[1] if len(arr) > 1 else None
        if num is not None:
            server_time = int(num[0])
        vacant_server = find_vacant_server()
        if vacant_server is None:
            contactServerConsumers(user_id, channel, command)
            response = "All servers are currently occupied. Wait while we contact all server holders..."
        else:
            updateUserServer(vacant_server, user_id, server_time)
            channel_message = "%s.staging has been allocated!" % vacant_server
            send_channel_message(channel, channel_message)
            response = "You have allocated %s.staging for %shrs." % (vacant_server, server_time)
    elif command.startswith(FREE_COMMAND):
        user_server = getUserServer(user_id)
        if user_server is None:
            response = "You currently do not have an assigned server to free."
        else:
            removeUserServer(user_id)
            response = "You have freed %s.staging." % user_server
            channel_message = "%s.staging is now free!" % user_server
            send_channel_message(channel, channel_message)
    elif command[0] == "y" or command[0] == "n":
        user_server = getUserServer(user_id)
        if command[0] == "y" and user_server is not None:
            removeUserServer(user_id)
            response = "Great! You have freed %s.staging." % user_server
            channel_message = "%s.staging is now free!" % user_server
            send_channel_message(channel, channel_message)
        elif command[0] == "n" and user_server is not None:
            response = "Thank you! You still hold %s.staging." % user_server

    send_message(user_id, response, default_response, channel)

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Server Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        serverbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel, u_id = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_commands(command, channel, u_id)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
