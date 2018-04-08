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

log = logging.getLogger('dogtrainer')

if DEBUG:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    log.info("Debug mode on: log level set to INFO")
else:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)


###
### ------------------ Constants for the dog table ------------------
###

# Table name
DOGS_TABLE = 'dogs'
# fields
DOG_NAME ='dogName'
SEX = 'sex'
PREVIOUS_DOGS='previous_dogs'
NUMBER_OF_TRAININGS = 'number_of_trainings'
NUMBER_OF_RENAMES='number_of_renames'
CREATED_AT='created_at'
UPDATED_AT='updated_at'

# Dog sex enum
MALE = 'male'
FEMALE = 'female'
UNKNOWN = 'unknown'

###
### ------------------ Constants for last_question session attribute ------------------
###

# Key
LAST_QUESTION = 'last_question'
# Values
NOTHING = 0
SHOULD_START_TRAINING = 1
TRAINING_CONFIRMATION = 2
DOG_NAME_ASKED = 3
SEX_ASKED = 4


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
    log.info("Session started at {}".format(datetime.now().isoformat()))

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
        log.info("Last question was: {}".format(last_question) )
        if last_question == SHOULD_START_TRAINING:
            return startTrainingHandler(None, None)
        elif last_question == TRAINING_CONFIRMATION:
            return train(None)
        elif last_question == DOG_NAME_ASKED:
            return setDogNameHandler(None)
        else:
            return endSession()
    else:
        log.error("Unknown last question")
        return endSession()

@ask.intent('SetDogNameIntent', mapping={'dogName': 'Dog'})
def setDogNameHandler(dogName):
    if not dogName:
        log.info("SetDogNameIntent started without filled name slot. Re-asking.")
        return delegate()

    saveDogForUser(session.user.userId, dogName=dogName)
    session.attributes[LAST_QUESTION] = SEX_ASKED

    speech_output = render_template('dog_name_set', dog=dogName)
    reprompt = render_template('ask_sex')
    card_title = render_template('dog_name_set_card_title', dog=dogName)
    card_content = render_template('dog_name_set_card_content', dog=dogName)

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

@ask.intent('SetSexIntent', mapping={'dogName': 'Dog', 'sex': 'Sex'})
def setSex(sex, dogName):
    if not dogName:
        try:
            dogFromDynamoDB = getDogFromDynamoDB(session.user.userId)
            dogName = dogFromDynamoDB[DOG_NAME]
            log.info("Fetched dog name from DB: {}".format(dogName))
        except:
            log.info("SetSexIntent started, but I don't know the name yet. First asking that before asking sex")
            return setDogNameHandler(None)
    else:
        log.info("Dog name taken from intent: {}".format(dogName))
    try:
        sex = getUniqueSlotID(request.intent.slots.Sex)
    except Exception as e:
        log.info("Could not get sex from intent.")
        return delegate()

    saveDogForUser(session.user.userId, dogName=dogName, sex=sex)

    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING
    speech_output = render_template('sex_set', dog=dogName, sex=render_template(sex))
    reprompt = render_template('should_start_training')
    card_title = render_template('dog_name_set_card_title', dog=dogName)
    card_content = render_template('dog_name_set_card_content', dog=dogName)

    return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

@ask.intent('StartTrainingIntent', mapping={'dogName': 'Dog', 'sexFromIntent': 'Sex'})
def startTrainingHandler(dogName, sexFromIntent):
    dogFromDynamoDB = getDogFromDynamoDB(session.user.userId)
    # If we don't know the dogname at all, ask again
    if not dogName:
        try:
            dogName = dogFromDynamoDB[DOG_NAME]
        except:
            log.info("Name not in intent, and dog not in DB. Asking name first.")
            session.attributes[LAST_QUESTION] = DOG_NAME_ASKED
            return delegate()

    if sexFromIntent:
        sex = getUniqueSlotID(request.intent.slots.Sex)
    else:
        try:
            sex = dogFromDynamoDB[SEX]
            assert sex != UNKNOWN
        except:
            session.attributes[LAST_QUESTION] = SEX_ASKED
            log.info("Sex is not known. Asking.")
            request.intent.slots.Dog.value = dogName
            return delegate(updated_intent=request.intent)

    dog = saveDogForUser(session.user.userId, dogName=dogName, sex=sex)

    if dog[NUMBER_OF_TRAININGS] < 2:
        return explainAndAskConfirmation(dog)
    else:
        return train(dog)

