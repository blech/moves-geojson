import logging
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta
from functools import wraps
from json import dumps

import memcache
from dateutil.relativedelta import relativedelta
from flask import Flask, Response, redirect, render_template, request, session, url_for
from moves import MovesClient, MovesAPIError

app = Flask(__name__)
app.secret_key = os.environ['app_secret']

client_id = os.environ['client_id']
client_secret = os.environ['client_secret']
Moves = MovesClient(client_id, client_secret)

mc = memcache.Client(['127.0.0.1:11211'], debug=0)

logging.basicConfig()
logging.StreamHandler(sys.stdout)
logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

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
        return render_template("about.html", auth=True)

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

@app.route("/about")
def about():
    return render_template("about.html", auth=False)

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
    months = get_month_range(profile['profile']['firstDate'])

    return render_template("list.html", profile=profile, summary=summary, months=months, days=using_for)

@app.route('/list/<month>')
@require_token
def month(month):
    if '-' in month:
        (y, m) = month.split('-')
    else:
        (y, m) = (month[0:4], month[4:6])

    dateobj = make_date_from("%s%s01" % (y, m))
    month = dateobj.strftime("%Y-%m")

    profile = get_profile(access_token=session['token'])

    summary = get_summary_month(access_token=session['token'], month=month)
    summary.reverse() # TODO sort by activity (activities?) do we need sort(summary, by)?

    for day in summary:
        day['dateObj'] = make_date_from(day['date'])
        day['summary'] = make_summaries(day)

    months = get_month_range(profile['profile']['firstDate'], excluding=month)

    return render_template("month.html", profile=profile, summary=summary, months=months)

@app.route("/map/<date>")
@require_token
def map(date):
    api_date = date.replace('-', '')
    validate_date(api_date)



    return render_template("map.html", date=date)

@app.route("/geojson/<date>")
@require_token
def geojson(date):
    api_date = date.replace('-', '')
    validate_date(api_date)
    
    info = get_storyline(access_token=session['token'], date=api_date)

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

def get_storyline(access_token, date):
    profile = get_profile(access_token)
    key = ":".join((str(profile['userId']), str(date)))

    storyline = mc.get(key)
    if not storyline:
        storyline = Moves.user_storyline_daily(date, trackPoints={'true'}, access_token=access_token)
        # only cache if it's earlier than today, since today is changing
        # TODO figure out utcnow implications / use profile offset
        if date < datetime.now().strftime("%Y%m%d"):
            mc.set(key, storyline, time=86400)

    return storyline

def get_summary_month(access_token, month):
    profile = get_profile(access_token)
    key = ":".join((str(profile['userId']), str(month)))

    summary = mc.get(key)
    if not summary:
        summary = Moves.user_summary_daily(month, access_token=access_token)
        mc.set(key, summary, time=86400)

    return summary

### utilities

def validate_date(date):
    date = date.replace('-', '')
    try:
        date_obj = make_date_from(date)
    except Exception, e:
        raise Exception("Date is not in the valid format: %s" % e)

    # TODO use profile, figure out timezones
    # until then, let's let Moves figure it out
    # if date_obj > datetime.now().date():
    #     raise Exception("Date is in the future")

def make_date_from(yyyymmdd):
    yyyymmdd = yyyymmdd.replace('-', '')

    year = int(yyyymmdd[0:4])
    month = int(yyyymmdd[4:6])
    day = int(yyyymmdd[6:8])

    logging.info(year, month, day)
    return date(year, month, day)

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
    months = []

    first = make_date_from(first_date)
    if last_date:
        cursor = make_date_from(last_date)
    else:
        cursor = datetime.utcnow().date()

    if excluding:
        (x_year, x_month) = excluding.split('-')
    else:
        x_year = x_month = "0"

    while cursor.year > first.year or cursor.month >= first.month:
        if not(cursor.year == int(x_year) and cursor.month == int(x_month)):
            months.append(cursor)
        cursor = cursor - relativedelta(months=1)

    return months

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
        # TODO convert activity?
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

    return feature

def geojson_move(segment):
    features = []
    lookup = {'wlk': 'Walking', 'trp': 'Transport', 'run': 'Running', 'cyc': 'Cycling'}
    stroke = {'wlk': '#00d45a', 'trp': '#000000', 'run': '#93139a', 'cyc': '#00ceef'}

    for activity in segment['activities']:
        trackpoints = activity['trackPoints']
        coordinates = [[point['lon'], point['lat']] for point in trackpoints]
        timestamps = [point['time'] for point in trackpoints]
        geojson = {'type': 'Feature', 'geometry': {}, 'properties': {}}
        geojson['geometry'] = {'type': 'LineString', 'coordinates': coordinates}
        for key in activity.keys():
            if key != 'trackPoints':
                geojson['properties'][key] = activity[key]

        # add a description & the saved timestamps
        geojson['properties']['description'] = make_summary(activity, lookup)
        geojson['properties']['times'] = timestamps

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
    
# @app.errorhandler(500)
# def internal_error(e):
#     return render_template('500.html'), 500

def handle_exception(e):
    # handle TwitterHTTPError
    # TODO use type() matching not duck typing, maybe?
    if type(e) == MovesAPIError:
        if e[1]:
            error = eval(e[1])['error']
        else:
            error = e
        logger.error("Handled Moves API error. Details: %r" % e)
        logger.exception(e)
        return render_template('500.html', error=error, type='moves'), 500

    logger.error("Handled non-Moves exception %s: %r" % (type(e), e))
    logger.exception(e)
    return render_template('500.html', error=e, type="other"), 500

app.handle_exception = handle_exception


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7771, debug=True)
