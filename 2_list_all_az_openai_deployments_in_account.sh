source config.sh

az account set -s $az_subscription_id

# It will get every single openai deployment in your region of choice
# You might want to use this for updating AZ_OAI_DEPLOYMENTS array in the python file
az cognitiveservices account deployment list -g $az_rg -n $az_cognitive_service_account_name --query "[?properties.model.format == 'OpenAI' && starts_with(name, 'gpt-')].name" -o tsv