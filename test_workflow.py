from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import zipfile
import pytest
import httpx
from core import *
from proposals import money, fill_annex
import api

def test_category_has_no_software_prefilter():
    records = [{'codigo': 'educacion', 'codigos_unspsc': ['86101700']}, {'codigo': 'consultoria', 'codigos_unspsc': ['80101500']}, {'codigo': 'software', 'codigos_unspsc': ['43230000']}]
    assert [r['codigo'] for r in category_filter(records, ['86', '80'])] == ['educacion', 'consultoria']

def test_real_excel():
    path = Path.home() / 'Downloads' / '20261008164134.xlsx'
    if not path.exists():
        pytest.skip('Excel privado no incluido en distribución')
    records = import_excel(path)
    assert len(records) == 108
    selected = next(r for r in records if r['codigo'] == '2403-844-COT26')
    assert selected['presupuesto']['monto'] == '600000'
    assert selected['cierre']['verificada'] is False
    assert selected['fuente']['fila'] >= 2
    assert review(selected, {})['decision'] == 'INVESTIGAR'

def test_chile_offset_winter_summer():
    assert date_info('2026-10-09T15:00:00Z')['conversion_chile'] == '2026-10-09T12:00:00-03:00'
    assert date_info('2026-06-09T15:00:00Z')['conversion_chile'] == '2026-06-09T11:00:00-04:00'
    assert 'conversion_chile' not in date_info('2026-10-09T15:00:00')

def evidence_dossier(tmp_path):
    p = tmp_path / 'bases.txt'
    p.write_text('No se requiere OTEC. Debe realizar taller presencial.\n' + 'Contenido completo. ' * 500)
    doc = extract_document(p)
    doc['lectura_confirmada'] = True
    ev = {'documento': 'bases', 'sha256': doc['sha256'], 'ubicacion': 'línea 1', 'cita': 'No se requiere OTEC.'}
    ts = now()
    return {'documentos': {'bases': doc}, 'inventario': {'confirmado': True, 'fuente': 'https://compra-agil.mercadopublico.cl/', 'revisado_en': ts, 'esperados': ['bases']}, 'otec': {'estado': 'NO_REQUERIDO', 'evidencia': ev}, 'requisitos_revisados': True, 'requisitos': [{'nombre': 'taller', 'cumple': True, 'excluyente': True, 'evidencia': dict(ev, cita='Debe realizar taller presencial.'), 'respaldo_proveedor': 'Plan revisado por proveedor'}], 'cierre': {'valor': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), 'fuente': 'https://compra-agil.mercadopublico.cl/', 'revisado_en': ts}, 'presupuesto': {'impuestos': 'INCLUIDOS', 'fuente': 'bases'}}

def test_missing_otec_never_eligible(tmp_path):
    d = evidence_dossier(tmp_path)
    d['otec'] = {}
    assert review({'codigo': 'TEST'}, d)['decision'] == 'INVESTIGAR'
    d['otec'] = {'estado': 'NO_REQUERIDO', 'evidencia': {'cita': 'inventado'}}
    assert review({'codigo': 'TEST'}, d)['otec'] == 'DESCONOCIDO'

def test_complete_then_missing_annex_and_changes(tmp_path):
    d = evidence_dossier(tmp_path)
    d['presupuesto'].update(monto='600000', moneda='CLP')
    assert review({'codigo': 'TEST'}, d)['decision'] == 'POSTULAR'
    assert len(d['documentos']['bases']['partes'][1]['texto']) > 2000
    d['inventario']['esperados'].append('modificacion')
    assert review({'codigo': 'TEST'}, d)['decision'] == 'INVESTIGAR'
    d['inventario']['esperados'].pop()
    Path(d['documentos']['bases']['archivo']).write_text('Cambiaron bases')
    assert review({'codigo': 'TEST'}, d)['decision'] == 'INVESTIGAR'

def test_mandatory_otec_and_closed(tmp_path):
    d = evidence_dossier(tmp_path)
    d['otec']['estado'] = 'OBLIGATORIO'
    assert review({'codigo': 'TEST'}, d)['decision'] == 'DESCARTAR'
    d['otec']['estado'] = 'NO_REQUERIDO'
    d['cierre']['valor'] = '2020-01-01T12:00:00Z'
    assert review({'codigo': 'TEST'}, d)['decision'] == 'DESCARTAR'

def test_stale_inventory(tmp_path):
    d = evidence_dossier(tmp_path)
    d['inventario']['revisado_en'] = '2020-01-01T12:00:00+00:00'
    assert review({'codigo': 'TEST'}, d)['decision'] == 'INVESTIGAR'

def test_money_explicit_taxes_and_budget():
    items = [{'cantidad': 2, 'precio_unitario_neto': '100000'}]
    with pytest.raises(ValueError):
        money(items, None, 'CLP')
    assert money(items, 19, 'CLP', '230000', 'INCLUIDOS')['dentro_presupuesto'] is False
    assert money(items, 19, 'CLP')['total'] == '238000'
    assert money(items, 0, 'CLP')['total'] == '200000'
    assert money(items, 19, 'CLP', '300000', None)['dentro_presupuesto'] is None
    with pytest.raises(ValueError):
        money([{'cantidad': 1, 'precio_unitario_neto': 'NaN'}], 19, 'CLP')

def test_api_headers_errors_and_scrub(monkeypatch):
    monkeypatch.setenv('MERCADO_PUBLICO_TICKET', 'secret-test')
    def handler(req):
        assert req.headers['ticket'] == 'secret-test'
        assert 'secret-test' not in str(req.url)
        return httpx.Response(200, json={'success': 'OK', 'payload': {'items': [], 'url': 'https://example.com/doc?token=secret'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        result = api.request('compra_agil', client=c)
    assert result['datos']['payload']['url'] == 'https://example.com/doc'
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(429))) as c:
        with pytest.raises(ValueError, match='Cuota'):
            api.request('compra_agil', client=c)

def test_atomic_private_persistence_and_invalidation(tmp_path):
    w = Workspace(tmp_path)
    w.merge([{'codigo': 'TEST', 'nombre': 'yoga'}])
    private_json(w.path('TEST'), {'cierre': {'valor': 'test'}, 'inventario': {'confirmado': True}})
    w.merge([{'codigo': 'TEST', 'nombre': 'mindfulness'}])
    assert w.dossier('TEST')['cierre'] == {}
    assert (w.root / 'oportunidades.json').stat().st_mode & 0o777 == 0o600
    assert len(list((w.root / 'historial').glob('*.json'))) == 1

def test_annex_preserves_original_and_split_runs(tmp_path):
    source, target = tmp_path / 'buyer.docx', tmp_path / 'draft.docx'
    xml = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Empresa: {{RAZ</w:t></w:r><w:r><w:t>ON}} / firma pendiente</w:t></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('word/document.xml', xml)
        z.writestr('word/styles.xml', b'keep-exactly')
    original = digest(source)
    result = fill_annex(source, target, {'{{RAZON}}': 'Ejemplo de prueba'})
    assert digest(source) == original
    with zipfile.ZipFile(target) as z:
        assert z.read('word/styles.xml') == b'keep-exactly'
        assert b'Ejemplo de prueba' in z.read('word/document.xml')
        assert b'firma pendiente' in z.read('word/document.xml')
    with pytest.raises(ValueError, match='Firmas'):
        fill_annex(source, tmp_path / 'bad.docx', {'{{FIRMA}}': 'No'})
    with pytest.raises(ValueError, match='no encontrados'):
        fill_annex(source, tmp_path / 'missing.docx', {'{{OTHER}}': 'No'})

def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        safe_id('../secret')
