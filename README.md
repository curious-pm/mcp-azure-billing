# Azure Billing MCP Server

A Model Context Protocol (MCP) server for Azure Billing integration. This server provides tools for interacting with Azure's Billing and Cost Management APIs, allowing you to query cost analysis, budgets, usage details, and other billing information.

## Features

- **Cost Analysis**: Analyze your Azure costs with various timeframes and granularity options
- **Budget Management**: View existing budget information
- **Usage Details**: Get detailed information about resource usage
- **Subscription Information**: Retrieve subscription details
- **Price Sheet**: Access pricing information for Azure services

## Installation

```bash
pip install mcp-azure-billing
```

## Azure Credentials

To use this MCP server, you'll need to set up an Azure service principal with permissions to access billing information. Here's how to obtain the necessary credentials:

1. **Create an Azure AD application and service principal**:
   
   ```bash
   az ad sp create-for-rbac --name "AzureBillingMCP" --role "Cost Management Reader" --scopes /subscriptions/{SUBSCRIPTION_ID}
   ```

   This command will output application (client) ID, tenant ID, and client secret.

2. **Verify the permissions**:
   
   Ensure the service principal has at least the "Cost Management Reader" role assigned at the subscription level to access billing data.

3. **Required Credentials**:
   
   - **AZURE_BILLING_TENANT_ID**: Your Azure AD tenant ID
   - **AZURE_BILLING_CLIENT_ID**: The application (client) ID of your service principal
   - **AZURE_BILLING_CLIENT_SECRET**: The client secret value
   - **AZURE_BILLING_SUBSCRIPTION_ID**: Your Azure subscription ID

## Configuration

Set the following environment variables:

```bash
export AZURE_BILLING_TENANT_ID="your_tenant_id"
export AZURE_BILLING_CLIENT_ID="your_client_id"
export AZURE_BILLING_CLIENT_SECRET="your_client_secret" 
export AZURE_BILLING_SUBSCRIPTION_ID="your_subscription_id"
```

## Usage

### Starting the server directly

```bash
mcp-azure-billing
```

### Using with Claude Desktop

Add the following to your `claude_desktop_config.json` file:

```json
"mcp-azure-billing": {
  "command": "uvx",
  "args": [
    "mcp-azure-billing"
  ],
  "env": {
    "AZURE_BILLING_TENANT_ID": "your_tenant_id",
    "AZURE_BILLING_CLIENT_ID": "your_client_id",
    "AZURE_BILLING_CLIENT_SECRET": "your_client_secret",
    "AZURE_BILLING_SUBSCRIPTION_ID": "your_subscription_id"
  }
}
```

Replace the environment variables with your actual Azure credentials.

## Available Tools

* **get_cost_analysis**: Analyze Azure costs with customizable timeframes, granularity, and grouping
* **get_budgets**: Retrieve information about all configured budgets for the subscription
* **get_usage_details**: Get detailed usage information for a specified date range
* **get_subscription_details**: Retrieve details about the current Azure subscription
* **get_price_sheet**: Get pricing information for Azure services

## Available Resources

* **azure_billing://subscription**: Details about the current Azure subscription
* **azure_billing://billing-summary**: Summary of current billing for the subscription
* **azure_billing://budgets**: Information about all configured budgets

## Available Prompts

* **analyze_costs**: Template for analyzing Azure costs with customizable parameters
* **budget_recommendations**: Template for getting budget recommendations based on usage patterns
* **cost_reduction**: Template for getting cost reduction suggestions

## Security Notes

- Store your Azure credentials securely - they provide access to potentially sensitive billing information
- Consider using environment variables rather than hardcoding credentials
- Ensure your service principal has the minimum necessary permissions

## Limitations

- This server provides read-only access to billing information
- Some operations may take time to complete due to the nature of the Azure Cost Management API
- Usage data may not reflect the most recent activities (typically 8-24 hour delay)

## Version

0.0.1
