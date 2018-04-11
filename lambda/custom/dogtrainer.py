"""
Alexa skill for dog training, to be ran in AWS lambda.

(c) 2018 Balloon Inc. VOF
Wouter Devriendt
"""

###
### ------------------ Imports ------------------
###

# Standard library imports
import os, sys
from datetime import datetime
import logging

# Amazon libraries import
import boto3

# add lib to path for other imports
sys.path.append('./lib')

# other external libs import
import watchtower

# flask imports
from flask import Flask, json, render_template
from flask_ask import Ask, request, session, question, statement, delegate, elicit_slot


###
### ------------------ DEBUG and Logging ------------------
###

try:
    DEBUG = os.environ['DEBUG']
except:
    DEBUG = 0

try:
    TRACE = os.environ['TRACE']
except:
    TRACE = 0

if TRACE:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    logging.info("Debug mode on: log level set to DEBUG")
elif DEBUG:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    logging.info("Debug mode on: log level set to INFO")
else:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

log = logging.getLogger(__name__)
log.addHandler(watchtower.CloudWatchLogHandler())

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

app.logger.addHandler(watchtower.CloudWatchLogHandler())
###
### Session management
###

@ask.on_session_started
def start_session():
    printDebug("Session started at {}".format(datetime.now().isoformat()))

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
        printDebug("Last question was: {}".format(last_question) )
        if last_question == SHOULD_START_TRAINING:
            return startTrainingHandler(None, None)
        elif last_question == TRAINING_CONFIRMATION:
            return train(None)
        elif last_question == DOG_NAME_ASKED:
            return setDogNameHandler(None, None)
        else:
            return endSession()
    else:
        print("Unknown last question")
        return endSession()

@ask.intent('HelloIntent')
def handle_hello():
    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

    speech_output = render_template('hello_text') + " " + render_template('help_text')
    reprompt = render_template('should_start_training')
    card_title = render_template('hello_card_title')
    return question(speech_output).reprompt(reprompt).simple_card(card_title, speech_output)


@ask.intent('SetDogNameIntent', mapping={'dogName': 'Dog', 'sexFromIntent': 'Sex'})
def setDogNameHandler(dogName, sexFromIntent):
    if not dogName:
        printDebug("SetDogNameIntent started without filled name slot. Re-asking.")
        return delegate()

    if sexFromIntent:
        sex = getUniqueSlotID(request.intent.slots.Sex)

        # Sex is given, but is invalid. Explicitely ask for it
        if not sex:
            printDebug("Invalid sex. Re-asking")
            del request.intent.slots.Sex['value']
            del request.intent.slots.Sex['resolutions']
            printDebug("Updated request to remove invalid sex: {}".format(request))
            session.attributes[LAST_QUESTION] = SEX_ASKED
            speech_output = render_template("invalid_sex_ask_again", dog=dogName)
            return elicit_slot("Sex", speech_output, updated_intent=request.intent)
        saveDogForUser(session.user.userId, dogName=dogName, sex=sex)

        speech_output = render_template('dog_name_set_sex_set', dog=dogName, pronoun=render_template(sex+'_pronoun'))
        reprompt = render_template('should_start_training')
        card_title = render_template('dog_name_set_card_title', dog=dogName)
        card_content = render_template('dog_name_set_card_content', dog=dogName)
        session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

        return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

    else:
        try:
            existingDog = getDogFromDynamoDB(session.user.userId)
            oldSex = existingDog[PREVIOUS_DOGS][dogName]
            print(oldSex)
            assert oldSex != UNKNOWN
            saveDogForUser(session.user.userId, dogName=dogName, sex=oldSex)
            session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING

            speech_output = render_template('dog_name_set_again', dog=dogName, pronoun=render_template(oldSex+'_pronoun'))
            reprompt = render_template('should_start_training')
            card_title = render_template('dog_name_set_card_title', dog=dogName)
            card_content = render_template('dog_name_set_again_card_content', dog=dogName)
            return question(speech_output).reprompt(reprompt).simple_card(card_title, card_content)

        except Exception as e:
            printDebug("The old sex was invalid or did not exist, asking again.")
            saveDogForUser(session.user.userId, dogName=dogName, sex=UNKNOWN)
            session.attributes[LAST_QUESTION] = SEX_ASKED
            speech_output = render_template("dog_name_set", dog=dogName)
            return elicit_slot("Sex", speech_output)

@ask.intent('SetSexIntent', mapping={'dogName': 'Dog', 'sexFromIntent': 'Sex'})
def setSex(sexFromIntent, dogName):
    if not dogName:
        try:
            dogFromDynamoDB = getDogFromDynamoDB(session.user.userId)
            dogName = dogFromDynamoDB[DOG_NAME]
            printDebug("Fetched dog name from DB: {}".format(dogName))
        except:
            printDebug("SetSexIntent started, but I don't know the name yet. First asking that before asking sex")
            return setDogNameHandler(None)
    else:
        printDebug("Dog name taken from intent: {}".format(dogName))

    if not sexFromIntent:
        printDebug("Could not get sex from intent.")
        return delegate()

    sex = getUniqueSlotID(request.intent.slots.Sex)

    # Sex is given, but is invalid. Explicitely ask for it
    if not sex:
        printDebug("Invalid sex. Re-asking")
        del request.intent.slots.Sex['value']
        del request.intent.slots.Sex['resolutions']
        printDebug("Updated request to remove invalid sex: {}".format(request))
        session.attributes[LAST_QUESTION] = DOG_NAME_ASKED
        speech_output = render_template("invalid_sex_ask_again", dog=dogName)
        return elicit_slot("Sex", speech_output, updated_intent=request.intent)

    saveDogForUser(session.user.userId, dogName=dogName, sex=sex)

    session.attributes[LAST_QUESTION] = SHOULD_START_TRAINING
    speech_output = render_template('sex_set', dog=dogName, sex=render_template(sex))
    reprompt = render_template('should_start_training')

    return question(speech_output).reprompt(reprompt)

