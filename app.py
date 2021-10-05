"""
A sample Hello World server.
"""
import os
import requests

from flask import Flask, render_template, request, redirect, make_response
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from mta import *

# pylint: disable=C0103
app = Flask(__name__)
CORS(app)
auth = HTTPBasicAuth()

users = {
    'teo': generate_password_hash('boom'),
    'chris': generate_password_hash('sirhc'),
    'ashley': generate_password_hash('yelhsa'),
    'rustam': generate_password_hash('matsur')
}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username

@app.route('/')
@auth.login_required
def hello():

    """Get Cloud Run environment variables."""
    service = os.environ.get('K_SERVICE', 'Unknown service')
    revision = os.environ.get('K_REVISION', 'Unknown revision')

    return redirect('/dash')
    # return render_template('login.html')

@app.route('/dash', methods = ['GET', 'POST'])
@auth.login_required
def dash():
    user = auth.current_user()
    # return render_template('dash.html', currentUser = currentUser)
    return render_template('dash.html',
        user=user)

@app.route('/compute')
@auth.login_required
def compute():
    """Return a friendly HTTP greeting."""
    message = "Congratulations!"

    """Get Cloud Run environment variables."""
    service = os.environ.get('K_SERVICE', 'Unknown service')
    revision = os.environ.get('K_REVISION', 'Unknown revision')

    startDate = request.args.get('startdate')
    endDate = request.args.get('enddate')
    viewID = request.args.get('viewid')
    userID = request.args.get('userid')
    journeyID = request.args.get('journeyid')
    sliderVal = float(request.args.get('sliderval'))
    
    try:
        main(startDate, endDate, viewID, userID, journeyID, sliderVal)
    except Exception as e:
        print(f'something went wrong here: {e}')
    
    # return render_template('dash.html')
    return (f'Guru meditation: {os.urandom(24)}')

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    app.run(debug=True, port=server_port, host='0.0.0.0', threaded=True)
