A work in progress to create utilities for [Moves](http://moves-app.com/), an activity 
tracker for Android and iOS, including displaying tracks on a web map and GeoJSON export.

## Hosted

The easiest way to use the utilities is at [moves.husk.org](http://moves.husk.org/), where 
you can use the site simply by authenticating on your mobile device. It's hosted on Heroku, 
and all the requisite files are in the repository.

## Development

If you'd like to hack on a copy of this, as well as the standard `git clone` you'll need to 
set up environment variables. I did this by

* generating an app_secret: from a Python shell, `import os; os.urandom(24)`
* getting the client variables from the Moves [developer site](https://dev.moves-app.com/apps/)
* pushing the variables into my shell with ``export `cat .env` ``

For the Python packages, you'll need to run:

* `git submodule init`
* `git submodule update`
* `virtualenv .`
* `source bin/activate`
* `pip install -r requirements.txt`

and then you're ready to run the server:

* `python moves-utilities.py`
