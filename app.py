from flask import Flask, jsonify, render_template, request
from scrapers import DataScrapers
from db_manager import DBManager
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import atexit
import logging
import json
import os
import traceback

COL_TZ = ZoneInfo('America/Bogota')
class ColombiaFormatter(logging.Formatter):
    def converter(self, timestamp):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(COL_TZ)
    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        return dt.strftime(datefmt or '%Y-%m-%d %H:%M:%S')

handler = logging.StreamHandler()
handler.setFormatter(ColombiaFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
logging.getLogger('apscheduler').setLevel(logging.WARNING)

app = Flask(__name__)
cached_data = None

DBManager.ensure_tables()

def save_all_data(data):
    for key in ['trm', 'dollar_spot', 'brent_oil', 'dxy', 'political_rate', 'ipc', 'pib']:
        if key in data:
            val = data[key].get('valor') if isinstance(data[key], dict) else None
            DBManager.save_data(key, val, data[key])
    if 'indices' in data and data['indices']:
        for idx_name, idx_val in data['indices'].items():
            DBManager.save_data(idx_name, idx_val.get('valor'), idx_val)
    if 'news' in data and data['news']:
        DBManager.save_news(data['news'])
    for key in ['ibr', 'cdts', 'tco']:
        if key in data:
            item = data[key]
            if 'valor' in item and isinstance(item['valor'], (int, float)):
                DBManager.save_data(key, item['valor'], item)
            nested = item.get('valores') or item.get('plazos')
            if nested:
                DBManager.save_data(key, nested)

def update_all_data():
    global cached_data
    logger.info('Starting daily data update...')
    try:
        data = DataScrapers.get_all()
        cached_data = data
        save_all_data(data)
        logger.info('Daily data update complete')
    except Exception:
        logger.error(f'Update failed:\n{traceback.format_exc()}')
    return cached_data

# --- Scheduler (daily 00:00 scrape, 23:55 cleanup) ---
# Guard: only start scheduler in the main process (not gunicorn workers).
# gunicorn sets GUNICORN_WORKER_ID; we skip scheduler inside workers.
if not os.environ.get('GUNICORN_WORKER_ID') and os.environ.get('WEBAPP_CONTAINER') != 'gunicorn_worker':
    def end_of_day_cleanup():
        logger.info('Running end-of-day cleanup...')
        try:
            DBManager.end_of_day_cleanup()
        except Exception:
            logger.error(f'Cleanup failed:\n{traceback.format_exc()}')

    scheduler = BackgroundScheduler(timezone='America/Bogota')
    scheduler.add_job(func=update_all_data, trigger='cron', hour=0, minute=0, id='daily_update',
                      replace_existing=True)
    scheduler.add_job(func=end_of_day_cleanup, trigger='cron', hour=23, minute=55, id='daily_cleanup',
                      replace_existing=True)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    logger.info('Scheduler started (America/Bogota, daily 00:00 / 23:55)')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/datos')
def api_datos():
    global cached_data
    data = cached_data if cached_data else update_all_data()
    return app.response_class(
        response=json.dumps(data, ensure_ascii=False, indent=2, default=str),
        status=200,
        mimetype='application/json'
    )

@app.route('/api/actualizar')
def api_actualizar():
    data = update_all_data()
    return app.response_class(
        response=json.dumps({'status': 'ok', 'data': data}, ensure_ascii=False, indent=2, default=str),
        status=200,
        mimetype='application/json'
    )

@app.route('/api/historico')
def api_historico():
    return jsonify({'status': 'ok', 'message': 'Data stored in PostgreSQL. Use /api/datos for latest values.'})

@app.route('/api/noticias/historial')
def api_noticias_historial():
    limit = request.args.get('limit', type=int)
    fuente = request.args.get('fuente')
    fecha = request.args.get('fecha')
    items = DBManager.get_news_history(limit=limit, fuente=fuente, fecha=fecha)
    return app.response_class(
        response=json.dumps(items, ensure_ascii=False, indent=2, default=str),
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    logger.info('Starting initial data fetch...')
    update_all_data()
    logger.info('Server starting on http://0.0.0.0:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)
