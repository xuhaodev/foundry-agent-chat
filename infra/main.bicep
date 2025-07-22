// Bicep file for Azure App Service deployment for Chainlit app
// Implements managed identity, CORS, diagnostic settings, Application Insights, Log Analytics
// Resource names use az-{resourcePrefix}-{resourceToken} format
// Outputs RESOURCE_GROUP_ID

param environmentName string
param location string = 'East US'
param AZURE_CLIENT_ID string
param AZURE_TENANT_ID string
param AZURE_SUBSCRIPTION_ID string

var resourcePrefix = 'cli' // ≤ 3 chars
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var appServiceName = 'az-${resourcePrefix}-${resourceToken}'
var appInsightsName = 'az-${resourcePrefix}-ai-${resourceToken}'
var logAnalyticsName = 'az-${resourcePrefix}-la-${resourceToken}'
var identityName = 'az-${resourcePrefix}-id-${resourceToken}'

resource userIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: 'az-${resourcePrefix}-plan-${resourceToken}'
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
  }
}

resource appService 'Microsoft.Web/sites@2022-03-01' = {
  name: appServiceName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      cors: {
        allowedOrigins: ['*']
      }
      appSettings: [
        {
          name: 'AZURE_CLIENT_ID'
          value: AZURE_CLIENT_ID
        }
        {
          name: 'AZURE_TENANT_ID'
          value: AZURE_TENANT_ID
        }
        {
          name: 'AZURE_SUBSCRIPTION_ID'
          value: AZURE_SUBSCRIPTION_ID
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'LOG_ANALYTICS_WORKSPACE_ID'
          value: logAnalytics.id
        }
      ]
    }
    httpsOnly: true
  }
  tags: {
    'azd-service-name': 'chainlit-app'
    'azd-env-name': environmentName
  }
}

resource diagSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'az-${resourcePrefix}-diag-${resourceToken}'
  scope: appService
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

output RESOURCE_GROUP_ID string = resourceGroup().id
