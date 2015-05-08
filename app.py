#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()

import time
import os
import datetime
import pytz
from threading import Thread
import dateutil.parser

from github import Github
import requests

from flask import Flask, render_template
from flask.ext.socketio import SocketIO


TIMEZONE = pytz.timezone('America/Edmonton')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'n7xw34tydr897123gj9s34r76t'

socketio =SocketIO(app)

thread = None
hub = Github(os.environ['GITHUB_USERNAME'], os.environ['GITHUB_PASSWORD'])

def check_commit(commit_url, timeseries):
    """
    Get information about a particualr commit
    """
    r = requests.get(commit_url)
    data = r.json()
    print(commit_url)
    print(data)
    date = dateutil.parser.parse(data['commit']['committer']['date']).date()
    stats = data['stats']
    timeseries[date.isoformat()].append(stats)


def process_push_event(event, timeseries):
    for commit in event.payload['commits']:
        # check_commit(commit['url'], timeseries)
        local_date = event.created_at.replace(tzinfo=pytz.utc).astimezone(TIMEZONE).date()
        timeseries[local_date.isoformat()] += 1


def process_issues_event(event, timeseries):
    # need to convert created_at from UTC to MST
    local_date = event.created_at.replace(tzinfo=pytz.utc).astimezone(TIMEZONE).date()
    timeseries[local_date.isoformat()] += 1


def recent_issues():
    date_array = [datetime.date.today() + datetime.timedelta(days=-i) for i in range(7)]
    timeseries = {d.isoformat(): 0 for d in date_array}

    user = hub.get_user('mfwarren')
    events = user.get_events()
    for event in events:
        try:
            if event.type == 'IssuesEvent':
                process_issues_event(event, timeseries)
        except:
            break
    return sum(timeseries.values())


def recent_commits():
    date_array = [datetime.date.today() + datetime.timedelta(days=-i) for i in range(7)]
    timeseries = {d.isoformat(): 0 for d in date_array}

    user = hub.get_user('mfwarren')
    events = user.get_events()
    for event in events:
        try:
            if event.type == 'PushEvent':
                process_push_event(event, timeseries)
        except:
            break

    return timeseries[datetime.date.today().isoformat()], sum(timeseries.values())

def background_thread():
    while True:
        issues = recent_issues()
        commits_today, commits_this_week = recent_commits()
        socketio.emit('response', {'issues': issues,
                      'commits': commits_this_week,
                      'commits_today': commits_today,
                      'critical_number': '1/5'}, namespace='')
        time.sleep(60*30)  # 30 minutes


@app.route('/')
def index():
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()
    return render_template('index.html')

@socketio.on('event')
def message(message):
    pass


if __name__ == '__main__':
    socketio.run(app)
