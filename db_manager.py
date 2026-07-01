import os
import json
import logging
from datetime import date, timedelta

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)

PG_CONN = os.environ.get('AZURE_POSTGRESQL_CONNECTIONSTRING', os.environ.get('DATABASE_URL', ''))

TBL_INDICADORES = 'indicadores'
TBL_DETALLE = 'indicadores_detalle'
TBL_NOTICIAS = 'noticias'

class DBManager:

    @staticmethod
    def _get_conn():
        if not psycopg2:
            raise RuntimeError('psycopg2 not installed. Run: pip install psycopg2-binary')
        if not PG_CONN:
            raise RuntimeError('DATABASE_URL or AZURE_POSTGRESQL_CONNECTIONSTRING not set')
        return psycopg2.connect(PG_CONN)

    @staticmethod
    def ensure_tables():
        if not psycopg2 or not PG_CONN:
            logger.warning('PostgreSQL not configured')
            return False
        try:
            conn = DBManager._get_conn()
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {TBL_INDICADORES} (
                    id SERIAL PRIMARY KEY,
                    variable VARCHAR(50) NOT NULL,
                    valor DOUBLE PRECISION,
                    unidad VARCHAR(50),
                    fuente VARCHAR(200),
                    extra_json TEXT,
                    fecha DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {TBL_DETALLE} (
                    id SERIAL PRIMARY KEY,
                    variable VARCHAR(50) NOT NULL,
                    entidad VARCHAR(200) NOT NULL,
                    valor DOUBLE PRECISION,
                    unidad VARCHAR(20),
                    fecha DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {TBL_NOTICIAS} (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(500) NOT NULL,
                    enlace VARCHAR(1000),
                    fuente VARCHAR(100),
                    imagen VARCHAR(1000),
                    hora VARCHAR(10),
                    fecha DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            conn.commit()
            conn.close()
            logger.info('PostgreSQL tables ensured')
            return True
        except Exception as e:
            logger.error(f'Error creating tables: {e}')
            return False

    @staticmethod
    def save_data(variable, value, extra=None):
        DBManager.ensure_tables()
        today_str = date.today().isoformat()
        conn = DBManager._get_conn()
        cursor = conn.cursor()
        try:
            if variable in ('cdts', 'tco', 'ibr') and isinstance(value, dict):
                for key, val in value.items():
                    if isinstance(val, dict):
                        if 'cotizaciones' in val:
                            for bank, rate in val['cotizaciones'].items():
                                cursor.execute(
                                    f'INSERT INTO {TBL_DETALLE} (variable, entidad, valor, unidad, fecha) VALUES (%s, %s, %s, %s, %s)',
                                    (f'{variable} - {key}', bank, rate, '%', today_str)
                                )
                        else:
                            for subkey, subval in val.items():
                                cursor.execute(
                                    f'INSERT INTO {TBL_DETALLE} (variable, entidad, valor, unidad, fecha) VALUES (%s, %s, %s, %s, %s)',
                                    (variable, f'{key} - {subkey}', subval if not isinstance(subval, (int, float)) else subval, '%', today_str)
                                )
                    else:
                        cursor.execute(
                            f'INSERT INTO {TBL_DETALLE} (variable, entidad, valor, unidad, fecha) VALUES (%s, %s, %s, %s, %s)',
                            (variable, key, val if not isinstance(val, (int, float)) else val,
                             '% EA' if variable == 'cdts' else '%', today_str)
                        )
            else:
                extra_json = None
                if extra and isinstance(extra, dict):
                    extra_copy = {k: v for k, v in extra.items() if k not in ('valor', 'unidad', 'fuente')}
                    if extra_copy:
                        extra_json = json.dumps(extra_copy, ensure_ascii=False)
                cursor.execute(
                    f'INSERT INTO {TBL_INDICADORES} (variable, valor, unidad, fuente, extra_json, fecha) VALUES (%s, %s, %s, %s, %s, %s)',
                    (variable, value,
                     (extra or {}).get('unidad', '') if extra else '',
                     (extra or {}).get('fuente', '') if extra else '',
                     extra_json, today_str)
                )
            conn.commit()
            logger.info(f'Saved {variable} to PostgreSQL')
        except Exception as e:
            logger.error(f'Error saving {variable}: {e}')
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def save_news(news_list):
        if not news_list:
            return
        DBManager.ensure_tables()
        today_str = date.today().isoformat()
        conn = DBManager._get_conn()
        cursor = conn.cursor()
        try:
            for item in news_list:
                cursor.execute(
                    f'INSERT INTO {TBL_NOTICIAS} (titulo, enlace, fuente, imagen, hora, fecha) '
                    f'SELECT %s, %s, %s, %s, %s, %s '
                    f'WHERE NOT EXISTS (SELECT 1 FROM {TBL_NOTICIAS} WHERE titulo = %s AND fecha = %s)',
                    (item.get('titulo', ''), item.get('enlace', ''),
                     item.get('fuente', ''), item.get('imagen', ''),
                     item.get('hora', ''), today_str,
                     item.get('titulo', ''), today_str)
                )
            conn.commit()
            DBManager.purge_old_data()
            logger.info(f'Saved {len(news_list)} news to PostgreSQL')
        except Exception as e:
            logger.error(f'Error saving news: {e}')
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_news_history(limit=None, fuente=None, fecha=None):
        DBManager.ensure_tables()
        conn = DBManager._get_conn()
        cursor = conn.cursor()
        try:
            cutoff = (date.today() - timedelta(days=7)).isoformat()
            params = [cutoff]
            sql = f'SELECT fecha, titulo, enlace, fuente, imagen, hora FROM {TBL_NOTICIAS} WHERE fecha >= %s'
            if fuente:
                sql += ' AND fuente = %s'
                params.append(fuente)
            if fecha:
                sql += ' AND fecha = %s'
                params.append(fecha)
            sql += ' ORDER BY created_at DESC'
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            items = []
            for r in rows:
                items.append({
                    'fecha': str(r[0]) if r[0] else '',
                    'titulo': str(r[1]) if r[1] else '',
                    'enlace': str(r[2]) if r[2] else '',
                    'fuente': str(r[3]) if r[3] else '',
                    'imagen': str(r[4]) if r[4] else '',
                    'hora': str(r[5]) if r[5] else '',
                })
            if limit:
                items = items[:limit]
            return items
        except Exception as e:
            logger.error(f'Error getting news history: {e}')
            return []
        finally:
            conn.close()

    @staticmethod
    def end_of_day_cleanup():
        DBManager.ensure_tables()
        today_str = date.today().isoformat()
        conn = DBManager._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(f'''
                DELETE FROM {TBL_INDICADORES}
                WHERE fecha = %s AND id NOT IN (
                    SELECT MAX(id) FROM {TBL_INDICADORES}
                    WHERE fecha = %s GROUP BY variable
                )
            ''', (today_str, today_str))
            conn.commit()
            DBManager.purge_old_data()
            logger.info('End-of-day cleanup complete')
        except Exception as e:
            logger.error(f'Cleanup error: {e}')
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def purge_old_data():
        DBManager.ensure_tables()
        conn = DBManager._get_conn()
        cursor = conn.cursor()
        try:
            indicadores_cutoff = (date.today() - timedelta(days=90)).isoformat()
            noticias_cutoff = (date.today() - timedelta(days=7)).isoformat()
            cursor.execute(f'DELETE FROM {TBL_INDICADORES} WHERE fecha < %s', (indicadores_cutoff,))
            cursor.execute(f'DELETE FROM {TBL_DETALLE} WHERE fecha < %s', (indicadores_cutoff,))
            cursor.execute(f'DELETE FROM {TBL_NOTICIAS} WHERE fecha < %s', (noticias_cutoff,))
            conn.commit()
            logger.info('Purge old data complete')
        except Exception as e:
            logger.error(f'Purge error: {e}')
            conn.rollback()
        finally:
            conn.close()
