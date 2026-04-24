from flask import Blueprint, current_app, render_template

bp = Blueprint('views', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('favicon.ico')
