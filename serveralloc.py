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
current_channel = None
non_vacant_servers = []
users_dict = {}
users_timer_dict = {}


# constants
RTM_READ_DELAY = 1
SERVER_COMMAND = "allocate"
FREE_COMMAND = "free"
MENTION_REGEX = "^<@(|[WU].+)>(.*)"
STAGING_SERVERS = ["release", "core", "platform", "qa", "collaboration", "mobile"]


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot parse_bot_commands
        If a bot command is found, this function returns a tuple of command and channel.
        If it's not found, then this function return None, None
    """
    for event in slack_events:
        if event["type"] == "message" and "user" in event:
            # event["user"], the id of the actual user
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

def contactServerConsumers():
    """
        Contacts all users of current servers and asks them if they're done with the current allocated server
    """
    for user_id in users_dict.keys():
        server = users_dict.get(user_id).getUserServer
        message = "Hello, are you done with %.staging?" % server
        send_message(user_id, message)

def send_message(user_id, message):
    """
        Contacts a user using a particular server asking them if they're done it
    """
    if current_channel is not None:
        slack_client.api_call(
        "chat.postEphemeral",
        channel=current_channel,
        text=message,
        user=user_id
        )



def getUserServer(user_id):
    """
        Finds the server that this user is currently using
    """
    if user_id in users_dict:
        return users_dict.get(user_id).getUserServer()
    return None

# TODO: I think this will probably used for commands asking if someone is done with their server
def handle_user_command(command, user_id):
    """
        Updates the User and Server they're currently using based on their command
    """


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


def updateServer(server, user_id, server_time):
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


def handle_bot_command(command, channel):

    """
        Executes bot command if the command is known
    """
    command = command.lower()
    default_response = "Not sure what you mean by %s. Try using 'allocate' and 'free' commands" % command
    response = None
    server_time = 4

    if user_id is not None:
        print("user_id is %s" % user_id)

    # This is where you start to implement more commands!
    if command.startswith(SERVER_COMMAND):
        arr = command.split(" ")
        num = arr[1] if len(arr) > 1 else None
        if num is not None:
            server_time = int(num[0])
        vacant_server = find_vacant_server()
        if vacant_server is None:
            contactServerConsumers()
            vacant_server = find_vacant_server()
            if vacant_server is None:
                response = "All servers are currently occupied. %s, %s" % (user_id, serverbot_id)
        else:
            updateServer(vacant_server, user_id, server_time)
            response = "You have allocated %s.staging for %shrs" % (vacant_server, server_time)
    elif command.startswith(FREE_COMMAND):
        user_server = getUserServer(user_id)
        if user_server is None:
            response = "You currently do not have an assigned server to free."
        else:
            removeUserServer(user_id)
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
        serverbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel, u_id = parse_bot_commands(slack_client.rtm_read())
            user_id = u_id
            current_channel = channel
            print(current_channel)
            if command:
                handle_bot_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
