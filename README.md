# Automatic gitlab cherry pick

Creates cherry pick merge requests when merging to a branch

For example you have 3 branches:
* prod
* dev
* stg

When merging a PR to production, you will need to cherry pick to development and staging to maintain the branches up to date.

This simple flask server automatically creates the merge requests for you when the PR is merged to production

It will create a cherry pick PR for each label that contains the following format `cp-to-{branch name}`

![image](https://github.com/ianshih2003/automatic-gitlab-cherry-pick/assets/54551203/cb2b7d0c-633e-45ba-b8d7-e2c3250cf0d7)

## Usage

### Installation
```
pip install -r requirements.txt
```

### Execution
```
python3 app.py
```
