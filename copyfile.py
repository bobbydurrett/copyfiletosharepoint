"""
Hacked together from https://github.com/microsoftgraph/python-sample-console-app

Modified it to copy a file to Sharepoint.

"""
# Copyright (c) Microsoft and Bobby Durrett. 
# All rights reserved. Licensed under the MIT license.
# See LICENSE in the project root for license information.
import pprint
import config
import mimetypes
import os
import urllib
import webbrowser
from adal import AuthenticationContext
import pyperclip
import requests
import json

def api_endpoint(url):
    """Convert a relative path such as /me/photo/$value to a full URI based
    on the current RESOURCE and API_VERSION settings in config.py.
    """
    if urllib.parse.urlparse(url).scheme in ['http', 'https']:
        return url # url is already complete
    return urllib.parse.urljoin(f'{config.RESOURCE}/{config.API_VERSION}/',
                                url.lstrip('/'))
    
def device_flow_session(client_id, auto=False):
    """Obtain an access token from Azure AD (via device flow) and create
    a Requests session instance ready to make authenticated calls to
    Microsoft Graph.

    client_id = Application ID for registered "Azure AD only" V1-endpoint app
    auto      = whether to copy device code to clipboard and auto-launch browser

    Returns Requests session object if user signed in successfully. The session
    includes the access token in an Authorization header.

    User identity must be an organizational account (ADAL does not support MSAs).
    """
    ctx = AuthenticationContext(config.AUTHORITY_URL, api_version=None)
    device_code = ctx.acquire_user_code(config.RESOURCE,
                                        client_id)

    # display user instructions
    if auto:
        pyperclip.copy(device_code['user_code']) # copy user code to clipboard
        webbrowser.open(device_code['verification_url']) # open browser
        print(f'The code {device_code["user_code"]} has been copied to your clipboard, '
              f'and your web browser is opening {device_code["verification_url"]}. '
              'Paste the code to sign in.')
    else:
        print(device_code['message'])

    token_response = ctx.acquire_token_with_device_code(config.RESOURCE,
                                                        device_code,
                                                        client_id)
    if not token_response.get('accessToken', None):
        return None

    session = requests.Session()
    session.headers.update({'Authorization': f'Bearer {token_response["accessToken"]}',
                            'SdkVersion': 'sample-python-adal',
                            'x-client-SKU': 'sample-python-adal'})
    return session

def upload_file(session,filename,driveid,folder):

    """Upload a file to Sharepoint.

    """
    fname_only = os.path.basename(filename)

    # create the Graph endpoint to be used
    
    endpoint = f'drives/{driveid}/root:/{folder}/{fname_only}:/createUploadSession'
        
    start_response = session.put(api_endpoint(endpoint))
    json_response = start_response.json()
    upload_url = json_response["uploadUrl"]
    
# upload in chunks

    filesize = os.path.getsize(filename)
        
    with open(filename, 'rb') as fhandle:
        start_byte = 0
        while True:
            file_content = fhandle.read(10*1024*1024)
            data_length = len(file_content)
            if data_length <= 0:
                break
                
            end_byte = start_byte + data_length - 1
            crange = "bytes "+str(start_byte)+"-"+str(end_byte)+"/"+str(filesize)
            print(crange)

            chunk_response = session.put(upload_url,
                                         headers={"Content-Length": str(data_length),"Content-Range": crange},
                                         data=file_content)
            if not chunk_response.ok:
                print(f'<Response [{chunk_response.status_code}]>')
                pprint.pprint(chunk_response.json()) # show error message
                break

            start_byte = end_byte + 1

    return chunk_response

def get_driveid(session,base_path):
    """
    
Get the drive id for a particular path in Sharepoint.

    """
    tenant = config.TENANT
    get_url=api_endpoint(f'sites/{tenant}.sharepoint.com:{base_path}:/drives?$select=name,id')
    base_return = session.get(get_url)
    print(f'<Response [{base_return.status_code}]>',
          f'bytes returned: {len(base_return.text)}\n')
    if not base_return.ok:
        pprint.pprint(base_return.json()) # display error
        return
    base_data = base_return.json()
    value = base_data["value"]
    for i in value:
        if i["name"] == "Shared Documents":
            drive_id = i["id"]
            return drive_id

def checkin_file(session,driveid,itemid):
    """
    
    checkin a file to Sharepoint.

    """
    # create the Graph endpoint to be used
    
    endpoint = f'drives/{driveid}/items/{itemid}/checkin'
        
    return session.put(api_endpoint(endpoint))

def delete_file(session,filename,driveid,folder):

    """
    
    delete file if it exists

    """
    fname_only = os.path.basename(filename)

    # create the Graph endpoint to be used
    
    endpoint = f'drives/{driveid}/root:/{folder}/{fname_only}'
        
    delete_response = session.delete(api_endpoint(endpoint))
    print(f'<Response [{delete_response.status_code}]>')
    
    return delete_response

def upload_one_file(base_path,folder_path,file_name,session):
    if not session:
        session = device_flow_session(config.CLIENT_ID,True)
    if session:
        driveid = get_driveid(session,base_path)
        
        print('Deleting file')
        delete_response = delete_file(session,file_name,driveid,folder_path)
    
        print('Uploading file')
        upload_response = upload_file(session,file_name,driveid,folder_path)
        json_response = upload_response.json()
        if not upload_response.ok:
            return
        itemid=json_response["id"]
        print('Checking in file')
        checkin_response = checkin_file(session,driveid,itemid)
        print(f'<Response [{checkin_response.status_code}]>')
        return session
       

if __name__ == '__main__':
    base_path = "/sites/YourTeams/YourPath"
    folder_path = "Test/Test2"
    file_name="C:\\temp\\test.txt"
    
    session = False
    
    session = upload_one_file(base_path,folder_path,file_name,session)            

