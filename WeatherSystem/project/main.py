import threading
from datetime import datetime

import pandas as pd
from flask import Flask, render_template, redirect, url_for, request, flash, current_app
from flask_login import LoginManager, UserMixin, current_user, login_user, login_required, logout_user
from flask_sock import Sock
from flask_sqlalchemy import SQLAlchemy
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash, check_password_hash

DB = SQLAlchemy()


class Weather:
    def __init__(self):
        self.weather_current = 'Датчики не подключены'
        self.weather_new = 'Погода не предсказана'
        self.addresses_states = None


WEATHER = Weather()


def output_parser(listofdicts):
    output = ''
    i = 0
    translates = {
        'date': ('Дата', ''),
        'time': ('Время', ''),
        'temperature': ('Температура', '°C'),
        'humidity': ('Влажность', '%'),
        'pressure': ('Давление', 'кПа')
    }

    for d in listofdicts:
        output += f'Плата {i}:\n'
        for key in d.keys():
            output += '- ' + translates[key.lower()][0] + ': ' + str(d[key]) + ' ' + translates[key.lower()][1] + '\n'
        i += 1
    return output


def date_toNum(obj):
    cut = str(obj).partition('-')[2].partition('-')[0]
    return int(cut)


def time_toNum(obj):
    cut = str(obj).partition(':')[0]
    return int(cut)


def predictWeather(hours):
    if hours < 1 or hours > 12:
        return False
    else:
        full_reg_result = list()
        for i in range(len(current_app.config['BLE_ADDRESSES'])):
            df = pd.read_sql(f'value{i}', DB.engine, 'id')
            print(df)

            cols = df.columns.to_list()

            xData = df.copy()
            xData[cols[0]] = xData[cols[0]].apply(lambda x: date_toNum(x))
            xData[cols[1]] = xData[cols[1]].apply(lambda x: time_toNum(x))
            yDatas = [xData[cols[i]].shift(-12) for i in range(2, len(cols), 1)]

            reg_result = dict()
            for yData in yDatas:
                print(yData)
                yData = yData[0:len(yData)-12]
                print(yData)
                regression = LinearRegression()
                regression.fit(xData[0:len(xData)-12], yData)

                reg_result[yData.name] = regression.predict(xData[12-hours:12-hours+1])[0]

            full_reg_result.append(reg_result)
            print(reg_result)

        WEATHER.weather_new = full_reg_result

        return True


