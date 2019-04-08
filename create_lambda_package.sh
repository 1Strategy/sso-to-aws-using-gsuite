#! /bin/bash
folder_name="lambda_venv"
if [ $# -gt 0 ]
    then folder_name=$1
fi

rm -r $folder_name
mkdir $folder_name
python3 -m venv ./$folder_name
cd ./$folder_name
source ./bin/activate
pip install --upgrade google-auth google-auth-httplib2 google-api-python-client
cp ../gsuite_user_role_mapping.py ./lib/python3.7/site-packages/
cp ../service.json ./lib/python3.7/site-packages/
cd ./lib/python3.7/site-packages/
zip -r ../../../lambda.zip .
