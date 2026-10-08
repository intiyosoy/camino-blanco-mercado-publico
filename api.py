"""Official read-only API clients. Never logs requests containing a ticket."""
import os
from pathlib import Path
import httpx
from core import now, safe_id

class AccessMissing(ValueError):
    pass

def ticket():
    value = os.getenv('MERCADO_PUBLICO_TICKET')
    path = Path.home() / '.local/share/camino-blanco-mercado-publico/ticket'
    if not value and path.exists():
        if path.stat().st_mode & 0o077:
            raise AccessMissing('El archivo del ticket debe ser privado (permisos 600)')
        value = path.read_text().strip()
    if not value:
        raise AccessMissing('Falta ticket personal de ChileCompra. Solicitar en https://www.chilecompra.cl/api/')
    return value

def scrub(value):
    """Do not persist bearer URLs, tokens or transport diagnostic strings."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k.lower() not in ('ticket', 'token', 'authorization', 'cookie', 'trace')}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str) and value.startswith(('https://', 'http://')):
        from urllib.parse import urlsplit, urlunsplit
        u = urlsplit(value)
        return urlunsplit((u.scheme, u.hostname or '', u.path, '', ''))
    return value

def request(kind, params=None, code=None, client=None):
    secret = ticket()
    if kind == 'compra_agil':
        url = 'https://api2.mercadopublico.cl/v2/compra-agil' + ('/' + safe_id(code) if code else '')
        headers, query = {'ticket': secret}, params or {}
    elif kind == 'licitacion':
        url = 'https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json'
        headers, query = {}, dict(params or {}, ticket=secret)
        if code:
            query['codigo'] = safe_id(code)
    else:
        raise ValueError('Tipo no soportado')
    try:
        if client is None:
            with httpx.Client(timeout=45, follow_redirects=False) as c:
                response = c.get(url, params=query, headers=headers)
        else:
            response = client.get(url, params=query, headers=headers)
    except httpx.HTTPError:
        raise ValueError('ChileCompra no respondió; no se reemplazaron los datos guardados') from None
    if response.status_code == 429:
        raise ValueError('Cuota de ChileCompra agotada; detener consultas y respetar Retry-After')
    if response.status_code != 200:
        raise ValueError(f'ChileCompra respondió HTTP {response.status_code}; revisar acceso o código')
    try:
        data = response.json()
    except ValueError:
        raise ValueError('ChileCompra devolvió una respuesta no interpretable') from None
    if kind == 'compra_agil' and data.get('success') != 'OK':
        raise ValueError('ChileCompra rechazó la consulta; revisar ticket y parámetros')
    return {'consultado_en': now(), 'fuente': url, 'datos': scrub(data)}

def search_agile(query='', page=1, size=50, region=None):
    if not 1 <= size <= 50 or page < 1 or region is not None and not 1 <= region <= 16:
        raise ValueError('Página, tamaño o región inválidos')
    params = {'estado': 'publicada', 'numero_pagina': page, 'tamano_pagina': size, 'ordenar_por': 'FechaPublicacion'}
    if query:
        params['q'] = query
    if region is not None:
        params['region'] = region
    return request('compra_agil', params)
