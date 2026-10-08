"""Buyer-specific annex drafts, monetary checks and explicit pending signatures."""
import json
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from lxml import etree
from core import Workspace, safe_id, private_json, digest, now, review, norm

def money(items, tax_rate, currency, budget=None, budget_tax=None):
    if not currency or tax_rate is None:
        raise ValueError('Confirmar moneda y tratamiento tributario; no se presume IVA')
    try:
        rate = Decimal(str(tax_rate))
        if not rate.is_finite() or not Decimal(0) <= rate <= Decimal(100):
            raise ValueError('Tasa tributaria inválida')
        net = Decimal(0)
        if not items:
            raise ValueError('Faltan ítems')
        for item in items:
            quantity, price = Decimal(str(item['cantidad'])), Decimal(str(item['precio_unitario_neto']))
            if not quantity.is_finite() or not price.is_finite() or quantity <= 0 or price < 0:
                raise ValueError('Cantidades o precios inválidos')
            net += quantity * price
        quantum = Decimal('1') if currency == 'CLP' else Decimal('0.01')
        from decimal import ROUND_HALF_UP
        net = net.quantize(quantum, rounding=ROUND_HALF_UP)
        tax = (net * rate / 100).quantize(quantum, rounding=ROUND_HALF_UP)
        total = net + tax
        within = None
        if budget is not None and budget_tax in ('INCLUIDOS', 'EXCLUIDOS', 'EXENTO'):
            value = Decimal(str(budget))
            if not value.is_finite() or value < 0:
                raise ValueError('Presupuesto inválido')
            within = (net if budget_tax == 'EXCLUIDOS' else total) <= value
        return {'neto': str(net), 'impuestos': str(tax), 'total': str(total), 'tasa_confirmada': str(rate), 'moneda': currency, 'dentro_presupuesto': within}
    except (InvalidOperation, KeyError):
        raise ValueError('Montos/cantidades incompletos o inválidos') from None

def fill_annex(source, target, replacements):
    """Edit only exact buyer placeholders in XML, preserving all other ZIP members.
    Tokens may span Word runs. Never accepts declarations or signature fields.
    """
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Conservar el anexo original')
    if not replacements:
        raise ValueError('Faltan campos específicos del anexo')
    forbidden = ('firma', 'declar', 'probidad', 'conflicto', 'integridad', 'acepto', 'jurament')
    for key, value in replacements.items():
        if not key or any(k in norm(key) for k in forbidden) or not isinstance(value, str):
            raise ValueError('Firmas y declaraciones requieren revisión humana y no se completan automáticamente')
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    found = {k: 0 for k in replacements}
    contents = []
    with zipfile.ZipFile(source) as original:
        if sum(i.file_size for i in original.infolist()) > 50_000_000:
            raise ValueError('Anexo demasiado grande')
        for info in original.infolist():
            data = original.read(info.filename)
            if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml', info.filename):
                tree = etree.fromstring(data, parser)
                for paragraph in tree.xpath('//w:p', namespaces=ns):
                    nodes = paragraph.xpath('.//w:t', namespaces=ns)
                    text = ''.join(n.text or '' for n in nodes)
                    matches = []
                    for token, value in replacements.items():
                        for match in re.finditer(re.escape(token), text):
                            matches.append((match.start(), match.end(), token, value))
                    ordered = sorted(matches)
                    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
                        raise ValueError('Campos superpuestos')
                    for start, end, token, value in sorted(matches, reverse=True):
                        offset = 0
                        spans = []
                        for node in nodes:
                            length = len(node.text or '')
                            spans.append((node, offset, offset + length))
                            offset += length
                        touched = [(n, a, b) for n, a, b in spans if a < end and b > start]
                        for i, (node, a, b) in enumerate(touched):
                            old = node.text or ''
                            node.text = old[:max(0, start-a)] + (value if i == 0 else '') + old[min(len(old), end-a):]
                            node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                        found[token] += 1
                data = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
            contents.append((info, data))
    missing = [k for k, v in found.items() if not v]
    if missing:
        raise ValueError('Campos no encontrados en anexo original: ' + ', '.join(missing))
    with zipfile.ZipFile(target, 'x') as output:
        for info, data in contents:
            output.writestr(info, data)
    Path(target).chmod(0o600)
    return {'archivo': str(target), 'original_sha256': digest(source), 'resultado_sha256': digest(target), 'campos': found, 'estado': 'BORRADOR: revisar visualmente y firmar solo si corresponde'}

def prepare(code, sections, items, currency, tax_rate, tax_source, deadline, annex_names):
    if not tax_source or not deadline:
        raise ValueError('Confirmar fuente tributaria y plazo de ejecución')
    w = Workspace()
    d = w.dossier(code)
    r = next((r for r in w.records() if r['codigo'] == code), {'codigo': code})
    evaluation = review(r, d)
    budget = d.get('presupuesto', {})
    amounts = money(items, tax_rate, currency, budget.get('monto') if budget.get('moneda') == currency else None, budget.get('impuestos'))
    pending = list(evaluation['pendientes']) + list(evaluation['exclusiones'])
    pending += ['Revisar propuesta y anexos visualmente', 'Confirmar firmas/declaraciones personalmente', 'Revalidar cambios y cierre en portal antes de enviar']
    if amounts['dentro_presupuesto'] is not True:
        pending.append('Monto fuera de presupuesto o comparación no confirmada')
    if not annex_names:
        pending.append('Identificar anexos específicos exigidos por el comprador')
    for name in annex_names:
        if name not in d.get('documentos', {}):
            pending.append('Falta anexo original: ' + name)
    directory = w.root / 'propuestas' / safe_id(code) / now().replace(':', '-')
    directory.mkdir(parents=True, mode=0o700)
    text = f'# Borrador de propuesta · {code}\n\n{r.get("nombre", "")}\n\n'
    for title in ['necesidad', 'objetivos', 'metodologia', 'actividades', 'equipo', 'entregables', 'evaluacion']:
        text += f'## {title.capitalize()}\n\n{sections.get(title) or "PENDIENTE: adaptar a las bases"}\n\n'
        if not sections.get(title):
            pending.append('Completar sección: ' + title)
    text += f'## Plazo de ejecución\n\n{deadline}\n\n## Oferta económica\n\n' + json.dumps(amounts, ensure_ascii=False, indent=2)
    text += '\n\nFuente del tratamiento tributario: ' + tax_source + '\n\n## Pendientes\n\n' + '\n'.join('- ' + p for p in pending)
    target = directory / 'Propuesta-para-revision.md'
    target.write_text(text)
    target.chmod(0o600)
    manifest = {'codigo': code, 'creado_en': now(), 'estado': 'BORRADOR_NO_ENVIADO', 'montos': amounts, 'items': items, 'anexos_requeridos': annex_names, 'pendientes': pending, 'evaluacion': evaluation}
    private_json(directory / 'revision.json', manifest)
    return {'propuesta': str(target), 'revision': str(directory / 'revision.json'), **manifest}
