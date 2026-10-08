# Mercado Público para Camino Blanco

Integración propia para buscar oportunidades de bienestar, autocuidado, mindfulness, yoga, equipos, liderazgo, comunicación y teatro. Funciona dentro de Codex y conserva la información en el computador.

## Uso en conversación

- «Muéstrame las oportunidades de Camino Blanco y qué falta revisar».
- «Importa el Excel nuevo de Compra Ágil».
- «Revisa las bases y todos los anexos de esta compra».
- «Prepara una propuesta para esta compra, con sus anexos originales y las firmas pendientes».

Las oportunidades se separan por afinidad temática y elegibilidad. **INVESTIGAR** significa que faltan comprobaciones; **DESCARTAR** exige una incompatibilidad respaldada; **POSTULAR** significa preparar para revisión, nunca que se haya enviado una oferta. No se calculan probabilidades de ganar. La afinidad ordena por cantidad de familias temáticas coincidentes, sin premiar presupuestos altos ni ocultar resultados sin coincidencias.

## Acceso y límites reales

La importación del Excel, la biblioteca, la lectura documental y la preparación local funcionan sin ticket. Las búsquedas en vivo necesitan un ticket personal de ChileCompra. Se solicita en https://www.chilecompra.cl/api/ con Clave Única; la aceptación de términos corresponde al usuario. Se guarda fuera del proyecto, en `~/.local/share/camino-blanco-mercado-publico/ticket`, con permisos 600, o mediante `MERCADO_PUBLICO_TICKET`. No pegarlo en conversaciones, archivos públicos ni argumentos de comandos.

Compra Ágil usa la API **oficial v2**, no endpoints internos del navegador. Las consultas son paginadas y señalan cobertura parcial. Licitaciones usa la API v1 y obtiene listado y detalle completos. `filtrar_por_rubros` recibe códigos UNSPSC del detalle; no prefiltra software. No adivinar códigos por el título.

Los adjuntos autenticados se descargan desde la sesión existente del navegador y se incorporan mediante `incorporar_documento`. Esta versión **no incluye un descargador automático del portal ni copia cookies**. La persistencia de sesión pertenece al navegador del usuario. El MCP no declara autenticación solo porque exista un archivo de cookies.

La lectura PDF/DOCX extrae texto completo y lo conserva por partes, con ubicación y hash; se puede recorrer sin truncar. Los PDF escaneados necesitan OCR y revisión visual. DOCX puede contener imágenes, cuadros de texto o cambios que requieren inspección visual. Extracción no equivale a lectura confirmada. Inventario, respuestas, modificaciones y cierre deben revalidarse; las revisiones de más de 24 horas quedan pendientes. Revisar nuevamente justo antes de enviar.

OTEC se clasifica como OBLIGATORIO/PUNTUABLE/NO_REQUERIDO/DESCONOCIDO con cita exacta de bases, ubicación y hash. El revisor interpreta el requisito; la herramienta valida que la cita exista, no que su interpretación jurídica sea correcta. La ausencia de la palabra OTEC no demuestra que no se requiera. El estado HÁBIL de la empresa es una observación fechada, no una acreditación permanente ni una garantía de admisibilidad.

Los impuestos y la moneda deben confirmarse; no se presume IVA ni exención. El Excel conserva la fecha original y su conversión a `America/Santiago` pero no acredita que el plazo siga vigente. No se asume que el segundo llamado ya esté abierto.

## Propuestas y anexos

`preparar_propuesta` construye un borrador específico y revisa montos, presupuesto conocido, secciones, plazos informados y anexos faltantes. El contenido del equipo debe salir de antecedentes verificados. No verifica automáticamente la veracidad de cada frase ni sustituye revisión editorial o legal.

`completar_anexo_comprador` trabaja sobre una copia de un DOCX real del comprador y reemplaza campos exactos, incluso separados entre fragmentos de Word, preservando otras partes. No completa firmas ni declaraciones por su nombre de campo. Los anexos sin marcadores requieren edición supervisada; PDF/XLSX/DOC no se rellenan automáticamente en esta versión. Revisar siempre visualmente antes de usar. Nunca se presentan seis documentos genéricos como suficientes.

No existen herramientas para enviar ofertas, firmar, presentar declaraciones gubernamentales o pagar.

## Instalación reproducible

Requiere Python 3.11+ y Codex. Crear un entorno independiente e instalar `requirements.txt`; para pruebas, instalar pytest. Ejecutar `python -m pytest -q`. Registrar con `codex mcp add camino-blanco-mercado-publico -- /ruta/venv/bin/python /ruta/server.py`. La instalación usada por Benjamin vive fuera del worktree, en `~/.local/share/camino-blanco-mercado-publico/app`, para que sobreviva a su archivo. Reiniciar Codex o abrir un chat nuevo si no aparecen las herramientas.

Los datos, originales y borradores se guardan separados del código, en un directorio privado 700 y archivos 600. Las respuestas de API limpian secretos y parámetros de URLs. El código no lee sesiones del navegador ni las publica.

## Procedencia y publicación

Se revisó https://github.com/shinsekai-dev/mcp-mercado-publico-cl en commit `75b020c01163e66cef14ef09f470098b67611f23`. No se encontró archivo LICENSE ni licencia redistributiva en el paquete principal. El README del scraper solo dice que sigue al proyecto principal y menciona uso para ofertas legítimas; esto no constituye una autorización clara para redistribuir. Por ese motivo esta implementación es independiente: no incluye código, plantillas ni documentos del upstream.

Fuentes oficiales consultadas el 8 de octubre de 2026:

- https://www.chilecompra.cl/api/
- https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil.pdf (versión 3.0, mayo 2026)
- https://learn.chatgpt.com/docs/extend/mcp?surface=cli

Los datos privados, la biblioteca del equipo y el Excel original no forman parte de la publicación del código.
