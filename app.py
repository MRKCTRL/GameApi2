from flask import Flask, jsonify, request 
from flask_sqlalchemy import SQLAlchemy 
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests 
import os

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from flask_caching import Cache


from flask_limiter import Limiter 
from flask_limiter.util import get_remote_address


from celery import Celery 
from celery.schedules import cronotab


from flask_marshmallow import Marshmallow

ma=Marshmallow(app)
app=Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'postgresql://username:password@localhost/game_api')
app.config['JWT_SECRET_KEY'] = 'super-secret'
db=SQLAlchemy(app)
jwt=JWTManager(app)

cache=Cache(app,config={'CACHE_TYPE': 'SimpleCache'})
limiter=Limiter(app, key_func=get_remote_address)
celery=Celery(app.name, broker='redis://localhost:6379/0')

sentry_sdk.init(
    dsn='',
    integrations=[FlaskIntegration()]
)

celery.conf.beat___schedule= {
    
    'fetch-twitch-games-every-hour': {
        'task': 'app.fetch_twitch_games',
        'schedule': cronotab(minute=0, hour='*/1'),
    },
}


class UserSchema(ma.Schema):
    class Meta:
        fields=('id', 'username')

user_schema=UserSchema()
users_schema=UserSchema(many=True)


class User(db.model):
    id=db.Column(db.Integer, primary_key=True)
    username=db.column(db.String(80), unique=True, nullable=False)
    password=db.Column(db.String(120), nullable=False)


RAPIDAPI_KEY= os.getenv('')
RAPIDAPI_HOST=os.getenv('')

def fetch_rapidapi_data(endpoint, params=None):
    headers= {
        'X-RapidAPI-Key': RAPIDAPI_KEY,
        'X-RapidAPI-Host': RAPIDAPI_HOST,
    }
    response= requests.get(f"https://{RAPIDAPI_HOST}/{endpoint}", headers=headers, params=params)
    return response.json 


@app.route('/api/register', methods=["POST"])
def register():
    data=request.get_json()
    errors=user_schema.validate(data)
    username=data['username']
    password=data['password']
    new_user=User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User register successfully'})
    if errors:
        return jsonify(errors), 400


@app.route('api/login', methods=["POST"])
def login():
    data=request.get_json()
    user=User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        access_token=create_access_token(identity=user.id)
        return jsonify({'access_token': access_token}), 401
    
@app.route('/api/twitch-games', methods=["GET"])
@cache.cached(timeout=300)
@limiter.limit("10 per minute")
@jwt_required()
@celery.task
def get_twitch_games():
    data=fetch_rapidapi_data('twitch-games-endpoint')
    return jsonify(data)

@app.route('/api/esport-news', methods=["GET"])
@cache.cached(timeout=300)
@limiter.limit("10 per minute")
@jwt_required()
@celery.task
def get_esports_news():
    data=fetch_rapidapi_data('esport-news-endpoint')
    return jsonify(data)


@app.route('/api/mmo-games', methods=["GET"])
@cache.cached(timeout=300)
@limiter.limit("10 per minute")
@jwt_required()
@celery.task
def get_mmo_games():
    data=fetch_rapidapi_data('mmo-games-endpoint')
    return jsonify(data)


@app.route('/api/playstaion-deals', methods=['GET'])
@cache.cached(timeout=300)
@limiter.limit("10 per minute")
@jwt_required()
@celery.task
def get_playstaion_deals():
    data=fetch_rapidapi_data('playstation-double-endpoint')
    return jsonify(data)


if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)    