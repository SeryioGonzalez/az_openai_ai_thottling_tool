from colorama import Fore, Style
from colorama import init as colorama_init
from itertools import product
from nltk.tokenize import word_tokenize

import nltk
import os
import requests
import time

# Environment variables
AZURE_OPENAI_API_KEY  = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")

# Some deployments will not ever get throttled, so we need a timeout for finishing the test
EXPERIMENT_TIMEOUT_SECONDS = 20

# Define the list with specified deployment names. 
# In the previous AZ CLI scripts, deployment name follow a model_name-mode_version naming
AZ_OAI_DEPLOYMENTS = [
    "gpt-4-1106",
    "gpt-4-0613",
    "gpt-4-vision-preview",
    "gpt-4-turbo-2024-04-09",
    "gpt-4o-2024-05-13",
    "gpt-35-turbo-0613",
    "gpt-35-turbo-1106",
    "gpt-35-turbo-16k-0613",
    "gpt-4-32k-0613"
]

# Set up combinations of prompt sizes and max token limits for experiments
prompt_sizes     = {'small': 100, 'large': 3400}
max_token_limits = {'no': None, 'small': 100, 'large': 2000}

#############################################
#### NO NEED TO CHANGE BEYOND THIS POINT ####
#############################################

AZURE_OPENAI_API_VERSION="2024-05-01-preview"
LARGE_TEXT_FILE_PATH = 'hamlet.txt'

# We will make sure there is at least 60 seconds between consecutive calls to a given deployment

def construct_text_from_tokens(token_list):
    # Initialize an empty string to build the sentence
    sentence = ""

    # Iterate through each token and check for punctuation
    for i, token in enumerate(token_list):
        if token in {",", ".", ":", ";", "!", "?", ")", "[", "]", "{", "}", "<", ">", "'", '"'}:
            # Add punctuation directly after the previous word without a space
            sentence = sentence.rstrip() + token
        else:
            # Add a space before the word if it's not the first word
            if i > 0:
                sentence += " "
            sentence += token

    return sentence

def generate_prompt_with_token_length(token_length):
    
    prompt_template_header = """
You are a literature expert. Indicate the author and book of the following text:
######START OF TEXT#######
"""
    prompt_template_footer = """
######END OF TEXT#######
Write an output in JSON with the following structure
{
    "author": "Author name",
    "book": "Book name"
}
""" 

    prompt_template_header_token_length = len(word_tokenize(prompt_template_header))
    prompt_template_footer_token_length = len(word_tokenize(prompt_template_footer))

    tokens_in_prompt_template = prompt_template_header_token_length + prompt_template_footer_token_length

    if token_length <= tokens_in_prompt_template:
        raise ValueError(f"Prompt tokens must be greater than {tokens_in_prompt_template}")

    # Open the file and read its content into a string
    with open(LARGE_TEXT_FILE_PATH, 'r', encoding='utf-8') as file:
        file_content = file.read()

    nltk.download('punkt', quiet=True)

    # Tokenize the text
    tokens_from_text = word_tokenize(file_content, language='english')

    # Get the desired number of tokens
    desired_text = construct_text_from_tokens(tokens_from_text[0:(token_length - tokens_in_prompt_template - 1)])

    # Replace the placeholder in the prompt template with the desired text
    prompt = prompt_template_header + desired_text + prompt_template_footer

    return prompt

def generate_message_list_with_token_length(tokens_in_prompt):
    desired_prompt = generate_prompt_with_token_length(tokens_in_prompt)
    messages = [{"role": "user", "content": desired_prompt }]  

    return messages

experiment_list = [
    {
        'deployment': deployment,
        'experiment_name': f'{size}_prompt_{limit}_max_tokens',
        'prompt_size': prompt_sizes[size],
        'max_token_limit': max_token_limits[limit],
        'experiment_result': None
    }
    for size in prompt_sizes  # Iterate over prompt sizes
    for limit in max_token_limits  # Iterate over token limits
    for deployment in AZ_OAI_DEPLOYMENTS
]

# Reseting color
colorama_init(autoreset=True)

# Initializing token count
last_call_to_deployments = { deployment: None for deployment in AZ_OAI_DEPLOYMENTS}