@ask.intent('StartTrainingIntent', mapping={'dogName': 'Dog', 'sexFromIntent': 'Sex'})
def startTrainingHandler(dogName, sexFromIntent):
    dogFromDynamoDB = getDogFromDynamoDB(session.user.userId)

    # If we don't know the dogname at all, ask again
    if not dogName:
        try:
            dogName = dogFromDynamoDB[DOG_NAME]
        except:
            printDebug("Name not in intent, and dog not in DB. Asking name first.")
            session.attributes[LAST_QUESTION] = DOG_NAME_ASKED
            speech_output = render_template("lets_train_get_name")
            printDebug("Starting elicit of DOG")
            return elicit_slot('Dog', speech_output)

    if sexFromIntent:
        sex = getUniqueSlotID(request.intent.slots.Sex)
        if not sex:
            printDebug("Invalid sex. Re-asking")
            del request.intent.slots.Sex['value']
            del request.intent.slots.Sex['resolutions']
            printDebug("Updated request to remove invalid sex: {}".format(request))
            session.attributes[LAST_QUESTION] = DOG_NAME_ASKED
            speech_output = render_template("invalid_sex_ask_again", dog=dogName)
            return elicit_slot('Sex', speech_output, updated_intent=request.intent)
    else:
        try:
            if dogName == dogFromDynamoDB[DOG_NAME]:
                printDebug("getting sex from active dog")
                sex = dogFromDynamoDB[SEX]
            else:
                printDebug("getting sex from previous dog")
                sex = dogFromDynamoDB[PREVIOUS_DOGS][dogName]
            printDebug("found sex as: {}".format(sex))
            assert sex != UNKNOWN
        except:
            session.attributes[LAST_QUESTION] = SEX_ASKED
            printDebug("Sex is not known. Asking.")
            request.intent.slots.Dog.value=dogName
            return delegate(updated_intent=request.intent)

    printDebug("Sex finally known: {}".format(sex))

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
    dogName = dog[DOG_NAME]
    pronoun = render_template(dog[SEX]+"_pronoun")
    subject = render_template(dog[SEX]+"_subject")
    speech_output = render_template('training_confirmation', dog=dogName, pronoun=pronoun, subject=subject)
    reprompt = render_template('ready_to_start_training')
    card_title = render_template('training_confirmation_card_title')
    card_content = render_template('training_confirmation_card_content', dog=dogName)

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
            printDebug("Sex is {}, will set".format(sex))
            dog[SEX] = sex
        else:
            printDebug("Sex is not set, will set to {}".format(UNKNOWN))
            dog[SEX] = UNKNOWN

        return saveDogToDynamoDB(dog, user)

    # One time upgrade
    dog = upgrade_v1_to_v2(dog)

    oldDogName = dog[DOG_NAME]

    # Name has changed: update
    if dogName and dogName.lower() != oldDogName.lower():
        print("old sex set to: {}".format(dog[SEX]))
        dog[PREVIOUS_DOGS][oldDogName] = dog[SEX]
        dog[NUMBER_OF_RENAMES] += 1
        dog[DOG_NAME] = dogName

    dog[SEX] = sex

    return saveDogToDynamoDB(dog, user)

# Validates that there is only one, returns the ID if it exists, None if it doesn't 
def getUniqueSlotID(slot):
    try:
        assert slot.resolutions.resolutionsPerAuthority[0]['status']['code'] == "ER_SUCCESS_MATCH"
        assert len(slot.resolutions.resolutionsPerAuthority[0]['values']) == 1
        return slot.resolutions.resolutionsPerAuthority[0]['values'][0]['value']['id']
    except AssertionError:
        return None

def upgrade_v1_to_v2(dog):
    if not PREVIOUS_DOGS in dog:
        dog[PREVIOUS_DOGS] = {}
    if not SEX in dog:
        printDebug("Sex is not set, will set to {}".format(UNKNOWN))
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
        printDebug("No dog found.")
        return None

def saveDogToDynamoDB(dog, user):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not CREATED_AT in dog:
        dog[CREATED_AT] = now
    dog[UPDATED_AT] = now
    printDebug("Dog will be saved: ")
    printDebug(dog)

    try:
        dogs_table.put_item(Item={'account':user,'dog':dog })
        return dog
    except Exception as e:
        print("Exception while saving dog: ")
        print(e)
        return None

def printDebug(s):
    if DEBUG:
        print(s)
        
### 
### Main handler: lambda_handler for lambda, app.run for debugging/ngrok
###

def lambda_handler(event, _context):
    return ask.run_aws_lambda(event)

if __name__ == '__main__':
    app.run(debug=True)

