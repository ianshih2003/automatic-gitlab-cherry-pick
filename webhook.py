import json
from flask import Flask, request, jsonify
import requests
from configparser import ConfigParser
import os
import logging

URL = 'https://gitlab.com/api/v4'
LABEL_HEADER = 'cp-to-'


app = Flask(__name__)

session = requests.Session()


# GitLab webhook endpoint

def initialize_config():
    """ Parse env variables or config file to find program config params

    Function that search and parse program configuration parameters in the
    program environment variables first and the in a config file.
    If at least one of the config parameters is not found a KeyError exception
    is thrown. If a parameter could not be parsed, a ValueError is thrown.
    If parsing succeeded, the function returns a ConfigParser object
    with config parameters
    """

    config = ConfigParser(os.environ)
    # If config.ini does not exists original config object is not modified
    config.read("config.ini")

    config_params = {}
    try:
        config_params["token"] = config["DEFAULT"]["TOKEN"]
        config_params["logging_level"] = os.getenv(
            'LOGGING_LEVEL', config["DEFAULT"]["LOGGING_LEVEL"])
        config_params["log_file"] = os.getenv(
            'LOG_FILE', config["DEFAULT"]["LOG_FILE"])

    except KeyError as e:
        raise KeyError(
            "Key was not found. Error: {} .Aborting server".format(e))

    return config_params


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()

        process_webhook_event(data)

        return jsonify({'message': 'Received'}), 200
    except Exception as e:
        logging.error(f'Error: {e}')


def process_webhook_event(data):
    logging.info(f'Event: {extract_important_data(data)}')
    if valid_webhook_request(data):
        branches = parse_branches(data['object_attributes']['labels'])

        for i, branch in enumerate(branches):
            create_cherry_pick(data, branch, i)


def parse_branches(labels):
    return [label.split(LABEL_HEADER)[1] for label in labels if LABEL_HEADER in label]


def valid_webhook_request(data):
    return 'object_kind' in data and data['object_kind'] == 'merge_request' and any(LABEL_HEADER in label for label in data['object_attributes']['labels']) and data['object_attributes']['action'] == 'merge'


def create_branch(source_branch, branch, project_id):
    validate_response(session.post(f'{URL}/projects/{project_id}/repository/branches',
                                   json={'branch': branch, 'ref': source_branch}), 201)


def validate_response(response, success_code, error_message=None):

    if response.status_code == success_code:
        return response

    else:
        raise Exception(
            f'{error_message}: {response.status_code} {response.json()}')


def get_latest_commit(branch, project_id):

    response = validate_response(
        session.get(f'{URL}/projects/{project_id}/repository/commits', params={'ref_name': branch}), 200, 'Failed to get latest commit')

    return response.json()[:2]


def cherry_pick(hash, target_branch, project_id):

    response = validate_response(
        session.post(f'{URL}/projects/{project_id}/repository/commits/{hash}/cherry_pick', json={
            "branch": target_branch,
        }), 201, 'Failed to create cherry-pick merge request')

    if response:
        print(
            f'Cherry-pick merge request created for {project_id}: {response.json()["web_url"]}')


def create_merge_request(project_id, source_branch, target_branch, merge_request_data, original_commit, merge_commit):
    original_commit_hash = original_commit['short_id']
    original_commit_title = original_commit['title']

    merge_commit_hash = merge_commit['short_id']
    merge_commit_description = merge_commit['message']

    data = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "assignee_ids": [merge_request_data['object_attributes']['assignee_ids']],
        "labels": "cherry-pick",
        "title": f"CP {original_commit_title} into {target_branch}",
        "description": f"{merge_commit_description}\n\n(cherry picked from commit {merge_commit_hash})\n\n{original_commit_hash} {original_commit_title}"
    }

    response = validate_response(
        session.post(f'{URL}/projects/{project_id}/merge_requests', json=data), 201, 'Failed to create merge request')

    if response:
        print(
            f'Merge request created for {project_id}: {response.json()["web_url"]}')


def create_cherry_pick(merge_request_data, target_branch, i):

    base_branch = merge_request_data['object_attributes']['target_branch']
    project_id = merge_request_data['object_attributes']['source_project_id']
    merge_commit, original_commit = get_latest_commit(
        base_branch, project_id)

    commit_hash = merge_commit['short_id']
    cp_branch = f'cherry-pick-{commit_hash}-{i}'

    create_branch(target_branch, cp_branch, project_id)

    cherry_pick(commit_hash, cp_branch, project_id)

    create_merge_request(project_id, cp_branch,
                         target_branch, merge_request_data, original_commit, merge_commit)


def extract_important_data(data):

    source_branch = data['object_attributes']['source_branch']
    target_branch = data['object_attributes']['target_branch']
    source_project_id = data['object_attributes']['source_project_id']
    assignee_ids = data['object_attributes']['assignee_ids']
    labels = data['object_attributes']['labels']
    id = data['object_attributes']['id']
    action = data['object_attributes']['action']

    return ",".join(str(field) for field in [source_branch, target_branch, source_project_id, assignee_ids, labels, id, action])


def initialize_log(logging_level, log_file):
    """
    Python custom logging initialization

    Current timestamp is added to be able to identify in docker
    compose logs the date when the log has arrived
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging_level,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename=log_file
    )


if __name__ == '__main__':
    config = initialize_config()
    initialize_log(config["logging_level"], config["log_file"])
    session.headers.update(
        {'PRIVATE-TOKEN': config["token"], 'Content-Type': 'application/json'})

    app.run(debug=True, host='0.0.0.0', port=5000)
