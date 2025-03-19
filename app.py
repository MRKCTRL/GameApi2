from flask import Flask, jsonify, request 
from flsk_sqlalchemy import SQLAlchemy 
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests 
import os

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration



app=Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'postgresql://username:password@localhost/game_api')
app.config['JWT_SECRET_KEY'] = 'super-secret'
db=SQLAlchemy(app)
jwt=JWTManager(app)

sentry_sdk.init(
    dsn='',
    integrations=[FlaskIntegration()]
)


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
    response= requests.get(f"https://{RAPIDAPI_HOST}/{endpoint}", headers=headers, params=paramss)
    return response.json 


@app.route('/api/register', methods=["POST"])
def register():
    data=request.get_json()
    username=data['username']
    password=data['password']
    new_user=User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User register successfully'})


@app.route('api/login', methods=["POST"])
def login():
    data=request.get_json()
    user=User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        access_token=create_access_token(identity=user.id)
        return jsonify({'access_token': access_token}), 401
    
@app.route('/api/twitch-game', methods=["GET"])
@jwt_required()
def get_esports_news():
    data=fetch_rapidapi_data('esport-news-endpoint')
    return jsonify(data)


@app.route('/api/mmo-games', methods=["GET"])
@jwt_required()
def get_mmo_games():
    data=fetch_rapidapi_data('mmo-games-endpoint')
    return jsonify(data)


@app.route('/api/playstaion-deals', methods=['GET'])
@jwt_required()
def get_playstaion_deals():
    data=fetch_rapidapi_data('playstation-double-endpoint')
    return jsonify(data)


if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)    