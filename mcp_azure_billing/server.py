# server.py
import sys
import os
import json
from typing import Dict, List, Optional, Any, Union
import httpx
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Azure Billing MCP")

# Environment variables for Azure Billing configuration
AZURE_BILLING_TENANT_ID = os.environ.get("AZURE_BILLING_TENANT_ID")
AZURE_BILLING_CLIENT_ID = os.environ.get("AZURE_BILLING_CLIENT_ID")
AZURE_BILLING_CLIENT_SECRET = os.environ.get("AZURE_BILLING_CLIENT_SECRET")
AZURE_BILLING_SUBSCRIPTION_ID = os.environ.get("AZURE_BILLING_SUBSCRIPTION_ID")

# Check if environment variables are set
if not all([AZURE_BILLING_TENANT_ID, AZURE_BILLING_CLIENT_ID, AZURE_BILLING_CLIENT_SECRET, AZURE_BILLING_SUBSCRIPTION_ID]):
    print("Warning: Azure Billing environment variables not fully configured. Set AZURE_BILLING_TENANT_ID, AZURE_BILLING_CLIENT_ID, AZURE_BILLING_CLIENT_SECRET, and AZURE_BILLING_SUBSCRIPTION_ID.", file=sys.stderr)

# Base URLs
AZURE_MANAGEMENT_URL = "https://management.azure.com"
AZURE_LOGIN_URL = "https://login.microsoftonline.com"

# Helper function to get Azure access token
async def get_azure_token() -> str:
    """Get Azure AD access token for API authentication."""
    url = f"{AZURE_LOGIN_URL}/{AZURE_BILLING_TENANT_ID}/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AZURE_BILLING_CLIENT_ID,
        "client_secret": AZURE_BILLING_CLIENT_SECRET,
        "resource": "https://management.azure.com/"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        if response.status_code != 200:
            print(f"Error getting Azure token: {response.text}", file=sys.stderr)
            return None
        
        return response.json().get("access_token")

# Helper function for API requests
async def make_azure_billing_request(method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
    """
    Make a request to the Azure Billing API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (without base URL)
        params: URL parameters
        data: Data to send (for POST/PUT)
    
    Returns:
        Response from Azure Billing API as dictionary
    """
    token = await get_azure_token()
    if not token:
        return {"error": True, "message": "Failed to authenticate with Azure"}
    
    url = f"{AZURE_MANAGEMENT_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, params=params, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code >= 400:
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "message": response.text
                }
            
            return response.json()
        except Exception as e:
            return {
                "error": True,
                "message": f"API request failed: {str(e)}"
            }

# === TOOLS ===

@mcp.tool()
async def get_cost_analysis(timeframe: str = "MonthToDate", granularity: str = "Daily", 
                           group_by: str = None) -> str:
    """
    Get cost analysis for the subscription.
    
    Args:
        timeframe: The time period for the query (MonthToDate, BillingMonthToDate, TheLastMonth, Custom)
        granularity: The granularity of data (Daily, Monthly, None)
        group_by: Optional property to group the results by (ResourceGroup, ResourceId, etc.)
    """
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.CostManagement/query"
    
    # Define time period based on timeframe
    time_period = {}
    today = datetime.now()
    
    if timeframe == "MonthToDate":
        time_period = {
            "from": datetime(today.year, today.month, 1).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        }
    elif timeframe == "BillingMonthToDate":
        # Billing month might be different from calendar month
        time_period = {
            "from": datetime(today.year, today.month, 1).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        }
    elif timeframe == "TheLastMonth":
        last_month = today.replace(day=1) - timedelta(days=1)
        time_period = {
            "from": datetime(last_month.year, last_month.month, 1).strftime("%Y-%m-%d"),
            "to": last_month.strftime("%Y-%m-%d")
        }
    else:  # Custom - default to last 30 days
        time_period = {
            "from": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        }
    
    # Prepare the query
    query_data = {
        "type": "ActualCost",
        "timeframe": timeframe,
        "timePeriod": time_period,
        "dataSet": {
            "granularity": granularity,
            "aggregation": {
                "totalCost": {
                    "name": "Cost",
                    "function": "Sum"
                }
            }
        }
    }
    
    # Add grouping if specified
    if group_by:
        query_data["dataSet"]["grouping"] = [
            {
                "type": "Dimension",
                "name": group_by
            }
        ]
    
    result = await make_azure_billing_request("POST", endpoint, 
                                             params={"api-version": "2023-03-01"}, 
                                             data=query_data)
    
    if "error" in result and result["error"]:
        return f"Error retrieving cost analysis: {result.get('message', 'Unknown error')}"
    
    # Format the result in a readable way
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_budgets() -> str:
    """
    Get all budgets for the subscription.
    """
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.Consumption/budgets"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={"api-version": "2023-04-01"})
    
    if "error" in result and result["error"]:
        return f"Error retrieving budgets: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_usage_details(start_date: str = None, end_date: str = None) -> str:
    """
    Get usage details for the subscription.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (defaults to beginning of current month)
        end_date: End date in YYYY-MM-DD format (defaults to today)
    """
    today = datetime.now()
    
    if not start_date:
        start_date = datetime(today.year, today.month, 1).strftime("%Y-%m-%d")
    
    if not end_date:
        end_date = today.strftime("%Y-%m-%d")
    
    # Filter is required for usage details
    filter_param = f"properties/usageStart ge '{start_date}' and properties/usageEnd le '{end_date}'"
    
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.Consumption/usageDetails"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={
                                                 "api-version": "2023-05-01",
                                                 "$filter": filter_param
                                             })
    
    if "error" in result and result["error"]:
        return f"Error retrieving usage details: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_subscription_details() -> str:
    """
    Get details about the current subscription.
    """
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={"api-version": "2022-12-01"})
    
    if "error" in result and result["error"]:
        return f"Error retrieving subscription details: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_price_sheet() -> str:
    """
    Get the price sheet for the subscription.
    """
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.Consumption/pricesheets/default"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={"api-version": "2023-03-01"})
    
    if "error" in result and result["error"]:
        return f"Error retrieving price sheet: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