for experiment_index, experiment_data in enumerate(experiment_list):
    experiment_name            = experiment_data['experiment_name']
    experiment_prompt_size     = experiment_data['prompt_size']
    experiment_max_token_limit = experiment_data['max_token_limit']
    az_openai_deployment       = experiment_data['deployment']

    # In order not to contaminate the experiment, we need to make sure the time between calls to the same deployment is at least 60 seconds so token count get reset
    if last_call_to_deployments[az_openai_deployment] is not None:
        time_since_last_call_to_this_deployment = time.time() - last_call_to_deployments[az_openai_deployment]
        if time_since_last_call_to_this_deployment < 60:
            needed_nap = 60 - time_since_last_call_to_this_deployment
            print(f"Sleeping for {needed_nap} seconds to respect the 60 seconds between calls to deployment {az_openai_deployment}")
            time.sleep(needed_nap)

    # HTTP INFO
    az_openai_url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{az_openai_deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {'api-key': AZURE_OPENAI_API_KEY, 'Content-Type': 'application/json'}
    data = {'messages': generate_message_list_with_token_length(experiment_prompt_size)}

    x_ratelimit_previous_tokens = None
    experiment_start_time = time.time()

    print(f"Starting experiment {experiment_name} on deployment {Fore.GREEN}{az_openai_deployment}{Style.RESET_ALL} with {Fore.GREEN}prompt_size=={experiment_prompt_size}{Style.RESET_ALL} and {Fore.GREEN}max_tokens=={experiment_max_token_limit}{Style.RESET_ALL}")
    try: 
        while time.time() - experiment_start_time < EXPERIMENT_TIMEOUT_SECONDS:
            # Set the max tokens in the header
            if experiment_max_token_limit is not None:
                data['max_tokens'] = experiment_max_token_limit

            # Send request
            response = requests.post(az_openai_url, headers=headers, json=data)
            
            status_code = response.status_code
            if status_code == 429:
                print(f"Response code:{Fore.RED} 429 - Rate limit exceeded")
                # Throw exception to stop the execution
                raise Exception("Rate limit exceeded")
                
            response_json = response.json()
            if 'error' in response_json:
                print(f"{Fore.RED}Error:{Style.RESET_ALL} {response_json['error']['message']}")
                raise Exception("Error in response")

            x_ratelimit_remaining_tokens   = int(response.headers.get("x-ratelimit-remaining-tokens"))
            x_ratelimit_remaining_requests = int(response.headers.get("x-ratelimit-remaining-requests"))
            api_reported_total_tokens      = response_json['usage']['total_tokens']
            api_reported_completion_tokens = response_json['usage']['completion_tokens']
            api_reported_prompt_tokens     = response_json['usage']['prompt_tokens']
            current_timestamp              = time.time()
            
            if x_ratelimit_previous_tokens != None:
                x_ratelimit_discounted_tokens = x_ratelimit_previous_tokens - x_ratelimit_remaining_tokens
                if x_ratelimit_discounted_tokens > api_reported_total_tokens:
                    color = Fore.RED
                else:
                    color = Fore.GREEN

                print(f"Model {Fore.GREEN}{az_openai_deployment}{Style.RESET_ALL} - Remaining requests for thr. {x_ratelimit_remaining_requests:>{3}} - Remaning tokens for thr. before {x_ratelimit_previous_tokens:>{6}} - Remaining tokens for thr. now: {x_ratelimit_remaining_tokens:>{6}} - {color}Discounted tokens for thr. {x_ratelimit_discounted_tokens:>{5}}{Style.RESET_ALL} ----- Total Tokens in call: {Fore.BLUE}{api_reported_total_tokens:>{4}}{Style.RESET_ALL} == (Prompt tokens { api_reported_prompt_tokens:>{4}} + Response tokens { api_reported_completion_tokens:>{4}})")
            else:
                x_ratelimit_discounted_tokens = None
                x_ratelimit_previous_tokens  = x_ratelimit_remaining_tokens + api_reported_total_tokens
                print(f"Model {Fore.GREEN}{az_openai_deployment}{Style.RESET_ALL} - Remaining requests for thr. {x_ratelimit_remaining_requests:>{3}} - Remaning tokens for thr. before {x_ratelimit_previous_tokens:>{6}} - Remaining tokens for thr. now: {x_ratelimit_remaining_tokens:>{6}} - Discounted tokens for thr.    NA ----- Total Tokens in call: {Fore.BLUE}{api_reported_total_tokens:>{4}}{Style.RESET_ALL} == (Prompt tokens { api_reported_prompt_tokens:>{4}} + Response tokens { api_reported_completion_tokens:>{4}})")
           
            
            x_ratelimit_previous_tokens = x_ratelimit_remaining_tokens

        experiment_status = 'Success'
    
    except Exception as e:
        print(f"Experiment {experiment_name} on deployment {az_openai_deployment} terminated with exception: {e}")
        experiment_status = 'Failure'

    experiment_list[experiment_index]['experiment_result'] = experiment_status
    last_call_to_deployments[az_openai_deployment] = time.time()

    print("")

