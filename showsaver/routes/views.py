from flask import Blueprint, redirect, render_template, url_for
from version import __version__

bp = Blueprint('views', __name__)


@bp.route('/')
def home():
    return render_template('index.html', version=__version__)


@bp.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.svg'))