# === RESOURCES ===

@mcp.resource("https://azure-billing/subscription")
async def get_subscription_resource() -> str:
    """Get details about the current subscription."""
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={"api-version": "2022-12-01"})
    
    if "error" in result and result["error"]:
        return f"Error retrieving subscription details: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

@mcp.resource("https://azure-billing/billing-summary")
async def get_billing_summary_resource() -> str:
    """Get a summary of current billing for the subscription."""
    # We'll use cost management API to get a quick summary
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.CostManagement/query"
    
    # Get current month's data
    today = datetime.now()
    time_period = {
        "from": datetime(today.year, today.month, 1).strftime("%Y-%m-%d"),
        "to": today.strftime("%Y-%m-%d")
    }
    
    query_data = {
        "type": "ActualCost",
        "timeframe": "MonthToDate",
        "timePeriod": time_period,
        "dataSet": {
            "granularity": "None",
            "aggregation": {
                "totalCost": {
                    "name": "Cost",
                    "function": "Sum"
                }
            }
        }
    }
    
    result = await make_azure_billing_request("POST", endpoint, 
                                             params={"api-version": "2023-03-01"}, 
                                             data=query_data)
    
    if "error" in result and result["error"]:
        return f"Error retrieving billing summary: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

@mcp.resource("https://azure-billing/budgets")
async def get_budgets_resource() -> str:
    """Get all budgets for the subscription."""
    endpoint = f"/subscriptions/{AZURE_BILLING_SUBSCRIPTION_ID}/providers/Microsoft.Consumption/budgets"
    
    result = await make_azure_billing_request("GET", endpoint, 
                                             params={"api-version": "2023-04-01"})
    
    if "error" in result and result["error"]:
        return f"Error retrieving budgets: {result.get('message', 'Unknown error')}"
    
    return json.dumps(result, indent=2)

# === PROMPTS ===

@mcp.prompt("analyze_costs")
def analyze_costs_prompt(timeframe: str = None, group_by: str = None):
    """
    A prompt template for analyzing Azure costs.
    
    Args:
        timeframe: The time period for analysis (MonthToDate, TheLastMonth, etc.)
        group_by: Property to group the analysis by (ResourceGroup, ResourceId, etc.)
    """
    if timeframe and group_by:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Please analyze my Azure costs for the timeframe '{timeframe}', grouped by '{group_by}'. What insights can you provide about my spending patterns, and are there any anomalies or areas where I could optimize costs?"
                    }
                }
            ]
        }
    elif timeframe:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Please analyze my Azure costs for the timeframe '{timeframe}'. What insights can you provide about my spending patterns, and are there any anomalies or areas where I could optimize costs?"
                    }
                }
            ]
        }
    else:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": "Please analyze my Azure costs. What insights can you provide about my spending patterns, and are there any anomalies or areas where I could optimize costs?"
                    }
                }
            ]
        }

@mcp.prompt("budget_recommendations")
def budget_recommendations_prompt():
    """
    A prompt template for getting budget recommendations.
    """
    return {
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "Based on my Azure usage and spending patterns, what budget recommendations would you suggest? Please analyze my current spending and provide realistic budget thresholds for different resource categories."
                }
            }
        ]
    }

@mcp.prompt("cost_reduction")
def cost_reduction_prompt():
    """
    A prompt template for getting cost reduction suggestions.
    """
    return {
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "Please analyze my Azure billing data and suggest specific ways I could reduce costs. Identify resources that might be underutilized, oversized, or could benefit from reserved instances or savings plans."
                }
            }
        ]
    }

if __name__ == "__main__":
    print("Starting Azure Billing MCP server...", file=sys.stderr)
    mcp.run()
