from flask import Flask, request, jsonify
import requests
import logging

from utils import initialize_config

URL = 'https://gitlab.com/api/v4'
LABEL_HEADER = 'cp-to-'


app = Flask(__name__)

config = initialize_config()

app.logger.setLevel(config['logging_level'])  # Set log level to INFO
handler = logging.FileHandler(config['log_file'])  # Log to a file
formatter = logging.Formatter(
    '%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
app.logger.addHandler(handler)


session = requests.Session()

session.headers.update(
    {'PRIVATE-TOKEN': config["token"], 'Content-Type': 'application/json'})


# GitLab webhook endpoint


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()

        process_webhook_event(data)

        return jsonify({'message': 'Received'}), 200
    except Exception as e:
        app.logger.error(f'Error: {e}')
        return jsonify({'message': 'Received with error, check logs'}), 200


def process_webhook_event(data):
    app.logger.info(f"Event for PR: {data['object_attributes']['id']}")
    if valid_webhook_request(data):
        app.logger.info(f'Event: {extract_important_data(data)}')
        branches = parse_branches(data['object_attributes']['labels'])

        for i, branch in enumerate(branches):
            create_cherry_pick(data, branch, i)


def parse_branches(labels):
    return [label['title'].split(LABEL_HEADER)[1] for label in labels if LABEL_HEADER in label['title']]


def valid_webhook_request(data):
    return 'object_kind' in data and data['object_kind'] == 'merge_request' and any(LABEL_HEADER in label['title'] for label in data['object_attributes']['labels']) and data['object_attributes']['action'] == 'merge'


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
        app.logger.info(
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
        app.logger.info(
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
    labels = ",".join([label['title']
                      for label in data['object_attributes']['labels']])
    id = data['object_attributes']['id']

    return ",".join(str(field) for field in [source_branch, target_branch, source_project_id, assignee_ids, labels, id])


if __name__ == '__main__':
    if config['env'] == 'dev':
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        from waitress import serve
        serve(app, host='0.0.0.0', port=5000)