def train(dog):
    if not dog:
        dog = getDogFromDynamoDB(session.user.userId)
    
    dog[NUMBER_OF_TRAININGS] += 1
    saveDogToDynamoDB(dog, session.user.userId)
    session.attributes[LAST_QUESTION]=SHOULD_START_TRAINING

    speech_output = render_template('training', dog=dog[DOG_NAME], sex=render_template(dog[SEX]))
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
    try:
        who_had_fun = dog[DOG_NAME]
        optional_name = " " + who_had_fun
    except:
        who_had_fun = render_template('you')
        optional_name = ""
        
    speech_output = render_template('stop')
    card_title = render_template('stop_card_title', someone=optional_name)
    card_content = render_template('stop_card_content', name=who_had_fun)

    return statement(speech_output).simple_card(card_title, card_content)

###
### ---------------  Local Helpers ---------------
###

def saveDogForUser(user, dogName="", sex=UNKNOWN):
    dog = getDogFromDynamoDB(user)

    # Dog does not yet exist in DB
    if not dog:
        dog = {
            NUMBER_OF_TRAININGS:0,
            NUMBER_OF_RENAMES:0,
            PREVIOUS_DOGS:{},
            DOG_NAME: dogName
        }

        if sex:
            log.info("Sex is {}, will set".format(sex))
            dog[SEX] = sex
        else:
            log.info("Sex is not set, will set to {}".format(UNKNOWN))
            dog[SEX] = UNKNOWN

        return saveDogToDynamoDB(dog, user)

    # One time upgrade
    dog = upgrade_v1_to_v2(dog)

    oldDogName = dog[DOG_NAME]
    oldSex = dog[SEX]

    # Name has changed: update
    if dogName and dogName.lower() != oldDogName.lower():
        dog[PREVIOUS_DOGS][oldDogName] = dog[SEX]
        dog[NUMBER_OF_RENAMES] += 1
        dog[DOG_NAME] = dogName

    # Sex has changed: update
    if sex != oldSex and sex != UNKNOWN:
        dog[SEX] = sex

    return saveDogToDynamoDB(dog, user)

# Validates that there is only one 
def getUniqueSlotID(slot):
    assert slot.resolutions.resolutionsPerAuthority[0]['status']['code'] == "ER_SUCCESS_MATCH"
    assert len(slot.resolutions.resolutionsPerAuthority[0]['values']) == 1
    return slot.resolutions.resolutionsPerAuthority[0]['values'][0]['value']['id']

def upgrade_v1_to_v2(dog):
    if not PREVIOUS_DOGS in dog:
        dog[PREVIOUS_DOGS] = {}
    if not SEX in dog:
        log.info("Sex is not set, will set to {}".format(UNKNOWN))
        dog[SEX] = UNKNOWN
    return dog

###
### --------------- DB Getters and setters --------------- 
###

def getDogFromDynamoDB(user):
    try:
        response = dogs_table.get_item(Key={ 'account': user })
        return response['Item']['dog']
    except:
        log.info("No dog found.")
        return None

def saveDogToDynamoDB(dog, user):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not CREATED_AT in dog:
        dog[CREATED_AT] = now
    dog[UPDATED_AT] = now
    log.info("Dog will be saved: ")
    log.info(dog)

    try:
        dogs_table.put_item(Item={'account':user,'dog':dog })
        return dog
    except Exception as e:
        log.error("Exception while saving dog: ")
        log.error(e)
        return None

### 
### Main handler: lambda_handler for lambda, app.run for debugging/ngrok
###

def lambda_handler(event, _context):
    return ask.run_aws_lambda(event)

if __name__ == '__main__':
    app.run(debug=True)
