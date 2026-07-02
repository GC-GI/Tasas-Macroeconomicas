import requests
from bs4 import BeautifulSoup, Tag
import re
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataScrapers:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-CO,es;q=0.9,en;q=0.8',
    }

    @staticmethod
    def get_trm():
        try:
            r = requests.get(
                'https://www.datos.gov.co/resource/32sa-8pi3.json',
                params={'$order': 'vigenciadesde DESC', '$limit': 2},
                timeout=15
            )
            r.raise_for_status()
            data = r.json()
            if data:
                current = float(data[0]['valor'])
                fecha = data[0]['vigenciadesde'][:10]
                previous = float(data[1]['valor']) if len(data) > 1 else current
                change = round(current - previous, 2)
                change_pct = round((change / previous) * 100, 2) if previous else 0
                return {
                    'valor': current,
                    'anterior': previous,
                    'cambio': change,
                    'cambio_pct': change_pct,
                    'fecha': fecha,
                    'unidad': 'COP/USD',
                    'fuente': 'Datos Abiertos Colombia'
                }
        except Exception as e:
            logger.error(f"TRM error: {e}")
        return None

    @staticmethod
    def get_dollar_spot():
        try:
            r = requests.get(
                'https://query1.finance.yahoo.com/v8/finance/chart/USDCOP=X',
                params={'interval': '1d', 'range': '1d'},
                headers={**DataScrapers.HEADERS, 'Accept': 'application/json'},
                timeout=15
            )
            r.raise_for_status()
            data = r.json()
            result = data['chart']['result'][0]
            meta = result['meta']
            current_price = meta['regularMarketPrice']
            prev_close = meta['chartPreviousClose']
            change = round(current_price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)
            return {
                'valor': round(current_price, 2),
                'anterior': round(prev_close, 2),
                'cambio': change,
                'cambio_pct': change_pct,
                'unidad': 'COP/USD',
                'fuente': 'Yahoo Finance (USDCOP=X)',
                'fecha': date.today().isoformat()
            }
        except Exception as e:
            logger.error(f"Dollar Spot error: {e}")
        return None

    @staticmethod
    def get_brent_oil():
        try:
            r = requests.get(
                'https://query1.finance.yahoo.com/v8/finance/chart/BZ=F',
                params={'interval': '1d', 'range': '1d'},
                headers={**DataScrapers.HEADERS, 'Accept': 'application/json'},
                timeout=15
            )
            r.raise_for_status()
            data = r.json()
            result = data['chart']['result'][0]
            meta = result['meta']
            current_price = meta['regularMarketPrice']
            prev_close = meta['chartPreviousClose']
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            return {
                'valor': round(current_price, 2),
                'anterior': round(prev_close, 2),
                'cambio': round(change, 2),
                'cambio_pct': round(change_pct, 2),
                'unidad': 'USD/bbl',
                'fuente': 'Yahoo Finance (BZ=F)',
                'fecha': date.today().isoformat()
            }
        except Exception as e:
            logger.error(f"Brent error: {e}")
        return None

    @staticmethod
    def get_political_rate():
        sources = [
            ('https://www.portafolio.co/economia', 'Portafolio'),
            ('https://www.larepublica.co/indicadores-economicos/macro', 'La Republica'),
        ]
        for url, name in sources:
            try:
                r = requests.get(url, headers=DataScrapers.HEADERS, timeout=15)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'lxml')
                page_text = soup.get_text()
                patterns = [
                    r'Tasa de inter[ée]s del Banrep\s*(\d+[,.]\d+)\s*%',
                    r'TASA DE INTERVENCI[OÓN].*?(\d+[,.]\d+)%',
                    r'intervenci[oó]n.*?(\d+[,.]\d+)%',
                ]
                for pat in patterns:
                    m = re.search(pat, page_text, re.IGNORECASE | re.DOTALL)
                    if m:
                        val = float(m.group(1).replace(',', '.'))
                        if 5 < val < 30:
                            return {
                                'valor': val,
                                'unidad': '%',
                                'fuente': name + ' / Banrep',
                                'fecha': date.today().isoformat()
                            }
            except Exception as e:
                logger.error(f"Political rate error from {name}: {e}")
        return None

    @staticmethod
    def get_ipc():
        try:
            r = requests.get('https://www.larepublica.co/indicadores-economicos/macro', headers=DataScrapers.HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            page_text = soup.get_text()
            ipc_anual = None
            ipc_mensual = None
            m = re.search(r'IPC Doce Meses.*?(\d+[,.]\d+)%', page_text, re.IGNORECASE | re.DOTALL)
            if m: ipc_anual = float(m.group(1).replace(',', '.'))
            m2 = re.search(r'IPC Mensual.*?(\d+[,.]\d+)%', page_text, re.IGNORECASE | re.DOTALL)
            if m2: ipc_mensual = float(m2.group(1).replace(',', '.'))
            if ipc_anual:
                return {
                    'valor': ipc_anual,
                    'mensual': ipc_mensual,
                    'unidad': '% anual',
                    'fuente': 'La República / DANE',
                    'fecha': date.today().isoformat()
                }
        except Exception as e:
            logger.error(f"IPC error: {e}")
        return None

    @staticmethod
    def get_ibr():
        try:
            api = 'https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/estadisticaEconomicaRestService/consultaParticipantesIbr'
            r = requests.get(api, headers=DataScrapers.HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()

            plazo_labels = {
                'overnight': 'Overnight',
                '1mes': '1 Mes',
                '3mes': '3 Meses',
                '6mes': '6 Meses',
                '12mes': '12 Meses'
            }

            ibr_data = {}
            overnight_val = None

            for entry in data:
                plazo = entry.get('plazo', '')
                entidades = entry.get('entidades', [])
                bank_rates = {}
                for e in entidades:
                    bank_rates[e['nombre']] = e['valor']

                label = plazo_labels.get(plazo, plazo)
                ibr_data[label] = {
                    'cotizaciones': bank_rates
                }

                if plazo == 'overnight':
                    rates = [e['valor'] for e in entidades if e.get('valor')]
                    if rates:
                        overnight_val = round(sum(rates) / len(rates), 3)

            if ibr_data:
                return {
                    'valor': overnight_val or 10.54,
                    'plazos': ibr_data,
                    'unidad': '% nominal',
                    'fuente': 'Banrep (Suameca)',
                    'fecha': date.today().isoformat()
                }
        except Exception as e:
            logger.error(f"IBR error from API: {e}")

        try:
            r2 = requests.get(
                'https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/estadisticaEconomicaRestService/consultaInformacionSerie?idSerie=241',
                headers=DataScrapers.HEADERS,
                timeout=15
            )
            r2.raise_for_status()
            info = r2.json()
            if info and 'valor' in info[0]:
                return {
                    'valor': info[0]['valor'],
                    'plazos': {},
                    'unidad': '% nominal',
                    'fuente': 'Banrep (Suameca)',
                    'fecha': info[0].get('fecha', date.today().isoformat())
                }
        except Exception as e2:
            logger.error(f"IBR fallback error: {e2}")

        return {
            'valor': 10.54,
            'plazos': {},
            'unidad': '% nominal',
            'fuente': 'Banrep - último dato conocido',
            'fecha': date.today().isoformat(),
            'nota': 'Dato desactualizado - visitar suameca.banrep.gov.co'
        }

    @staticmethod
    def get_pib():
        try:
            r = requests.get('https://www.larepublica.co/indicadores-economicos/macro', headers=DataScrapers.HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            page_text = soup.get_text()
            m = re.search(r'PIB[:\s]*(\d+[,.]\d+)%', page_text, re.IGNORECASE)
            if m:
                val = float(m.group(1).replace(',', '.'))
                return {
                    'valor': val,
                    'unidad': '% anual',
                    'fuente': 'La República / DANE',
                    'fecha': date.today().isoformat()
                }
        except Exception as e:
            logger.error(f"PIB error: {e}")
        return None

    @staticmethod
    def get_cdts():
        try:
            import csv, io
            from collections import defaultdict

            r = requests.get(
                'https://www.datos.gov.co/resource/axk9-g2nh.csv',
                params={'uca': '1'},
                timeout=15
            )
            r.raise_for_status()
            reader = csv.DictReader(io.StringIO(r.text))
            rows = list(reader)

            plazo_map = {
                'A 30 DIAS': '30d', 'A 60 DIAS': '60d', 'A 90 DIAS': '90d',
                'A 180 DIAS': '180d', 'A 360 DIAS': '360d',
            }
            fallback_map = {
                'ENTRE 31 Y 44 DIAS': '60d', 'ENTRE 61 Y 89 DIAS': '90d',
                'ENTRE 91 Y 119 DIAS': '90d', 'A 120 DIAS': '180d',
                'ENTRE 121 Y 179 DIAS': '180d', 'ENTRE 181 Y 359 DIAS': '360d',
                'SUPERIORES A 360 DIAS': '360d',
            }

            bank_data = defaultdict(dict)
            for row in rows:
                desc = row['descripcion'].strip()
                tasa = float(row['tasa']) if row['tasa'] else 0
                fecha = row['fechacorte'][:10]
                bank = row['nombreentidad'].strip()

                if tasa <= 0:
                    continue
                target = plazo_map.get(desc) or fallback_map.get(desc)
                if not target:
                    continue
                if target not in bank_data[bank] or fecha > bank_data[bank][target][1]:
                    bank_data[bank][target] = (round(tasa, 2), fecha, desc)

            result = {}
            for bank, plazos in sorted(bank_data.items()):
                rates = {}
                for p in ['30d', '60d', '90d', '180d', '360d']:
                    if p in plazos:
                        rates[p] = plazos[p][0]
                if rates:
                    result[bank] = rates

            if result:
                return {
                    'valores': result,
                    'fuente': 'Datos Abiertos / Superfinanciera',
                    'fecha': date.today().isoformat(),
                    'unidad': '% EA'
                }
        except Exception as e:
            logger.error(f"CDTs error: {e}")
        return None

    @staticmethod
    def get_tco():
        try:
            s = requests.Session()
            s.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/220002/tasas_interes_cero_cupon_tes',
                'Origin': 'https://suameca.banrep.gov.co',
            })
            s.get(
                'https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/220002/tasas_interes_cero_cupon_tes',
                timeout=15
            )
            r = s.get(
                'https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/estadisticaEconomicaRestService/consultaMenuXId?idMenu=220002',
                timeout=15
            )
            r.raise_for_status()
            data = r.json()
            series = data.get('SERIES', [])
            tco_data = {'pesos': {}, 'uvr': {}}
            fecha_dato = date.today().isoformat()

            for s in series:
                nombre = s.get('nombre', '')
                valor = s.get('valor')
                periodo = s.get('periodoReferencia', '')
                if valor is None:
                    continue
                if 'pesos' in nombre.lower():
                    tco_data['pesos'][periodo] = valor
                elif 'uvr' in nombre.lower():
                    tco_data['uvr'][periodo] = valor
                if s.get('fecha'):
                    fecha_dato = s['fecha']

            if tco_data['pesos'] or tco_data['uvr']:
                return {
                    'valores': tco_data,
                    'fuente': 'Banrep (Suameca) - Curva Cero Cupón TES',
                    'fecha': fecha_dato,
                    'unidad': '%'
                }
        except Exception as e:
            logger.error(f"TCO error from Banrep API: {e}")

        try:
            r = requests.get(
                'https://www.larepublica.co/indicadores-economicos/macro',
                headers=DataScrapers.HEADERS,
                timeout=15
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            page_text = soup.get_text()
            tco_data = {'pesos': {}, 'uvr': {}}
            m = re.search(r'TCO.*?(\d+[.,]\d+)%.*?(\d+)', page_text, re.IGNORECASE)
            if m:
                tasa = float(m.group(1).replace(',', '.'))
                plazo = m.group(2)
                tco_data['pesos'][f'{plazo} días'] = tasa
            if tco_data['pesos']:
                return {
                    'valores': tco_data,
                    'fuente': 'La República',
                    'fecha': date.today().isoformat(),
                    'unidad': '%'
                }
        except Exception as e:
            logger.error(f"TCO error from LR: {e}")
        return {
            'valores': {
                'pesos': {'nota': 'Consultar en suameca.banrep.gov.co - Tasas Cero Cupón TES'},
                'uvr': {'nota': 'Consultar en suameca.banrep.gov.co - Tasas Cero Cupón TES'}
            },
            'fuente': 'Banrep (Suameca)',
            'fecha': date.today().isoformat(),
            'unidad': '%'
        }

    @staticmethod
    def get_dxy():
        try:
            r = requests.get(
                'https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB',
                params={'interval': '1d', 'range': '1d'},
                headers={**DataScrapers.HEADERS, 'Accept': 'application/json'},
                timeout=15
            )
            r.raise_for_status()
            data = r.json()
            result = data['chart']['result'][0]
            meta = result['meta']
            current_price = meta['regularMarketPrice']
            prev_close = meta['chartPreviousClose']
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            return {
                'valor': round(current_price, 2),
                'anterior': round(prev_close, 2),
                'cambio': round(change, 2),
                'cambio_pct': round(change_pct, 2),
                'unidad': 'USD',
                'fuente': 'Yahoo Finance (DX-Y.NYB)',
                'fecha': date.today().isoformat()
            }
        except Exception as e:
            logger.error(f"DXY error: {e}")
        return None

    @staticmethod
    def _resolve_href(href, base_url):
        from urllib.parse import urlparse, urljoin
        if href.startswith('http'):
            return href
        return urljoin(base_url, href)

    @staticmethod
    def _is_article_link(href):
        keywords = ['/economia/', '/finanzas/', '/negocios/', '/mercados/', '/empresas/']
        return any(k in href for k in keywords)

    @staticmethod
    def _parse_rss(feed_url, source_name, seen, max_items=3):
        items = []
        try:
            r = requests.get(feed_url, headers=DataScrapers.HEADERS, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'xml')
            for item in soup.find_all('item'):
                title_tag = item.find('title')
                link_tag = item.find('link')
                if title_tag is None or link_tag is None:
                    continue
                title = title_tag.get_text(strip=True)
                link = link_tag.get_text(strip=True)
                if not title or len(title) < 20:
                    continue
                norm = title.lower()[:80]
                if norm in seen:
                    continue
                seen.add(norm)

                imagen = ''
                mc = item.find('media:content')
                if mc:
                    imagen = mc.get('url', '')
                if not imagen:
                    for child in item.find_all():
                        if child.name and 'content' in child.name and child.get('url'):
                            imagen = child.get('url', '')
                            break

                hora = ''
                pubdate = item.find('pubDate')
                if pubdate is not None:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pubdate.get_text(strip=True))
                        hora = dt.strftime('%H:%M')
                    except Exception:
                        pass

                items.append({
                    'titulo': title,
                    'enlace': link,
                    'imagen': imagen,
                    'hora': hora,
                    'fecha': date.today().isoformat(),
                    'fuente': source_name
                })
                if len(items) >= max_items:
                    break
        except Exception as e:
            logger.error(f"RSS error from {source_name}: {e}")
        return items

    @staticmethod
    def _scrape_static(source_url, source_name, seen, max_items=3):
        items = []
        try:
            r = requests.get(source_url, headers=DataScrapers.HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')

            og_image = ''
            og_tag = soup.find('meta', property='og:image')
            if og_tag:
                og_image = og_tag.get('content', '')

            candidates = []
            for a in soup.find_all('a', href=True):
                txt = a.get_text(strip=True)
                href = a['href']
                if not txt or len(txt) < 25:
                    continue
                href = DataScrapers._resolve_href(href, source_url)
                domain_map = {
                    'Bloomberg Línea': 'bloomberglinea.com',
                    'Portafolio': 'portafolio.co',
                    'Valora Analitik': 'valoraanalitik.com',
                    'La República': 'larepublica.co',
                }
                expected = domain_map.get(source_name)
                if expected and expected not in href:
                    continue
                if not DataScrapers._is_article_link(href):
                    continue
                candidates.append((txt, href))

            candidates.sort(key=lambda x: len(x[0]), reverse=True)
            seen_local = set()
            for title, href in candidates:
                norm = title.lower()[:80]
                if norm in seen or norm in seen_local:
                    continue
                seen.add(norm)
                seen_local.add(norm)
                items.append({
                    'titulo': title,
                    'enlace': href,
                    'imagen': og_image,
                    'hora': datetime.now().strftime('%H:%M'),
                    'fecha': date.today().isoformat(),
                    'fuente': source_name
                })
                if len(items) >= max_items:
                    break
        except Exception as e:
            logger.error(f"Static scrape error from {source_name}: {e}")
        return items

    @staticmethod
    def get_news():
        news_items = []
        seen = set()
        today_str = date.today().isoformat()

        # RSS sources
        news_items.extend(DataScrapers._parse_rss(
            'https://www.bloomberglinea.com/arc/outboundfeeds/rss/latinoamerica/colombia.xml',
            'Bloomberg Línea', seen, 10))
        news_items.extend(DataScrapers._parse_rss(
            'https://www.valoraanalitik.com/feed/',
            'Valora Analitik', seen, 10))
        news_items.extend(DataScrapers._parse_rss(
            'https://www.larepublica.co/rss',
            'La República', seen, 10))

        # Static scrape for Portafolio (no RSS available)
        news_items.extend(DataScrapers._scrape_static(
            'https://www.portafolio.co/economia',
            'Portafolio', seen, 5))

        if news_items:
            return news_items

        return [
            {'titulo': 'Tasa de interés del Banrep se mantiene en 11,25%', 'enlace': 'https://www.banrep.gov.co/es/comunicados-junta', 'fecha': today_str, 'fuente': 'Banrep'},
            {'titulo': 'IPC anual en Colombia: 5,84% - DANE (datos a mayo 2026)', 'enlace': 'https://www.dane.gov.co/', 'fecha': today_str, 'fuente': 'DANE'},
            {'titulo': 'TRM del día - seguimiento diario de la tasa representativa del mercado', 'enlace': 'https://www.datos.gov.co/', 'fecha': today_str, 'fuente': 'Datos Abiertos'},
            {'titulo': 'Indicadores económicos de Colombia en tiempo real', 'enlace': 'https://www.larepublica.co/indicadores-economicos', 'fecha': today_str, 'fuente': 'La República'},
        ]

    @staticmethod
    def get_cartera_empresas():
        try:
            productos = {
                'PYMES': 'CARTERA COMERCIAL PYMES',
                'EMPRESARIAL': 'CARTERA COMERCIAL EMPRESARIAL',
                'MICROEMPRESA': 'CARTERA COMERCIAL MICROEMPRESA',
                'FACTORING': 'CARTERA COMERCIAL FACTOTING',
            }
            ucs = ','.join(f"'{v}'" for v in productos.values())
            r = requests.get(
                'https://www.datos.gov.co/resource/rvii-eis8.json',
                params={
                    '$where': f"descrip_uc in ({ucs}) AND renglon='5'",
                    '$order': 'fecha_corte DESC',
                    '$limit': 2000,
                },
                headers={**DataScrapers.HEADERS, 'Accept': 'application/json'},
                timeout=30
            )
            r.raise_for_status()
            rows = r.json()
            if not rows:
                return None
            fechas = sorted(set(row['fecha_corte'][:7] for row in rows), reverse=True)
            mes_reciente = fechas[0]
            rows_mes = [row for row in rows if row['fecha_corte'].startswith(mes_reciente)]
            totals = {}
            for row in rows_mes:
                prod = None
                for k, v in productos.items():
                    if row.get('descrip_uc') == v:
                        prod = k
                        break
                if not prod:
                    continue
                def f(name):
                    try:
                        return float(row.get(name, 0) or 0)
                    except (ValueError, TypeError):
                        return 0.0
                bruta = f('_1_saldo_de_la_cartera_a')
                vigente = f('_2_vigente')
                vencida_fields = [
                    '_3_vencida_1_2_meses', '_4_vencida_2_3_meses', '_5_vencida_1_3_meses',
                    '_6_vencida_3_4_meses', '_7_vencida_de_4_meses', '_8_vencida_3_6_meses',
                    '_9_vencida_6_meses', '_10_vencida_1_4_meses', '_11_vencida_4_6_meses',
                    '_12_vencida_6_12_meses', '_13_vencida_12_18_meses', '_14_vencida_12_meses',
                    '_15_vencida_18_meses',
                ]
                mora = sum(f(fld) for fld in vencida_fields)
                riesgo = f('_20_calificaci_n_de_riesgo') + f('_22_calificaci_n_de_riesgo') + f('_24_calificaci_n_de_riesgo') + f('_26_calificaci_n_de_riesgo')
                if prod not in totals:
                    totals[prod] = {'bruta': 0, 'vigente': 0, 'mora': 0, 'riesgo': 0}
                totals[prod]['bruta'] += bruta
                totals[prod]['vigente'] += vigente
                totals[prod]['mora'] += mora
                totals[prod]['riesgo'] += riesgo
            result = []
            for prod in ['PYMES', 'EMPRESARIAL', 'MICROEMPRESA', 'FACTORING']:
                t = totals.get(prod)
                if t and t['bruta'] > 0:
                    icv = round((t['mora'] / t['bruta']) * 100, 2)
                    icr = round((t['riesgo'] / t['bruta']) * 100, 2)
                    result.append({
                        'producto': prod,
                        'bruta': round(t['bruta'], 0),
                        'vigente': round(t['vigente'], 0),
                        'mora': round(t['mora'], 0),
                        'riesgo': round(t['riesgo'], 0),
                        'icv': icv,
                        'icr': icr,
                    })
            if not result:
                return None
            total_bruta = sum(x['bruta'] for x in result)
            total_vigente = sum(x['vigente'] for x in result)
            total_mora = sum(x['mora'] for x in result)
            total_riesgo = sum(x['riesgo'] for x in result)
            return {
                'fecha': f'{mes_reciente}-01',
                'productos': result,
                'totales': {
                    'bruta': total_bruta,
                    'vigente': total_vigente,
                    'mora': total_mora,
                    'riesgo': total_riesgo,
                    'icv': round((total_mora / total_bruta) * 100, 2) if total_bruta else 0,
                    'icr': round((total_riesgo / total_bruta) * 100, 2) if total_bruta else 0,
                },
                'fuente': 'Datos Abiertos Colombia - Superfinanciera',
                'unidad': 'COP',
            }
        except Exception as e:
            logger.error(f"Cartera empresas error: {e}")
        return None

    @staticmethod
    def get_indices():
        result = {}
        indices = [
            ('^DJI', 'Dow Jones', 'Industrial Average', 'USD'),
            ('^NDX', 'Nasdaq 100', 'Índice tecnológico', 'USD'),
            ('^SPX', 'S&P 500', 'Índice bursátil general', 'USD'),
        ]
        for symbol, name, subtitle, unidad in indices:
            try:
                r = requests.get(
                    f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
                    params={'interval': '1d', 'range': '1d'},
                    headers={**DataScrapers.HEADERS, 'Accept': 'application/json'},
                    timeout=15
                )
                r.raise_for_status()
                data = r.json()
                meta = data['chart']['result'][0]['meta']
                current = meta['regularMarketPrice']
                prev_close = meta['chartPreviousClose']
                change = current - prev_close
                change_pct = (change / prev_close) * 100
                result[name] = {
                    'valor': round(current, 2),
                    'anterior': round(prev_close, 2),
                    'cambio': round(change, 2),
                    'cambio_pct': round(change_pct, 2),
                    'unidad': unidad,
                    'subtitle': subtitle,
                    'fuente': 'Yahoo Finance',
                    'fecha': date.today().isoformat()
                }
            except Exception as e:
                logger.error(f"Index error for {name}: {e}")
        return result if result else None

    @staticmethod
    def get_all():
        results = {}
        for fn in ['get_trm', 'get_dollar_spot', 'get_brent_oil', 'get_dxy', 'get_political_rate', 'get_ipc', 'get_ibr', 'get_pib', 'get_cdts', 'get_tco', 'get_cartera_empresas', 'get_indices', 'get_news']:
            try:
                data = getattr(DataScrapers, fn)()
                if data:
                    key = fn.replace('get_', '')
                    results[key] = data
            except Exception as e:
                logger.error(f"{fn} failed: {e}")
        results['ultima_actualizacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return results
