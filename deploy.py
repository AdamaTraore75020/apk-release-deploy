#!/usr/bin/python3
#
# Copyright (C) 2019 Oleg Shnaydman
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import os
import argparse
import requests
import json
import re

DROPBOX_ERROR_CODE = 1
TEMPLATE_ERROR_CODE = 3
CHANGES_ERROR_CODE = 4
OUTPUT_FILE_PARSING_ERROR = 5

DROPBOX_UPLOAD_ARGS = {
    'path': None,
    'mode': 'overwrite',
    'autorename': True,
    'strict_conflict': True
}
DROPBOX_UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload'

DROPBOX_SHARE_DATA = {
    'path': None,
    'settings': {
        'requested_visibility': 'public'
    }
}
DROPBOX_SHARE_URL = 'https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings'

DROPBOX_DELETE_DATA = {
    'path' : None
}
DROPBOX_DELETE_URL = 'https://api.dropboxapi.com/2/files/delete_v2'


def upload_to_dropbox(target_file_name, source_file, dropbox_token, dropbox_folder):
    '''Upload file to dropbox
    
    Args:
        target_file_name (str): Uploaded file will be rename to this file name.
        source_file (str): File that is going to be uploaded.
        dropbox_token (str): Dropbox API key.
        dropbox_folder (str): Dropbox target folder.

    Returns:
        str: Shared url for download.
    '''
    dropbox_path = '/{folder}/{file_name}'.format(folder=dropbox_folder, file_name=target_file_name)
    DROPBOX_UPLOAD_ARGS['path'] = dropbox_path
    DROPBOX_SHARE_DATA['path'] = dropbox_path
    DROPBOX_DELETE_DATA['path'] = dropbox_path

    # Try to delete the file before upload
    # It's possible to overwrite but this way is cleaner
    headers = {'Authorization': 'Bearer ' + dropbox_token,
            'Content-Type': 'application/json'}
    
    requests.post(DROPBOX_DELETE_URL, data=json.dumps(DROPBOX_DELETE_DATA), headers=headers)

    headers = {'Authorization': 'Bearer ' + dropbox_token,
               'Dropbox-API-Arg': json.dumps(DROPBOX_UPLOAD_ARGS),
               'Content-Type': 'application/octet-stream'}

    # Upload the file
    r = requests.post(DROPBOX_UPLOAD_URL, data=open(source_file, 'rb'), headers=headers)

    if r.status_code != requests.codes.ok:
        print("Failed: upload file to Dropbox: {errcode}".format(errcode=r.status_code))
        return None

    headers = {'Authorization': 'Bearer ' + dropbox_token,
               'Content-Type': 'application/json'}

    # Share and return downloadable url
    r = requests.post(DROPBOX_SHARE_URL, data=json.dumps(DROPBOX_SHARE_DATA), headers=headers)

    if r.status_code != requests.codes.ok:
        print("Failed: get share link from Dropbox {errcode}".format(errcode=r.status_code))
        return None

    # Replace the '0' at the end of the url with '1' for direct download
    return re.sub('dl=.*', 'raw=1', r.json()['url'])


def get_app(release_dir):
    '''Extract app data
    
    Args:
        release_dir (str): Path to release directory.

    Returns:
        (str, str): App version and path to release apk file.
    '''
    output_path = os.path.join(release_dir, 'output.json')

    with(open(output_path)) as app_output:
        json_data = json.load(app_output)

    apk_details_key = ''
    if 'apkInfo' in json_data[0]:
        apk_details_key = 'apkInfo'
    elif 'apkData' in json_data[0]:
        apk_details_key = 'apkData'
    else:
        print("Failed: parsing json in output file")
        return None, None

    app_version = json_data[0][apk_details_key]['versionName']
    app_file = os.path.join(release_dir, json_data[0][apk_details_key]['outputFile'])
    return app_version, app_file


def get_target_file_name(app_name, app_version):
    '''Generate file name for released apk, using app name and version:
    app_name - MyApp
    version - 1.03
    result: myapp_1_03.apk
    
    Args:
        app_name (str): App name.
        app_version (str): App version.

    Returns:
        str: App file name.
    '''
    app_name = app_name.lower()
    app_version = app_version.replace('.', '_')
    return '{name}_{version}.apk'.format(name=app_name, version=app_version).replace(' ','')


def get_changes(change_log_path):
    '''Extract latest changes from changelog file.
    Changes are separated by ##

    Args:
        change_log_path (str): Path to changelog file.

    Returns:
        str: Latest changes.
    '''
    with(open(change_log_path)) as change_log_file:
        change_log = change_log_file.read()

    # Split by '##' and remove lines starting with '#'
    latest_version_changes = change_log.split('##')[0][:-1]
    latest_version_changes = re.sub('^#.*\n?', '', latest_version_changes, flags=re.MULTILINE)

    return latest_version_changes
