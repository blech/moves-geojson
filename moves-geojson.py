import os

from datetime import date, datetime, timedelta
from json import dumps

from flask import Flask, url_for, request, session, redirect, render_template
from moves import MovesClient

app = Flask(__name__)

app.secret_key = os.environ['app_secret']

client_id = os.environ['client_id']
client_secret = os.environ['client_secret']

Moves = MovesClient(client_id, client_secret)

@app.route("/")
def index():
    if 'token' not in session:
        return render_template("auth.html")

    return redirect(url_for('list'))

@app.route("/auth")
def auth():
    oauth_return_url = url_for('oauth_return', _external=True)
    auth_url = Moves.build_oauth_url(oauth_return_url)
    return redirect(auth_url)

@app.route("/oauth_return")
def oauth_return():
    error = request.values.get('error', None)
    if error is not None:
        return error
    oauth_return_url = url_for('oauth_return', _external=True)
    code = request.args.get("code")
    token = Moves.get_oauth_token(code, redirect_uri=oauth_return_url)
    session['token'] = token
    return redirect(url_for('list'))

@app.route('/logout')
def logout():
    if 'token' in session:
        del(session['token'])
    return redirect(url_for('index'))

@app.route('/list')
def list():
    if 'token' not in session:
        return redirect(url_for('index'))

    profile = Moves.user_profile(access_token=session['token'])

    days = get_dates_range(profile['profile']['firstDate'])

    return render_template("list.html", profile=profile, days=days)

#     response = 'User ID: %s<br />First day using Moves: %s' % \
#         (profile['userId'], profile['profile']['firstDate'])
#     return response + "<br /><a href=\"%s\">Info for today</a>" % url_for('today') + \
#         "<br /><a href=\"%s\">Logout</a>" % url_for('logout')

@app.route("/info")
def show_info():
    if 'token' not in session:
        return redirect(url_for('index'))

    profile = Moves.user_profile(access_token=session['token'])
    response = 'User ID: %s<br />First day using Moves: %s' % \
        (profile['userId'], profile['profile']['firstDate'])
    return response + "<br /><a href=\"%s\">Info for today</a>" % url_for('today') + \
        "<br /><a href=\"%s\">Logout</a>" % url_for('logout')


@app.route("/map/<date>")
def map(date):
    if 'token' not in session:
        return redirect(url_for('index'))

    return render_template("map.html", date=date)

@app.route("/geojson/<date>")
def geojson(date):
    if 'token' not in session:
        return redirect(url_for('index'))

    api_date = date.replace('-', '')
    info = Moves.user_storyline_daily(api_date, trackPoints={'true'}, access_token=session['token'])
    
    features = []
    
    for segment in info[0]['segments']:
        if segment['type'] == 'place':
            # features.append(geojson_place(segment)
            pass
        elif segment['type'] == 'move':
            features.extend(geojson_move(segment))

    geojson = {'type': 'FeatureCollection', 'features': features}

    return dumps(geojson)

### utilities

def get_dates_range(firstDate):
    year = int(firstDate[0:4])
    month = int(firstDate[4:6])
    day = int(firstDate[6:8])

    first = date(year, month, day)

    now = datetime.now()
    today = date(now.year, now.month, now.day)

    days = []
    cursor = today
    
    while cursor >= first:
        days.append(cursor)
        cursor = cursor - timedelta(days=1)

    return days


def geojson_move(segment):
    features = []

    for activity in segment['activities']:
        trackpoints = activity['trackPoints']
        coordinates = [[point['lon'], point['lat']] for point in trackpoints]
        geojson = {'type': 'Feature', 'geometry': {}, 'properties': {}}
        geojson['geometry'] = {'type': 'LineString', 'coordinates': coordinates}
        for key in activity.keys():
            if key != 'trackPoints':
                geojson['properties'][key] = activity[key]
        
        features.append(geojson)

    return features

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7771, debug=True)
