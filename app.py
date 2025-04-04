from flask import Flask, jsonify, request 
from flask_sqlalchemy import SQLAlchemy 
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests 
import os

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from flask_caching import Cache


from flask_limiter import Limiter 

from flask_jwt_extended import creat_refresh_token, jwt_refresh_token_required
from flask_limiter.util import get_remote_address
from flask import g

from celery import Celery 
from celery.schedules import cronotab

from flask_socketio import SocketIO, emit

import psycopg2
from psycopg2.extras import RealDictCursor
 
import pandas as pd 


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


from flask_marshmallow import Marshmallow
from marshmallow import Schema, fields

from werkzeug.secruity import generate_password_hash, check_password_hash

import os 
from dotenv import loadenv

from flask_migrate import Migrate

from flask_cors import CORS

from flask_talisman import Talisman

import logging 
from pythonjsonlogger import jsonlogger

from celery import Celery

load_dotenv()



app=Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'postgresql://username:password@localhost/game_api')
app.config['SQLALCHEMY_POOL_SIZE'] = 20
app.config['JWT_SECRET_KEY'] = 'super-secret'
db=SQLAlchemy(app)
cache=Cache(app, config={'CACHE_TYPE': 'RedisCache', 'CACHE_REDIS_URL':'redis://localhost:6379'})


CORS(app, resources={r"/api/*": {"origins": "https;// #fill this"}})
jwt=JWTManager(app)

logger=logging.getLogger()
handler= logging.StreamHandler()
formatter=jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)


ma=Marshmallow(app)
migrate=Migrate(app, db)
socketio=SocketIO(app)

Talisman(app)

conn=psycopg2.connect("dbname=game_api user+username password=password")
query= "SELECT id, title, genre, tags FROM games"
games_df =pd.read_sql(query, conn)
conn.close()



hashed_pw=generate_password_hash('user_password')
check_password_hash(hashed_pw, 'input_password') 

games_df['features'] = games_df['genre'] + ' ' + games_df['tags'].apply(lambda x: ' '.join(x))
vectorizer=TfidfVectorizer()
tfidf_matrix= vectorizer.fit_transform(games_df['features'])


similarity_matrix=cosine_similarity(tfidf_matrix, tfidf_matrix)

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
@celery.task
def process_game_data(data):
    # write the code for this 
    pass



class UserSchema(ma.Schema):
    class Meta:
        fields=('id', 'username')

user_schema=UserSchema()
users_schema=UserSchema(many=True)


class User(db.model):
    id=db.Column(db.Integer, primary_key=True)
    username=db.column(db.String(80), unique=True, nullable=False)
    password=db.Column(db.String(120), nullable=False)
    

class GameSchema(Schema):
    title= fields.Str(required=True)
    genre=fields.Str(required=True)

schema = GameSchema()
errors = schema.validate(request.json)
if errors:
    return jsonify(errors), 400

DATABASE_CONFIG ={
    'host': 'localhost',
    'database': 'game_api',
    'user': '',
    'password' : '',
    'port' : '5432' 
}

def get_db_connection():
    if 'db_conn' not in g:
        g.db_conn = psycopg2.connect(
            host=os.getenv['host'],
            database=os.getenv['database'],
            user=os.getenv['user'],
            password=os.getenv['password'],
            port=os.getenv['port'],
            cursor_factory=RealDictCursor
        )
        return g.db_conn

def close_db_connection(e=None):
    db_conn =g.pop('db_conn', None)
    if db_conn is not None:
        db_conn.close()


def init_db(app):
    with app.app_context():
        conn = get_db_connection()
        cursor=conn.cursor()
        
        
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS USERS (
                           ID SERIAL PRIMARY KEY,
                           username VARCHAR(80) UNIQUE NOT NULL,
                           password VARCHAR(120) NOT NULL
                       )
                       """)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS user_preferences (
                           user_id INTEGER REFERENCES users(id),
                           game_id INTEGER REFERENCES games(id),
                           liked BOOLEAN DEFAULT TRUE,
                           PRIMARY KEY  (user_id, game_id)
                       )
                       """)
        conn.commit()
        cursor.close()
        
app.teardown_appcontext(close_db_connection)
init_db(app)

RAPIDAPI_KEY= os.getenv('')
RAPIDAPI_HOST=os.getenv('')

def recommend_games(game_id, top_n=5):
    game_index=games_df[games_df['id'] == game_id].index[0]
    
    
    similarity_scores=list(enumerate(similarity_matrix[game_index]))
    
    similarity_scores=sorted(similarity_scores, key=lambda x: x[1], reverse=True)
    
    top_games=similarity_scores[1:top_n + 1]
    
    recommended_games=[]
    for index, score in top_games:
        recommended_games.append({
            'id': games_df.iloc[index]['id'],
            'title': games_df.iloc[index]['title'],
            'score': score
        })
    return recommended_games
    


def fetch_rapidapi_data(endpoint, params=None):
    headers= {
        'X-RapidAPI-Key': RAPIDAPI_KEY,
        'X-RapidAPI-Host': RAPIDAPI_HOST,
    }
    response= requests.get(f"https://{RAPIDAPI_HOST}/{endpoint}", headers=headers, params=params)
    return response.json 

@app.route('/admin')
@jwt_required()
def admin_dashboard():
    current_user=get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({"error": "Admin access required"}), 403
    return jsonify({"message": "Welcome, Admin"})

@socketio.on('new_deal')
def handle_new_deal(data):
    emit('deal_alert', data, broadcast=True)


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
    
    
@app.route('/api/data')
@limiter.limit("100 per day")
def get_data():
    return jsonify({"data": "protected"})



@app.route('/api/refresh', methods=['POST'])
@jwt_refresh_token_required
def refresh():
    current_user=get_jwt_identity()
    new_token=create_access_token(identity=current_user)
    return jsonify({'access_token': new_token})

@app.route('/api/games')
@cache.cached(timeout=300)
def get_games():
    conn = get_db_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM games")
    games= cursor.fetchall()
    cursor.close()
    return jsonify(games)

@app.route('/api/like-game', methods=['POST'])
@jwt_required()
def like_game():
    user_id=get_jwt_identity()
    game_id=request.json.get('game_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_preferences (user_id, game_id, liked)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (user_id, game_id) 
            DO UPDATE SET liked = NOT user_preferences.liked
            RETURNING liked
        """, (user_id, game_id))
        
        result = cursor.fetchone()
        conn.commit()
        return jsonify({'liked': result['liked']})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
        
    finally:
        conn.execute('INSERT INTO user_preferences (user_id, game_id) VALUES (%s, %s)', (user_id, game_id))
        conn.commit()
        cursor.close()
        return jsonify({'message': 'Game liked successfully!'})

@app.route('/api/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    user_id=get_jwt_identity()
    liked_games=get_liked_games(user_id)
    
    recommendations = []
    for game_id in liked_games:
        for game_id in liked_games:
            recommendations.extend(recommend_games(game_id))
        
    
    recommendations=sorted(recommendations, key=lambda x: x['score'], reverse=True)
    unique_recommendations=[]
    seen=set()
    for rec in recommendations:
        if rec['id'] not in seen:
            unique_recommendations.append(rec)
            seen.add(rec['id'])
    return jsonify(unique_recommendations[:10])





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