"""
Alexa skill for dog training, to be ran in AWS lambda.

(c) 2018 Balloon Inc. VOF
Wouter Devriendt
"""

###
### ------------------ Imports ------------------
###

# General imports
import os, sys
from datetime import datetime

# Amazon libraries import
import boto3

# Flask imports
sys.path.insert(0, './lib')

from flask import Flask, json, render_template
from flask_ask import Ask, request, session, question, statement


###
### ------------------ DEBUG ------------------
###

DEBUG = os.environ['DEBUG']


###
### ------------------ Constants for the dog table ------------------
###

# Table name
DOGS_TABLE = "dogs"
# fields
DOG_NAME ="dogName"
PREVIOUS_NAMES="previous_names"
NUMBER_OF_TRAININGS = "number_of_trainings"
NUMBER_OF_RENAMES="number_of_renames"
CREATED_AT="created_at"
UPDATED_AT="updated_at"


###
### ------------------ Constants for last_question session attribute ------------------
###

# Key
LAST_QUESTION = "last_question"
# Values
NOTHING = 0
SHOULD_START_TRAINING = 1
TRAINING_CONFIRMATION = 2
MALE_OR_FEMALE = 3



###
### --------------- DynamoDB Init and Flask Init ------------------
###

dynamodb = boto3.resource('dynamodb')
dogs_table = dynamodb.Table(DOGS_TABLE)

app = Flask(__name__)
ask = Ask(app, '/')


#
# Session management
#

@ask.on_session_started
def start_session():
    """
    Fired at the start of the session, this is a great place to initialise state variables and the like.
    """
    print("Session started at {}".format(datetime.now().isoformat()))

@ask.session_ended
def session_ended():
    return statement("")

@ask.launch
def handle_launch():
    welcome_text = render_template('welcome')
    welcome_re_text = render_template('welcome_re')
    welcome_card_text = render_template('welcome_card')

    return question(welcome_text).reprompt(welcome_re_text).standard_card(title="Dog Trainer",                                                                        text=welcome_card_text)

#
# Intents
#

@ask.intent('AMAZON.StopIntent')
def handle_stop():
    farewell_text = render_template('stop_bye')
    return statement(farewell_text)


@ask.intent('AMAZON.CancelIntent')
def handle_cancel():
    farewell_text = render_template('cancel_bye')
    return statement(farewell_text)

@ask.intent('AMAZON.HelpIntent')
def handle_help():
    help_text = render_template('help_text')
    return question(help_text).simple_card('Hello', speech_text)

@ask.intent('AMAZON.NoIntent')
def handle_no():
    pass

@ask.intent('AMAZON.YesIntent')
def handle_yes():
    pass

###
### --------------- DB Getters and setters --------------- 
###

def getDogFromDynamoDB(user):
    try:
        response = dogs_table.get_item(Key={ 'account': user })
        return response['Item']['dog']
    except Exception as e:
        print("exception while getting dog: ")
        print(e)
        return None


def saveDogToDynamoDB(dog, user):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not CREATED_AT in dog:
        dog[CREATED_AT] = now
    dog[UPDATED_AT] = now

    try:
        dogs_table.put_item(Item={'account':user,'dog':dog })
        return dog
    except Exception as e:
        print("exception while saving dog: ")
        print(e)
        return None

# 
# Main handler: lambda_handler for lambda, app.run for debugging
# 

def lambda_handler(event, _context):
    return ask.run_aws_lambda(event)

if __name__ == '__main__':
    app.run(debug=True)
