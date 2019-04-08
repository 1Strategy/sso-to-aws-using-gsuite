# Federated Single Sign-On to AWS Using GSuite

## Overview

Enable single sign-on to AWS console using GSuite:

1. On AWS - setup cross account roles in the SSO account to switch roles to other accounts, so we only need to map GSuite groups to IAM roles in SSO acccount
1. On GSuite - add AWS Console as a SAML App to GSuite and enable SSO experience
1. On AWS - automate mapping between GSuite groups to IAM roles and update the mapping based on a config file (google sheets) on an hourly basis
1. On Client - Enable AWS CLI using GSuite credential

## Prerequistes
1. Python 3.7 or greater
1. A G Suite domain with [API access enabled](https://support.google.com/a/answer/60757)
1. A G Suite user with super administrator access
1. A google sheets file with below two columns:
    * group_email: the email address of the group
    * role_arns: a comma seperated arn list of the IAM roles assigned to users in the group
    * Here is an example:

    | group_email        | role_arns                                         |
    | ------------------ |:-------------------------------------------------:|
    | test@abc.com       |arn:aws:iam::<account_num>:role/rolename01,arn:aws:iam::<account_num>:role/rolename02 |
    | dev@abc.com        |arn:aws:iam::<account_num>:role/rolename03,arn:aws:iam::<account_num>:role/rolename04 |
   
## Manually Setup GSuite and AWS federation

### GSuite Admin Console Set up
1. Add custom attributes to GSuite user

    Create a custom attribute category named "SSO" with two attributes defined:
    * IAM Role (IAM_Role): this is a multiple value text attribute that has all the roles mapped to the user. The format is "ARN of IAM role to assume", "ARN of the identity provider (will setup in step 3 below)"
    * Session Duration (Session_Duation): Whole Number, the session duration in seconds, default is 3600 (an hour)

1. Add a new SAML App in GSuite

    * Step 1 - Select Amazon Web Service
    * Step 2 - Download the IDP metadata in XML (save it securely)
    * Step 3 - Give an application name, description and logo
    * Step 4 - Set "Name Id" as Basic Information | Primary Email and format  as EMAIL
    * Step 5 - Attribute mapping
        * https://aws.amazon.com/SAML/Attributes/RoleSessionName --> "Basic Information" | "Primary Email"
        * https://aws.amazon.com/SAML/Attributes/Role --> "SSO" | "IAM_Role"
        * https://aws.amazon.com/SAML/Attributes/SessionDuration --> "SSO" | "Session_Duation"

### AWS Console Set Up
1. Add Identity Provider in AWS
    * Log in to AWS SSO account
    * Go to IAM --> Identity providers
    * Choose Create Provider with SAML as type and give a name and upload the IDP XML file downloaded from previous step.
    * Keep a record of the Provider ARN for future use

1. Create IAM role(s) for the GSuite users to consume.

### Update the "SSO" custom attribute in the GSuite Admin Console

    * Set "SSO" | "IAM_Role" as "ARN of IAM role to assume,ARN of the identity provider"
    * Set "SSO" | "Session_Duation" as the session duration in seconds, default is 3600s

Then you should be able to log into AWS SSO env by single click on the GSuite App named Amazon Web Services, then switch roles to other accounts from AWS console.

## Automatically update mapping between GSuite Group and AWS IAM Roles

Automate mapping between GSuite groups to AWS roles and update the mapping based on configuration in a google sheets on an hourly basis.

1. Enable Directory API from GSuite Admin SDK following guidelines [here](https://developers.google.com/admin-sdk/directory/v1/quickstart/python) and create a project called "SSO-AWS-GSuite"

1. Enable Sheets API following guidelines [here](https://developers.google.com/sheets/api/quickstart/python)

1. Go to the project in [google API developer console](https://console.developers.google.com) created in Step 1 above

1. In Credentials section choose Create Credentials drop down and choose Service account key option and follow the wizard:

    * Choose New service account
    * give an account name and choose a role (project owner)
    * set a service account id, it'll form an email address for the service account under the project's domain
    * choose JSON as key type and click create. NOTE: make sure you save the json file securely for future use

1. Setup API client access in GSuite

    This is to setup an Authorized API client in GSuite so the service account we created above can assume a GSuite user and perform operations on behalf of the user from a lambda function.

    * Go to [GSuite Admin Console](admin.google.com)
    * Go to Security --> Advanced Settings --> Manage API Client Access
    * Copy the client_id from the JSON file you saved from previous to the Client Name section
    * Put "https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.group.readonly,https://www.googleapis.com/auth/spreadsheets.readonly" in the "One or More API Scopes" section. It'll make sure the service account can: view groups on your domain, view and manage the provisioning of users on your domain and access spreadsheets on Sheets app (where we save the group-role mapping)

1. Create lambda deployment package

    * Clone this repo
    * Copy the service account key file to the repo folder and rename it to service.json
    * Open a terminal (on mac) go to the repo folder and run the create_lambda_package.sh
        
        ```bash
        $ create_lambda_package.sh venv_folder_name
        ```
        This will create a folder with name "venv_folder_name" if you don't specify a name "lambda_venv" will be used.
        The script will create a lambda.zip in the venv folder.

1. Create lambda function

    * Create an IAM role with AWSLambdaExecute permission
    * Create a python3.6 lambda function using the IAM role and package created above.
    * Add following environment variables:
        "schema_name": "SSO",
        "iam_role_property_name": "IAM_Role",
        "session_duration_property_name": "Session_Duration",
        "session_duration_property_value": "28800",
        "assume_user": "email of the user to assume",
        "spreadsheet_id": "spreadsheet id",
        "spreadsheet_range_name": "spreadsheet range name",
        "idp_arn": "idp arn"
    * Set Handler as gsuite_user_role_mapping.lambda_handler
    * Set timeout to 5min

1. Create a CloudWatch event rule to trigger the lambda function on an hourly basis

    * Create a Scheduled CloudWatch Rule and set Fixed rate of 1 hour
    * Set Targets as the lambda function created above and save

## Enable AWS CLI using GSuite credential (Optional)
We use online solution [aws-google-auth](https://github.com/cevoaustralia/aws-google-auth) to achieve access AWS CLI with GSuite credential, and then update file "~/.aws/config" on the client to enable switching roles between multiple accounts. Here are the steps:

1. Installation

    ```shell
    localhost$ sudo pip install aws-google-auth
    ```

1. Execution below command and provide necessary parameters

    ```shell
    localhost$ aws-google-auth -p SSO -d 3600
    ```

1. Update file "~/.aws/config" with "source_profile" set to "SSO" and role_arn set to the role you are going to switch to in the second account, here is an example:

    ```
    [profile sandbox]
    region = us-east-1
    role_arn = arn:aws:iam::xxxxxxxxxx:role/Admins
    source_profile = SSO
    ```

1. Then you should be able to switch role using --profile parameter in the CLI, e.g.

    ```
    aws s3 ls --profile sandbox
    ```