class User(UserMixin, DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    login = DB.Column(DB.String(1000), unique=True)
    password = DB.Column(DB.String(200))
    access_level = DB.Column(DB.Integer)


class UserLog(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    user_id = DB.Column(DB.Integer, DB.ForeignKey('user.id'))
    action_date = DB.Column(DB.DateTime)
    action_type = DB.Column(DB.String(100))


def createValues(config):
    addressTables = list()
    for i in range(config):
        addressTables.append(DB.Table(
            f'value{i}',
            DB.Column('id', DB.Integer, primary_key=True),
            DB.Column('date', DB.Date),
            DB.Column('time', DB.Time),
            DB.Column('temperature', DB.Float),
            DB.Column('humidity', DB.Float),
            DB.Column('pressure', DB.Float),
            extend_existing=False
        ))
    return addressTables


def addUserLog(user_id, action_type):
    user_log = UserLog(
        user_id=user_id,
        action_date=datetime.now().isoformat(),
        action_type=action_type
    )
    DB.session.add(user_log)


# create app function

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config.cfg')
    DB.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)
    login_manager.login_message = 'Необходимо войти, чтобы получить доступ к этой странице.'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    user_sock = Sock()
    user_sock.init_app(app)

    @user_sock.route('/echo')
    def echo(sock):
        while True:
            data_in = sock.receive()
            print('sock вход:', data_in)

            if data_in == 'weather_current':
                try:
                    sock.send('0_' + output_parser(WEATHER.weather_current))
                except AttributeError:
                    sock.send('0_' + 'Датчики не подключены')
            else:
                result = predictWeather(int(data_in))
                if result:
                    sock.send('1_' + output_parser(WEATHER.weather_new))
                else:
                    sock.send('1_' + 'Предсказание невозможно сделать')

    app.use_reloader = False
    app.debug = False

    app.add_url_rule('/', view_func=index)
    app.add_url_rule('/profile', view_func=login_required(profile))
    app.add_url_rule('/weather', view_func=login_required(weather))
    app.add_url_rule('/login', view_func=login)
    app.add_url_rule('/login', view_func=login_post, methods=['POST'])
    app.add_url_rule('/signup', view_func=signup)
    app.add_url_rule('/signup', view_func=signup_post, methods=['POST'])
    app.add_url_rule('/logout', view_func=login_required(logout))

    return app


# index page

def index():
    return render_template('index.html')


def profile():
    return render_template(
        'profile.html',
        name=current_user.login,
        access_level=current_user.access_level,
        addresses_states=WEATHER.addresses_states
    )


# weather

def weather():
    return render_template('weather.html', access_level=current_user.access_level)


# auth login

def login():
    return render_template('login.html')


def login_post():
    user_login = request.form.get('login')
    user_password = request.form.get('password')
    user_remember = True if request.form.get('remember') else False

    user = User.query.filter_by(login=user_login).first()

    if not user or not check_password_hash(user.password, user_password):
        flash('Пожалуйста, проверьте правильность ввода логина и пароля.')
        return redirect(url_for('login'))

    login_user(user, remember=user_remember)

    addUserLog(user.id, 'Пользователь вошёл')
    DB.session.commit()

    return redirect(url_for('profile'))


# auth signup

def signup():
    return render_template('signup.html')


def signup_post():
    signup_code = request.form.get('signup_code')
    user_login = request.form.get('login')
    user_password = request.form.get('password')
    signup_error = False

    if signup_code != current_app.config['SIGNUP_CODE']:
        flash('Введено неправильное кодовое слово.', category='wrong_code')
        signup_error = True

    if len(user_login) < current_app.config['MIN_LOGIN_SIZE']:
        flash(f"Логин должен быть не короче {current_app.config['MIN_LOGIN_SIZE']} символов.", category='short_password')
        signup_error = True

    if len(user_password) < current_app.config['MIN_PASSWORD_SIZE']:
        flash(f"Пароль должен быть не короче {current_app.config['MIN_PASSWORD_SIZE']} символов.", category='short_login')
        signup_error = True

    if signup_error:
        return redirect(url_for('signup'))

    with current_app.app_context():
        user = User.query.filter(User.login == user_login).first()

    if user:
        addUserLog(user.id, 'Попытка создания уже существующего пользователя')
        DB.session.commit()
        flash('Такой логин уже существует.', category='wrong_user')
        return redirect(url_for('signup'))

    new_user = User(login=user_login,
                    password=generate_password_hash(user_password, method='pbkdf2'),
                    access_level=1)
    DB.session.add(new_user)
    DB.session.commit()

    user = User.query.filter(User.login == user_login).first()
    addUserLog(user.id, 'Пользователь создан')
    DB.session.commit()

    return redirect(url_for('login'))


# auth logout

def logout():
    addUserLog(current_user.id, 'Пользователь вышел')
    DB.session.commit()
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    ws_app = create_app()
    with ws_app.app_context():
        createValues(len(ws_app.config['BLE_ADDRESSES']))
        DB.create_all()

    flask_thread = threading.Thread(target=ws_app.run, daemon=True)

    from ble_read_to_db import readAll

    stop_event = threading.Event()

    ble_thread = threading.Thread(target=readAll, kwargs={
        'addresses': ws_app.config['BLE_ADDRESSES'],
        'param_service_uuid': ws_app.config['BLE_SERVICE_UUID'],
        'read_delay': 15,
        'stop_event': stop_event,
        'weather': WEATHER
    })

    WEATHER.addresses_states = [[address, 0] for address in ws_app.config['BLE_ADDRESSES']]

    flask_thread.start()
    ble_thread.start()

    try:
        while True:
            input()
    except KeyboardInterrupt:
        stop_event.set()
