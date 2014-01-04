from flask import Flask, url_for, request, session, redirect
from moves import MovesClient

from datetime import datetime, timedelta
from json import dumps

import _keys

app = Flask(__name__)

Moves = MovesClient(_keys.client_id, _keys.client_secret)

@app.route("/")
def index():
    if 'token' not in session:
        oauth_return_url = url_for('oauth_return', _external=True)
        auth_url = Moves.build_oauth_url(oauth_return_url)
        return 'Authorize this application: <a href="%s">%s</a>' % \
            (auth_url, auth_url)
    return redirect(url_for('show_info'))


@app.route("/oauth_return")
def oauth_return():
    error = request.values.get('error', None)
    if error is not None:
        return error
    oauth_return_url = url_for('oauth_return', _external=True)
    code = request.args.get("code")
    token = Moves.get_oauth_token(code, redirect_uri=oauth_return_url)
    session['token'] = token
    return redirect(url_for('show_info'))


@app.route('/logout')
def logout():
    if 'token' in session:
        del(session['token'])
    return redirect(url_for('index'))


@app.route("/info")
def show_info():
    profile = Moves.user_profile(access_token=session['token'])
    response = 'User ID: %s<br />First day using Moves: %s' % \
        (profile['userId'], profile['profile']['firstDate'])
    return response + "<br /><a href=\"%s\">Info for today</a>" % url_for('today') + \
        "<br /><a href=\"%s\">Logout</a>" % url_for('logout')


@app.route("/geojson")
def geojson():
    today = datetime.now().strftime('%Y%m%d')
    info = Moves.user_storyline_daily(today, trackPoints={'true'}, access_token=session['token'])
    
    features = []
    
    for segment in info[0]['segments']:
        if segment['type'] == 'place':
            # features.append(geojson_place(segment)
            pass
        elif segment['type'] == 'move':
            features.extend(geojson_move(segment))

    geojson = {'type': 'FeatureCollection', 'features': features}

    return dumps(geojson)

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

app.secret_key = _keys.secret_key

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7771, debug=True)
