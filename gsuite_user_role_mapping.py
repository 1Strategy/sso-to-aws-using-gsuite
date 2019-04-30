from __future__ import print_function
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/admin.directory.user', \
        'https://www.googleapis.com/auth/admin.directory.group.readonly', \
        'https://www.googleapis.com/auth/spreadsheets.readonly']

def updateUserRoleMapping(service_admin, group_email, user_role, group_role):
    try:
        results = service_admin.members().list(groupKey=group_email).execute()
        members = results.get('members', [])
        print("Group: " + group_email)
        if not members:
            print('No data found.')
        else:
            for m in members:
                if m['type'] == 'USER':
                    print("    User: " + m['email'])
                    primary_email = service_admin.users().get(userKey=m["email"]).execute().get('primaryEmail', '')
                    if primary_email == '':
                        continue
                    if primary_email in user_role:
                        user_role[primary_email].update(group_role)
                    else:
                        user_role[primary_email] = set(group_role)
                if m['type'] == 'GROUP':
                    updateUserRoleMapping(service_admin, m['email'], user_role, group_role)
    except Exception as ex:
        print(ex)
        return

def getUserRoleMapping(service_sheets, service_admin, spreadsheet_id, range_name):
    # Call the Sheets API to get group role mapping
    result = service_sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
                                                range=range_name).execute()
    values = result.get('values', [])
    mapping = {}
    if not values:
        print('No data found.')
    else:
        for row in values[1:]:
            if (not row) or (not row[0].strip()):
                continue
            roles = []
            if len(row) > 1 and row[1].strip() != '':
                roles = [x.strip() for x in row[1].split(',')]
            if row[0] in mapping:
                mapping[row[0].strip()].update(roles)
            else:
                mapping[row[0].strip()] = set(roles)

    # get user-role mapping
    user_role = {}
    for group_email in mapping:
        updateUserRoleMapping(service_admin, group_email, user_role, mapping[group_email])

    return user_role

def lambda_handler(event, context):
    # Get parameters from environment variables
    schema_name = os.environ['schema_name']
    iam_role_property_name = os.environ['iam_role_property_name']
    session_duration_property_name = os.environ['session_duration_property_name']
    session_duration_property_value = int(os.environ['session_duration_property_value'])
    assume_user = os.environ['assume_user']
    spreadsheet_id = os.environ['spreadsheet_id']
    spreadsheet_range_name = os.environ['spreadsheet_range_name']
    idp_arn = os.environ['idp_arn']

    # Create admin service and sheets service using service account
    creds = service_account.Credentials.from_service_account_file(
                'service.json', scopes=SCOPES).with_subject(assume_user)
    service_admin = build('admin', 'directory_v1', credentials=creds)
    service_sheets = build('sheets', 'v4', credentials=creds)
    # Get User-Role Mapping
    user_role_mapping = getUserRoleMapping(service_sheets, service_admin, spreadsheet_id, spreadsheet_range_name)
    print(user_role_mapping)

    # Update users
    for user in user_role_mapping:
        requestBody = {
            "customSchemas": {
                schema_name: {
                    iam_role_property_name: [],
                    session_duration_property_name: session_duration_property_value
                }
            }
        }
        for role in user_role_mapping[user]:
            requestBody['customSchemas'][schema_name][iam_role_property_name].append(
                {
                    'value': role + ',' + idp_arn
                }
            )
        service_admin.users().update(userKey=user, body=requestBody).execute()