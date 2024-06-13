
#You need to set-up the following values with the ones you have in your Azure account
# Your local subscription
az_subscription_id="$AZURE_SUBSCRIPTION_ID"
# Your desired location
az_location="swedencentral"

# The RG of your Azure Cognitive Services account
az_rg="auxResources"

# The name of your Azure Cognitive Services account
az_cognitive_service_account_name="sergioazopenai"

# The capacity of the deployments in thousands of tokens per minute
az_model_deployment_tpm_capacity=10