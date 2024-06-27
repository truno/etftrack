import click
from datetime import datetime, date, timedelta
from flask import Flask, render_template
from flask_login import current_user, login_user, LoginManager, logout_user
from auth.auth import auth_bp
from funds.funds import funds_bp
from config import Config
from models import db, User, Role, Fund, Holding, Stock, Price, Snapshot
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore
import flask_admin as admin
#from flask_migrate import Migrate
#from flask_marshmallow import Marshmallow
from flask_bootstrap import Bootstrap
from etfutil import load_current_holdings, load_database, reset_all_prices

def create_app():
    app = Flask('__name__', static_folder='static')
    app.config.from_object(Config)
    app.register_blueprint(auth_bp)
    app.register_blueprint(funds_bp)
    db.init_app(app)

    return app

app = create_app()

login = LoginManager(app)
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)
bootstrap = Bootstrap(app)

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/logout')
def logout():
    logout_user()
    return render_template('index.html', title='Home')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@login.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Fund': Fund, 'Holding': Holding,
            'Stock': Stock, 'Price': Price, 'Snapshot': Snapshot}

@app.template_filter()
def numberFormat(value):
    if value:
        return format(int(value), ',d')
    else:
        return '<missing data>'

@app.route('/empty_stocks')
def empty_stocks():
    stocks = Stock.query.all()
    no_children = [s.serialize() for s in stocks if not Price.query.filter_by(yahoo_ticker=s.yahoo_ticker).first()]
    return render_template('empty_stocks.html', stocks=no_children)

@app.cli.command('load_holdings')
@click.argument('path')
def load_holdings(path):
    load_current_holdings(path)

@app.cli.command('load_db')
@click.argument('config_file')
def load_db(config_file):
    db.create_all()
    user_role = Role(name='user')
    super_user_role = Role(name='superuser')
    db.session.add(user_role)
    db.session.add(super_user_role)
    db.session.commit()
    first_user = user_datastore.create_user(username='admin',
                                            email='geoluc8@gmail.com',
                                            roles=[user_role, super_user_role])
    first_user.set_password(password='admin')
    user_datastore.toggle_active(first_user)
    db.session.commit()

    load_database(config_file)

@app.cli.command('reset_prices')
def reset_prices():
    reset_all_prices()

if __name__ == "__main__":
    app.run(debug=True)
    app.wsgi_app = DebuggedApplications(app.wsgi_app, evalex=True)
