import os
from datetime import date, datetime, timedelta
from functools import wraps
from json import dumps

import memcache
from dateutil.relativedelta import relativedelta
from flask import Flask, Response, redirect, render_template, request, session, url_for
from moves import MovesClient

app = Flask(__name__)

app.secret_key = os.environ['app_secret']

client_id = os.environ['client_id']
client_secret = os.environ['client_secret']

Moves = MovesClient(client_id, client_secret)

mc = memcache.Client(['127.0.0.1:11211'], debug=0)

### decorator
def require_token(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if 'token' not in session:
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated


### main methods

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
@require_token
def list():
    profile = get_profile(access_token=session['token'])

    summary = Moves.user_summary_daily(pastDays=30, access_token=session['token'])
    summary.reverse()

    for day in summary:
        day['dateObj'] = make_date_from(day['date'])
        day['summary'] = make_summaries(day)

    using_for = get_days_using(profile['profile']['firstDate'])
    months = get_month_range(profile['profile']['firstDate'], last_date=summary[-1]['date'])

    return render_template("list.html", profile=profile, summary=summary, months=months, days=using_for)

@app.route('/list/<month>')
@require_token
def month(month):
    profile = get_profile(access_token=session['token'])

    summary = Moves.user_summary_daily(month, access_token=session['token'])
    summary.reverse()

    for day in summary:
        day['dateObj'] = make_date_from(day['date'])
        day['summary'] = make_summaries(day)

    months = get_month_range(profile['profile']['firstDate'], excluding=month)

    return render_template("month.html", profile=profile, summary=summary, months=months)

@app.route("/map/<date>")
@require_token
def map(date):
    # TODO validate date
    return render_template("map.html", date=date)

@app.route("/geojson/<date>")
@require_token
def geojson(date):
    # TODO validate date
    api_date = date.replace('-', '')
    info = Moves.user_storyline_daily(api_date, trackPoints={'true'}, access_token=session['token'])

    features = []

    for segment in info[0]['segments']:
        if segment['type'] == 'place':
            features.append(geojson_place(segment))
        elif segment['type'] == 'move':
            features.extend(geojson_move(segment))

    geojson = {'type': 'FeatureCollection', 'features': features}

    filename = "moves-%s.geojson" % date
    headers = (('Content-Disposition', 'attachment; filename="%s"' % filename),)

    return Response(dumps(geojson), headers=headers, content_type='application/geo+json')

@app.route("/info")
@require_token
def show_info():
    profile = get_profile(access_token=session['token'])
    response = 'User ID: %s<br />First day using Moves: %s' % \
        (profile['userId'], profile['profile']['firstDate'])
    return response + "<br /><a href=\"%s\">Info for today</a>" % url_for('map') + \
        "<br /><a href=\"%s\">Logout</a>" % url_for('logout')

@app.route("/test")
@require_token
def show_test():
    info = Moves.user_storyline_daily('20131231', trackPoints={'true'}, access_token=session['token'])
    return "%r" % info


### moves wrappers
def get_profile(access_token):
    profile = mc.get(str(access_token))
    if not profile:
        profile = Moves.user_profile(access_token=access_token)
        mc.set(str(access_token), profile, time=86400)
    return profile


### utilities

def get_dates_range(first_date):
    first = make_date_from(first_date)

    now = datetime.utcnow() # TODO use profile TZ?
    today = date(now.year, now.month, now.day)

    days = []
    cursor = today
    
    while cursor >= first:
        days.append(cursor)
        cursor = cursor - timedelta(days=1)

    return days

def get_days_using(first_date):
    first = make_date_from(first_date)
    now = datetime.utcnow().date()

    delta = now-first
    return delta.days

def get_month_range(first_date, last_date=None, excluding=None):
    first = make_date_from(first_date)
    if last_date:
        last = make_date_from(last_date)
    else:
        last = datetime.utcnow().date()

    if excluding:
        (x_year, x_month) = excluding.split('-')
    else:
        x_year = x_month = "0"

    months = []
    cursor = last

    if not(cursor.year == int(x_year) and cursor.month == int(x_month)):
        months.append(cursor)

    while cursor >= first:
        cursor = cursor - relativedelta(months=1)
        if not(cursor.year == int(x_year) and cursor.month == int(x_month)):
            months.append(cursor)

    return months

def make_date_from(yyyymmdd):
    year = int(yyyymmdd[0:4])
    month = int(yyyymmdd[4:6])
    day = int(yyyymmdd[6:8])

    return date(year, month, day)

def make_summary(object, lookup):
    return "%s for %.1f km, taking %i minutes" % (lookup[object['activity']], 
            float(object['distance'])/1000, float(object['duration'])/60)

def make_summaries(day):
    returned = {}
    lookup = {'wlk': 'Walked', 'run': 'ran', 'cyc': 'cycled'}

    if not day['summary']:
        return {'wlk': 'No activity'}

    for summary in day['summary']:
        returned[summary['activity']] = make_summary(summary, lookup)

    return returned


def geojson_place(segment):
    feature = {'type': 'Feature', 'geometry': {}, 'properties': {}}

    coordinates = [segment['place']['location']['lon'], segment['place']['location']['lat']]
    feature['geometry'] = {"type": "Point", "coordinates": coordinates}

    for key in segment.keys():
        feature['properties'][key] = segment[key]

    # make a nice duration number as well
    start = datetime.strptime(segment['startTime'], '%Y%m%dT%H%M%SZ')
    end = datetime.strptime(segment['endTime'], '%Y%m%dT%H%M%SZ')
    duration = end-start
    feature['properties']['duration'] = duration.seconds

    # name and description
    if 'name' in segment['place']:
        feature['properties']['title'] = segment['place']['name']
    else:
        feature['properties']['title'] = "Unknown"

    if 'foursquareId' in segment['place']:
        feature['properties']['url'] = "https://foursquare.com/v/"+segment['place']['foursquareId']

    # styling
    feature['properties']['icon'] = {
        "iconUrl": "/static/images/circle-stroked-24.svg",
        "iconSize": [24, 24],
        "iconAnchor": [12, 12],
        "popupAnchor": [0, -12]
    }

#     feature['properties']['marker-symbol'] = 'circle-stroked'
#     feature['properties']['marker-size'] = 'large'

    return feature

def geojson_move(segment):
    features = []
    lookup = {'wlk': 'Walking', 'trp': 'Transport', 'run': 'Running', 'cyc': 'Cycling'}
    stroke = {'wlk': '#00d45a', 'trp': '#000000', 'run': '#93139a', 'cyc': '#00ceef'}

    for activity in segment['activities']:
        trackpoints = activity['trackPoints']
        coordinates = [[point['lon'], point['lat']] for point in trackpoints]
        geojson = {'type': 'Feature', 'geometry': {}, 'properties': {}}
        geojson['geometry'] = {'type': 'LineString', 'coordinates': coordinates}
        for key in activity.keys():
            if key != 'trackPoints':
                geojson['properties'][key] = activity[key]

        # add a description
        geojson['properties']['description'] = make_summary(activity, lookup)

        # add styling
        geojson['properties']['stroke'] = stroke[activity['activity']]
        geojson['properties']['stroke-width'] = 3
        if activity['activity'] == 'trp':
            geojson['properties']['stroke-opacity'] = 0.1
        
        features.append(geojson)

    return features


### error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
    
@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7771, debug=True)
