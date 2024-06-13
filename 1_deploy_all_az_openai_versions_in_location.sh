source config.sh

az account set -s $az_subscription_id

# It will create every single model name and version in your region of choice
az cognitiveservices model list -l $az_location --query "[?model.format == 'OpenAI' && starts_with(model.name, 'gpt') && model.skus[?name == 'Standard'] ].{name:model.name, version:model.version}" -o tsv | while read -r model version; do
  model_deployment_name="$model-$version"
  echo "Model is $model with version $version will be a deployment named $model_deployment_name"
  az cognitiveservices account deployment create -g $az_rg -n $az_cognitive_service_account_name --model-format OpenAI --model-name $model --model-version $version --deployment-name $model_deployment_name --sku Standard --sku-capacity $az_model_deployment_tpm_capacity -o none
done