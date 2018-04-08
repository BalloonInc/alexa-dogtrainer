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
import logging

# Amazon libraries import
import boto3

# Flask imports
sys.path.append('./lib')

from flask import Flask, json, render_template
from flask_ask import Ask, request, session, question, statement, delegate


###
### ------------------ DEBUG ------------------
###

try:
    DEBUG = os.environ['DEBUG']
except:
    DEBUG = 0

if DEBUG:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
else:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


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
DOG_NAME_ASKED = 3
MALE_OR_FEMALE = 4


###
### --------------- DynamoDB Init and Flask Init ------------------
###

dynamodb = boto3.resource('dynamodb')
dogs_table = dynamodb.Table(DOGS_TABLE)

app = Flask(__name__)
ask = Ask(app, '/')


###
### Session management
###

@ask.on_session_started
def start_session():
    logging.info("Session started at {}".format(datetime.now().isoformat()))

@ask.session_ended
def session_ended():
    return statement("")

@ask.launch
def handle_launch():
    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

    speech_output = render_template('welcome')
    reprompt = render_template('welcome_re')
    card_title = render_template('welcome_card_title')
    card_content = render_template('welcome_card_content')

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)


###
### Intents
###

@ask.intent('AMAZON.StopIntent')
def handle_stop():
    return endSession()

@ask.intent('AMAZON.CancelIntent')
def handle_cancel():
    return endSession()

@ask.intent('AMAZON.HelpIntent')
def handle_help():
    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

    speech_output = render_template('help_text')
    reprompt = render_template('should_start_training')
    card_title = render_template('help_card_title')
    return question(speech_output).reprompt(reprompt).simple_card(card_title, speech_output)

@ask.intent('AMAZON.NoIntent')
def handle_no():
    return endSession()

@ask.intent('AMAZON.YesIntent')
def handle_yes():
    if LAST_QUESTION in session.attributes:
        last_question =session.attributes[LAST_QUESTION]
        logging.info("Last question was: {}".format(last_question) )
        if last_question == SHOULD_START_TRAINING:
            return startTrainingHandler(None)
        elif last_question == TRAINING_CONFIRMATION:
            return train(None)
        elif last_question == DOG_NAME_ASKED:
            return setDogNameHandler(None)
        else:
            return endSession()
    else:
        logging.error("Unknown last question")
        return endSession()

@ask.intent('SetDogNameIntent', mapping={'dogNameFromIntent': 'Dog'})
def setDogNameHandler(dogNameFromIntent):
    if not dogNameFromIntent:
        return delegate()

    saveDogNameForUser(dogNameFromIntent, session.user.userId)
    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

    speech_output = render_template('dog_name_set', dog=dogNameFromIntent)
    reprompt = render_template('should_start_training')
    card_title = render_template('dog_name_set_card_title', dog=dogNameFromIntent)
    card_content = render_template('dog_name_set_card_content', dog=dogNameFromIntent)

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

@ask.intent('StartTrainingIntent', mapping={'dogNameFromIntent': 'Dog'})
def startTrainingHandler(dogNameFromIntent):
    dogFromDynamoDB = getDogFromDynamoDB(session.user.userId)

    # If we don't know the dogname at all, ask again
    if not (dogNameFromIntent or dogFromDynamoDB):
        return delegate()
    # If it is in the DB, but not in the intent, just get it from the DB
    if not dogNameFromIntent:
        dog = dogFromDynamoDB
    # If it is in the intent, use that one and update DB if needed:
    else:
        dog = saveDogNameForUser(dogNameFromIntent, user)

    if dog[NUMBER_OF_TRAININGS] < 2:
        return explainAndAskConfirmation(dog)

    else:
        return train(dog)

def train(dog):
    if not dog:
        dog = getDogFromDynamoDB(session.user.userId)

    sex = render_template('boy')
    
    dog[NUMBER_OF_TRAININGS] += 1
    saveDogToDynamoDB(dog, session.user.userId)
    session.attributes[LAST_QUESTION]=SHOULD_START_TRAINING

    speech_output = render_template('training', dog=dog[DOG_NAME], sex=sex)
    reprompt = render_template('train_again')
    card_title = render_template('training_card_title')
    card_content = render_template('training_card_content', dog=dog[DOG_NAME])

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

def explainAndAskConfirmation(dog):
    session.attributes[LAST_QUESTION]=TRAINING_CONFIRMATION

    speech_output = render_template('training_confirmation', dog=dog[DOG_NAME])
    reprompt = render_template('ready_to_start_training')
    card_title = render_template('training_confirmation_card_title')
    card_content = render_template('training_confirmation_card_content', dog=dog[DOG_NAME])

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

def endSession():
    dog = getDogFromDynamoDB(session.user.userId)
    if dog:
        who_had_fun = dog[DOG_NAME]
        optional_name = " " + who_had_fun
    else:
        who_had_fun = render_template('you')
        optional_name = ""
        
    speech_output = render_template('stop')
    card_title = render_template('stop_card_title', someone=optional_name)
    card_content = render_template('stop_card_content', name=who_had_fun)

    return statement(speech_output).simple_card(card_title, card_content)

###
### ---------------  Local Helpers ---------------
###

def saveDogNameForUser(dogName, user):
    dog = getDogFromDynamoDB(user)

    # Dog does not yet exist in DB
    if not dog:
        dog = {
            NUMBER_OF_TRAININGS:0,
            NUMBER_OF_RENAMES:0,
            PREVIOUS_NAMES:[],
            DOG_NAME:dogName
        }
        return saveDogToDynamoDB(dog, user)

    # Name has changed, update
    if dog[DOG_NAME].lower() != dogName.lower():
        dog[NUMBER_OF_RENAMES] += 1
        dog[PREVIOUS_NAMES].append(dog[DOG_NAME])
        dog[DOG_NAME] = dogName
        return saveDogToDynamoDB(dog, user)
    # Nothing changed, don't update
    return dog


###
### --------------- DB Getters and setters --------------- 
###

def getDogFromDynamoDB(user):
    try:
        response = dogs_table.get_item(Key={ 'account': user })
        return response['Item']['dog']
    except Exception as e:
        logging.error("exception while getting dog: ")
        logging.error(e)
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
        logging.error("exception while saving dog: ")
        logging.error(e)
        return None

### 
### Main handler: lambda_handler for lambda, app.run for debugging
###

def lambda_handler(event, _context):
    return ask.run_aws_lambda(event)

if __name__ == '__main__':
    app.run(debug=True)
