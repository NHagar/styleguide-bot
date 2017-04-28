# -*- coding: UTF-8 -*-
import os
import pickle
import difflib
from slackeventsapi import SlackEventAdapter
from slackclient import SlackClient

SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CLIENT = SlackClient(SLACK_BOT_TOKEN)

slack_events_adapter = SlackEventAdapter(SLACK_VERIFICATION_TOKEN, endpoint="/slack_events")
styleguide = pickle.load(open('style_guide', 'rb'))

@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    if 'Horace' in message.get('text'):
        text = message.get('text').split(' ')
        text.remove('Horace')
        text = ' '.join(text)
        response = styleguide.get(text.lower())
        if response != None:
            channel = message["channel"]
            message = response
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)
        else:
            keys = list(styleguide.keys())
            suggestions = difflib.get_close_matches(text, keys)
            for i in keys:
                if text in i:
                    suggestions.append(i)
            suggestions = [i for i in suggestions]
            suggestions = list(set(suggestions))
            channel = message["channel"]
            message = "I don't have an entry for %s, try one of these: %s" % (text, suggestions)
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)

slack_events_adapter.start(port=3000)
