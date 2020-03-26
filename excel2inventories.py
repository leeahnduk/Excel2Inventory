# =================================================================================

from tetpyclient import RestClient
import tetpyclient
import json
import requests.packages.urllib3
import sys
import os
import argparse
import time
import csv
from columnar import columnar

# =================================================================================
# python3 excel2inventories.py --url https://192.168.30.4 --credential api_credentials.json --csv output_csv_file.csv
# See reason below -- why verify=False param is used
# feedback: Le Anh Duc - anhdle@cisco.com
# =================================================================================

requests.packages.urllib3.disable_warnings()

# ====================================================================================
# GLOBALS
# ------------------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Script to convert K8s Manifest YAML File to Inventory Filter')
parser.add_argument('--url', help='Tetration URL', required=True)
parser.add_argument('--credential', help='Path to Tetration json credential file', required=True)
parser.add_argument('--csv', help='Path to CSV File', required=True)
args = parser.parse_args()

'''
====================================================================================
Class Constructor
------------------------------------------------------------------------------------
'''
def CreateRestClient():
    rc = RestClient(args.url,
                    credentials_file=args.credential, verify=False)
    return rc

def GetApplicationScopes(rc):
    resp = rc.get('/app_scopes')

    if resp.status_code != 200:
        print("Failed to retrieve app scopes")
        print(resp.status_code)
        print(resp.text)
    else:
        return resp.json()

def GetVRFs(rc):
    # Get all VRFs in the cluster
    resp = rc.get('/vrfs')

    if resp.status_code != 200:
        print("Failed to retrieve app scopes")
        print(resp.status_code)
        print(resp.text)
    else:
        return resp.json()

def GetRootScope(vrfs):
    #return list of Root Scopes and its' names
    rootScopes = []
    headers = ['Root Scope Name', 'VRF ID']
    for vrf in vrfs:
        rootScopes.append([vrf["name"] , vrf["vrf_id"]])
    table = columnar(rootScopes, headers, no_borders=False)
    print(table)

def GetAppScopeId(scopes,name):
    try:
        return [scope["id"] for scope in scopes if scope["name"] == name][0]
    except:
        print("App Scope {name} not found".format(name=name))

def CreateInventoryFilters(rc,scopes):
    inventoryDict = {}
    vrfs = GetVRFs(rc)
    print ("\nHere are the names and VRF ID of all the root scopes in your cluster: ")
    GetRootScope(vrfs)
    ParentScope = input ("Which parent Scope you want to define your inventory Filter: ") 
    NameSpace = input ("Which NameSpace in K8s you defined your apps: ")
    with open(args.csv) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['Deployment'] not in inventoryDict:
                inventoryDict[row['Deployment']] = {}
                inventoryDict[row['Deployment']]['app_scope_id'] = GetAppScopeId(scopes,ParentScope)
                inventoryDict[row['Deployment']]['name'] = row['Deployment']
                inventoryDict[row['Deployment']]['short_query'] = {
                    "type" : "and",
                    "filters" : [
                    {
                "type": "eq",
                "field": "user_orchestrator_name",
                "value": row['Deployment']
                },
                {
                    "type": "eq",
                    "field": "user_orchestrator_system/namespace",
                    "value": NameSpace
                }]
                }
            if inventoryDict[row['Deployment']]['app_scope_id'] != GetAppScopeId(scopes,ParentScope):
                print("Parent scope does not match previous definition")
                continue
                
            if row['Service'] not in inventoryDict:
                inventoryDict[row['Service']] = {}
                inventoryDict[row['Service']]['app_scope_id'] = GetAppScopeId(scopes,ParentScope)
                inventoryDict[row['Service']]['name'] = row['Service']
                inventoryDict[row['Service']]['short_query'] = {
                    "type" : "and",
                    "filters" : [
                    {
                "type": "eq",
                "field": "user_orchestrator_system/service_endpoint",
                "value": row['Service']
                },
                {
                    "type": "eq",
                    "field": "user_orchestrator_system/namespace",
                    "value": NameSpace
                }]
                }
            if inventoryDict[row['Service']]['app_scope_id'] != GetAppScopeId(scopes,ParentScope):
                print("Parent scope does not match previous definition")
                continue

    return inventoryDict

def PushInventoryFilters(rc,inventoryFilters):
    for inventoryFilter in inventoryFilters:
        req_payload = inventoryFilters[inventoryFilter]
        resp = rc.post('/filters/inventories', json_body=json.dumps(req_payload))
        if resp.status_code != 200:
            print("Error pushing InventorFilter")
            print(resp.status_code)
            print(resp.text)
        else:
            print("Inventory Filters successfully pushed for " + inventoryFilters[inventoryFilter]["name"])


def main():
    rc = CreateRestClient()
    scopes = GetApplicationScopes(rc)
    inventoryFilters = CreateInventoryFilters(rc,scopes)
    PushInventoryFilters(rc,inventoryFilters)

if __name__ == "__main__":
    main()
