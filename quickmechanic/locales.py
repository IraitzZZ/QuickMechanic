"""Tabla de traducciones español → inglés.

La clave es el texto tal cual aparece en el codigo (español) y el valor su
version en ingles. ``EN_EXACT`` es para frases completas y ``EN_TEMPLATES`` para
mensajes que llevan valores dentro: se escribe ``{}`` en cada hueco y el mismo
numero de huecos en inglés. ``UI_IGNORED`` son cadenas que parecen texto pero
son identificadores (nombres de objeto de Qt, claves de settings, codigos de
estado), y por eso no se traducen.

Mantenimiento: ``python -m quickmechanic.i18n`` lista lo que falta traducir de
la superficie visible; ``tests/test_i18n.py`` comprueba que esta tabla cubre los
modulos declarados en :data:`quickmechanic.i18n.CORE_TRANSLATED_MODULES`.
"""
from __future__ import annotations

__all__ = ["EN_EXACT", "EN_TEMPLATES", "UI_IGNORED"]

#: Identificadores internos (no texto visible): nombres de objeto, claves y codigos.
UI_IGNORED: frozenset[str] = frozenset({
    "headerSearch",
    "QuickMechanic", "version", "favorites", "win32", "cars", "content", "ascii",
    "utf-8-sig", "tabs", "accent", "info", "muted", "dato", "aviso", "peligro",
    "gold", "file", "abs", "cut", "rpm", "gears", "final", "top", "drive",
    "power", "torque", "mass", "ratio", "installed", "editable", "locked",
    "available", "present", "active", "skins", "motor", "sonido", "transmisión",
    "fitment", "data", "TODO", "DPI",
    # Identificadores de la pestana Taller (claves de fila, series de la grafica).
    "zero100", "zero200", "accel", "brake", "label", "points", "markers", "utf-8",
    # Atajos de teclado y formatos de archivo (no se traducen).
    "Ctrl+T", "Ctrl+P", "Ctrl+R", "Ctrl+I", "Ctrl+Shift+B", "Ctrl+D", "Ctrl+E",
    "Ctrl+F", "Ctrl+S", "Alt+Up", "Alt+Down", "Ctrl+Tab", "Ctrl+Shift+Tab", "Ctrl+Shift+F", "Ctrl+Shift+C",
    "Ctrl+Shift+H", "Ctrl+Shift+L", "Ctrl+L", "F1", "txt", "html", "json", "qmsetup", "csv",
    "Ctrl+Shift+D", "Ctrl+Shift+E", "Ctrl+Shift+O", "Ctrl+Shift+P", "Ctrl+Shift+N",
    "Ctrl+Shift+S", "Alt+Shift+Up", "Alt+Shift+Down", "F5", "Esc",
    "Ctrl+Home", "Ctrl+End", "Ctrl+Q", "Ctrl+,", "Ctrl+Shift+M", "Ctrl+Shift+A", "Ctrl+Shift+G",
    "Ctrl+Shift+K", "Ctrl+Shift+U", "Ctrl+Shift+Y", "Delete", "name", "recent",
    # Palabras clave de la paleta Ctrl+K (solo sirven para encontrar comandos) y nombres internos.
    "navSection", "Ctrl+K", "filtrar lista coleccion", "excel hoja", "estrella",
    "grabar escribir", "atras", "adelante",
    # Estilos y nombres de objeto de Qt.
    "iconButton", "sectionLabel", "previewSubtitle", "banner", "pageEyebrow",
    "pageTitle", "pageDescription", "pageHeading", "navRail", "dashboardHeading",
    "navButton", "header", "appTitle", "appSubtitle", "headerNote", "carHeader",
    "carName", "carBrand", "footer", "footerStatus", "danger", "primary",
    "communityNotification", "communityBadge", "communityMessage", "heroButton",
    "guideStrip", "guideStripText", "guideDialog", "guideEyebrow", "guideTitle",
    "guideSubtitle", "guideCard", "guideStep", "guideBody", "guideProgress",
    "guideStartup", "integrationCard", "integrationMark", "integrationTitle",
    "integrationStatus", "integrationPath", "appStripe", "headerButton",
    "pill", "statTile", "statTitle", "statValue", "statUnit", "previewCard",
    "previewBadge", "previewTitle", "previewViewport", "previewArea",    "zoomSlider", "navBrand", "navBrandSub", "navCarStatus", "homeLink",

    # Ayudantes de widgets (nombres de funcion/clase, no texto).
    "dspin", "ispin", "Panel", "note", "heading", "GridView", "BrandMark",
    "Pill", "StatTile", "StatRow", "CarPreview", "sectionRule",
    # Atajos de teclado, rutas de ejemplo y titulos que ya estan en ingles.
    "Ctrl+D", "Ctrl+S", "Ctrl+F", "Ctrl+E", "Ctrl+Y", "content manager.exe",
    "frozen", "quickmechanic", "ghost", "palette", "random", "export", "sync",
    "QUICK MECHANIC", "CONTENT MANAGER", "PERFORMANCE OVERVIEW", "POWERTRAIN LAB",
    "GEARBOX & RATIOS", "CHASSIS SETUP", "VEHICLE INSPECTION", "DRIVER AIDS",
    "EXPERT PARAMETERS", "Guardado: ", " con cambios sin guardar: ", "01  /  ",
})

EN_EXACT: dict[str, str] = {
    "Taller": "Workshop",
    "Taller de ajuste para Assetto Corsa": "Tuning shop for Assetto Corsa",
    "⌕    Buscar herramienta": "⌕    Search tool",
    "Buscar una herramienta o acción (Ctrl+K)": "Search for a tool or action (Ctrl+K)",
    "Editable · data/ extraída": "Editable · data/ extracted",
    "Bloqueado · data.acd": "Locked · data.acd",
    "Sin carpeta data/": "No data/ folder",
    "Buscar herramienta o acción… (Enter)": "Search tool or action… (Enter)",
    "Buscar": "Search",
    "Todas las herramientas": "All tools",
    "Abrir el buscador de herramientas (Ctrl+K)": "Open the tool search (Ctrl+K)",
    "Coche aleatorio": "Random car",
    "Elegir al azar un coche de la lista (Ctrl+Shift+N)": "Pick a random car from the list (Ctrl+Shift+N)",
    "Exportar CSV": "Export CSV",
    "Exportar la biblioteca visible a CSV (Ctrl+E)": "Export the visible library to CSV (Ctrl+E)",
    "Sincronizar biblioteca": "Sync library",
    "Volver a leer la carpeta de coches de Assetto Corsa": "Re-read the Assetto Corsa cars folder",
    "Coches recientes": "Recent cars",
    "Favoritos": "Favorites",
    "Herramientas recientes": "Recent tools",
    "Abre un coche para verlo aquí.": "Open a car to see it here.",
    "Marca coches con ★ para fijarlos aquí.": "Star cars with ★ to pin them here.",
    "Las herramientas que abras aparecerán aquí.": "Tools you open will appear here.",
    "Selecciona un coche para usar estas mejoras.": "Select a car to use these upgrades.",
    "Este coche no tiene carpeta data/. Si tiene data.acd se extrae al seleccionarlo.":
        "This car has no data/ folder. If it has data.acd, it is extracted when selected.",
    "Perfiles de mejora": "Upgrade profiles",
    "Versión": "Version",
    "Relaciones de transmisión": "Transmission ratios",
    "Aplica un perfil de mejora. Se modifican los ficheros del coche.":
        "Applies an upgrade profile. The car files are modified.",
    "Stock": "Stock",
    "Restaura la configuración de fábrica. Se modifican los ficheros del coche.":
        "Restores the factory setup. The car files are modified.",
    "Volver a stock": "Back to stock",
    "¿Restaurar la configuración de fábrica del coche?": "Restore the car's factory setup?",
    "Coche restaurado a stock": "Car restored to stock",
    "No se pudo restaurar el stock": "Could not restore stock",
    "Cambios sin guardar": "Unsaved changes",
    "Guarda o descarta los cambios del coche antes de aplicar una mejora.":
        "Save or discard the car's changes before applying an upgrade.",
    "Aplicar stage": "Apply stage",
    "No se pudo aplicar el stage": "Could not apply the stage",
    "Este coche no tiene este fichero RTO.": "This car does not have this RTO file.",
    "Añadir relación": "Add ratio",
    "Relación (ej. 3.250):": "Ratio (e.g. 3.250):",
    "RTO sin guardar": "Unsaved RTO",
    "¿Descartar los cambios sin guardar del RTO?": "Discard the unsaved RTO changes?",
    "Añadir": "Add",
    "Quitar": "Remove",
    "Ordenar": "Sort",
    "Ficha guardada": "Card saved",
    "No se pudo guardar la ficha": "Could not save the card",
    "Este coche no tiene ui/ui_car.json": "This car has no ui/ui_car.json",
    "Ficha ui_car": "UI card (ui_car)",
    "Guardar ficha": "Save card",
    "Datos del coche (ui_car.json)": "Car data (ui_car.json)",
    "Tags (separados por coma)": "Tags (comma separated)",
    "Biblioteca": "Library",
    "Componentes guardados": "Saved components",
    "Tipo": "Type",
    "Eliminar": "Delete",
    "Importar…": "Import…",
    "Exportar todo…": "Export all…",
    "Importar componentes": "Import components",
    "Exportar componentes": "Export components",
    "Componentes importados": "Components imported",
    "Biblioteca exportada": "Library exported",
    "Respaldos": "Backups",
    "Copias de seguridad": "Backups",
    "Restaura las copias .bak que se crean al guardar (data/ y ui/). Vuelve a la última versión guardada antes de cada cambio.":
        "Restores the .bak copies created when saving (data/ and ui/). Returns to the last saved version before each change.",
    "Restaurar copias .bak": "Restore .bak copies",
    "Restaurar": "Restore",
    "No hay copias .bak para restaurar": "There are no .bak copies to restore",
    "Circuitos": "Tracks",
    "No se ha encontrado la instalación de Assetto Corsa.": "The Assetto Corsa installation was not found.",
    "Ruta de circuito no válida": "Invalid track path",
    "La carpeta ya no está disponible dentro de la biblioteca de Assetto Corsa.":
        "The folder is no longer available in the Assetto Corsa library.",
    "El INI ya no está disponible dentro de las ubicaciones reconocidas del circuito.":
        "The INI is no longer available in the recognized track locations.",
    "TRACK LIBRARY": "TRACK LIBRARY",
    "Explora circuitos y layouts instalados; inspección local de solo lectura":
        "Browse installed tracks and layouts; local read-only inspection",
    "Ctrl+Shift+T": "Ctrl+Shift+T",
    "Mejoras": "Upgrades",
    "Ctrl+M": "Ctrl+M",
    "Stage tuning, RTO, ficha ui_car, biblioteca de componentes y copias de seguridad":
        "Stage tuning, RTO, ui_car sheet, component library and backups",
    'Inspector de datos .ini (solo lectura)': 'Data inspector .ini (read only)',
    'Filtrar por fichero, seccion, clave o valor…': 'Filter by file, section, key or value…',
    'Localizar': 'Locate',
    'Solo lectura: aqui se mira el valor tal cual esta en el .ini, sin tocar nada.': 'Read only: here you look at the value exactly as it is in the .ini, touching nothing.',
    'Clonar coche': 'Clone car',
    'nombre de la carpeta nueva (opcional)': 'new folder name (optional)',
    'Carpeta destino': 'Destination folder',
    'Clonar este coche': 'Clone this car',
    'Copia entera del coche en content/cars con otro nombre; el original no se toca': 'Full copy of the car into content/cars under another name; the original is untouched',
    'Nombre de la carpeta nueva:': 'New folder name:',
    'Todas las claves rapidas existen en este coche.': 'All quick keys exist on this car.',
    'Este coche no declara ninguna de esas claves; no se ha tocado nada.': 'This car declares none of those keys; nothing was changed.',
    'Sin coche': 'No car selected',
    'Elige un coche de la biblioteca para clonarlo.': 'Pick a car from the library to clone it.',
    'Ruta no valida': 'Invalid path',
    'No se encontro la carpeta content/cars del coche.': "The car's content/cars folder was not found.",
    'Ya existe': 'Already exists',
    'Confirmar clonado': 'Confirm cloning',
    'El clonado necesita un coche cargado.': 'Cloning needs a loaded car.',
    'Este coche no declara esta clave; no se inventa.': 'This car does not declare this key; it is not invented.',
    'presion delantera': 'front pressure',
    'presion trasera': 'rear pressure',
    'reparto de freno': 'brake bias',
    'par de frenado': 'braking torque',
    'altura delantera': 'front ride height',
    'altura trasera': 'rear ride height',
    'No se puede clonar': 'Cannot clone',
    'No se pudo clonar': 'Could not clone',
    # Titulos con barra: el escaner los salta, pero se ven en la interfaz.
    "Peso/potencia": "Power/weight",
    "Prestaciones, comparador, gearing, setups, versiones, respaldos e informes":
        "Performance, comparison, gearing, setups, versions, backups and reports",
    "Busca circuitos instalados, layouts, metadatos y archivos de configuración en modo lectura.":
        "Browse installed tracks, layouts, metadata and configuration files in read-only mode.",
    "Prestaciones, setups, historial, ajustes y respaldos del coche seleccionado.":
        "Performance, setups, history, adjustments and backups for the selected car.",
    "CIRCUITOS INSTALADOS · INSPECCIÓN Y EDICIÓN SEGURA CON RESPALDO":
        "INSTALLED TRACKS · INSPECTION AND SAFE EDITING WITH BACKUP",
    "Buscar circuito, layout, país o autor…": "Search tracks, layout, country or author…",
    "Explora circuitos y layouts. Edita solo valores numéricos ya existentes en INI reconocidos; "
    "se crea un respaldo antes de guardar.":
        "Browse tracks and layouts. Edit only existing numeric values in recognized INI files; "
        "a backup is created before saving.",
    "Selecciona un circuito": "Select a track",
    "Buscar en sección, clave o valor…": "Search section, key or value…",
    "Abrir carpeta": "Open folder",
    "Abrir INI": "Open INI",
    "Abre el INI seleccionado en el editor de texto del sistema; el editor rápido guarda con copia de seguridad.":
        "Opens the selected INI in the system text editor; the quick editor saves with a backup.",
    "Layout:": "Layout:",
    "Ficheros INI:": "INI files:",
    "País": "Country",
    "Autor": "Author",
    "Año": "Year",
    "Descripción": "Description",
    "Longitud": "Length",
    "Pit boxes": "Pit boxes",
    "Metadatos": "Metadata",
    "Modelos": "Models",
    "No se encontraron INI técnicos en las ubicaciones reconocidas.":
        "No technical INI files found in recognized locations.",
    "Sin circuitos instalados": "No tracks installed",
    "model": "model",
    "author": "author",
    "year": "year",
    "description": "description",
    "length": "length",
    "pitboxes": "pit boxes",
    "ui_track.json no encontrado": "ui_track.json not found",
    "Guardar valor": "Save value",
    "No se pudo guardar el INI": "Could not save the INI",
    "INI guardado · copia de seguridad creada antes del cambio":
        "INI saved · a backup was created before the change",
    "Circuitos: {}": "Tracks: {}",
    "Actualizar circuitos": "Refresh tracks",
    "[SIMPLE]": "[SIMPLE]",
    '0-100 km/h': '0-100 km/h',
    '0-200 km/h': '0-200 km/h',
    'Simulacion cuasi-estatica con la curva de par actual': 'Quasi-static simulation with the current torque curve',
    'Misma simulacion hasta 200 km/h': 'Same simulation up to 200 km/h',
    'Punta estimada': 'Estimated top speed',
    'Velocidad donde la fuerza iguala la resistencia': 'Speed where drive force equals resistance',
    'CV por tonelada y kg por CV': 'HP per tonne and kg per HP',
    'Aceleracion': 'Acceleration',
    'Aceleracion longitudinal maxima estimada': 'Estimated peak longitudinal acceleration',
    'Curva del motor · arrastra los puntos para editarla': 'Engine curve · drag the points to edit it',
    'Par (power.lut)': 'Torque (power.lut)',
    'Potencia (CV)': 'Power (HP)',
    'Frenada en rueda': 'Wheel braking',
    'Curva': 'Curve',
    'Simulador de cambio · velocidad por marcha': 'Gear simulator · speed per gear',
    'Gearing optimo': 'Optimal gearing',
    'Auto (según potencia)': 'Auto (from power)',
    'Circuito': 'Circuit',
    'Calcular relaciones': 'Calculate ratios',
    'Aplicar a drivetrain.ini': 'Apply to drivetrain.ini',
    'Comparador de coches': 'Car comparator',
    'Comparar con': 'Compare with',
    'Comparar': 'Compare',
    'Diagnostico visual y conflictos': 'Visual diagnostics and conflicts',
    'Revisar de nuevo': 'Check again',
    'Presets de estilo': 'Style presets',
    'Ajustes rapidos (solo claves existentes)': 'Quick settings (existing keys only)',
    'PRESSURE_STATIC del eje delantero': 'PRESSURE_STATIC of the front axle',
    'PRESSURE_STATIC del eje trasero': 'PRESSURE_STATIC of the rear axle',
    'FRONT_SHARE: reparto de frenada al eje delantero': 'FRONT_SHARE: brake bias to the front axle',
    'ROD_LENGTH del eje delantero (altura libre)': 'ROD_LENGTH of the front axle (ride height)',
    'ROD_LENGTH del eje trasero': 'ROD_LENGTH of the rear axle',
    'Valor del parametro de aero.ini elegido': 'Value of the selected aero.ini parameter',
    'Aero (aero.ini)': 'Aero (aero.ini)',
    'Aplicar valor de aero': 'Apply aero value',
    'Setup Manager · por circuito y condiciones': 'Setup Manager · per circuit and conditions',
    'Nombre del setup': 'Setup name',
    'seco, lluvia, 25 °C…': 'dry, rain, 25 °C…',
    'Condiciones': 'Conditions',
    'Estilo': 'Style',
    'Gestor de versiones': 'Version manager',
    'Etiqueta de la version': 'Version label',
    'Etiqueta': 'Label',
    'Respaldos y backup inteligente': 'Backups and smart backup',
    'Informe, historial y estadisticas': 'Report, history and statistics',
    'Relaciones propuestas; revisa el simulador antes de aplicarlas.': 'Suggested ratios; check the simulator before applying them.',
    'Exportar setup': 'Export setup',
    'Setup de Quick Mechanic (*.qmsetup)': 'Quick Mechanic setup (*.qmsetup)',
    'Importar setup': 'Import setup',
    'Restaurar un fichero': 'Restore a single file',
    'Ficheros del respaldo:': 'Files in the backup:',
    'Guardar informe': 'Save report',
    'Neumaticos delanteros': 'Front tyres',
    'Neumaticos traseros': 'Rear tyres',
    'Reparto de freno': 'Brake bias',
    'FRONT_SHARE de brakes.ini': 'FRONT_SHARE from brakes.ini',
    'Par de frenado': 'Braking torque',
    'Altura delantera': 'Front ride height',
    'ROD_LENGTH delantero': 'Front ROD_LENGTH',
    'Altura trasera': 'Rear ride height',
    'ROD_LENGTH trasero': 'Rear ROD_LENGTH',
    'Cargar': 'Load',
    'Borrar': 'Delete',
    'Exportar': 'Export',
    'Importar': 'Import',
    'Guardar version': 'Save version',
    'Restaurar': 'Restore',
    'Crear respaldo': 'Create backup',
    'Restaurar fichero': 'Restore file',
    'Limpiar antiguos': 'Clean old ones',
    'Actualizar': 'Refresh',
    'Exportar .txt': 'Export .txt',
    'Exportar .html': 'Export .html',
    'Historial de cambios': 'Change history',
    'Estadisticas de la biblioteca': 'Library statistics',
    'Este coche no declara aero.ini: el downforce va dentro del modelo de AC.': 'This car has no aero.ini: downforce lives inside the AC model.',
    'Elige un coche para ver sus respaldos.': 'Pick a car to see its backups.',
    'Todavia no hay respaldos: se crean solos antes de cada guardado y swap.': 'No backups yet: they are created before every save and swap.',
    'Elige un coche con carpeta data/ para ver su curva.': 'Pick a car with a data/ folder to see its curve.',
    'Vista de potencia: la curva real que se edita es el par (power.lut). Cambia a «Par» para arrastrar los puntos.': 'Power view: the curve you actually edit is torque (power.lut). Switch to «Torque» to drag the points.',
    'Fuerza de frenada estimada: el limite lo pone el par de freno (MAX_TORQUE) o el agarre disponible, y crece con la carga aerodinamica. Se ajusta con el par de frenado y el reparto de los campos de la izquierda.': 'Estimated braking force: limited by brake torque (MAX_TORQUE) or available grip, and it grows with aero load. Adjust it with the braking torque and bias fields on the left.',
    'No hay relaciones de cambio legibles.': 'No readable gear ratios.',
    'Este coche no tiene relaciones suficientes para recalcularlas.': 'This car has too few ratios to recalculate them.',
    'Falta el nombre': 'Name missing',
    'Escribe un nombre para el setup.': 'Type a name for the setup.',
    'Respaldo vacio': 'Empty backup',
    'Este respaldo no contiene archivos de data/.': 'This backup holds no data/ files.',
    'Texto (*.txt)': 'Text (*.txt)',
    'HTML (*.html)': 'HTML (*.html)',
    'Sin cambios': 'No changes',
    'No se pudo cargar': 'Could not load',
    'No se pudo importar': 'Could not import',
    'No se pudo guardar la version': 'Could not save the version',
    'No se pudo restaurar': 'Could not restore',
    'Setup no compatible': 'Incompatible setup',
    'No se pudo respaldar': 'Could not create the backup',
    'No se pudo escribir el informe': 'Could not write the report',
    # ------------------------------------------------------------ barra lateral
    "Buscar coche por nombre, carpeta o marca...": "Search cars by name, folder or brand...",
    "Mostrar solo favoritos": "Show favourites only",
    "Garaje": "Garage",
    "Ingeniería": "Engineering",
    "Herramientas": "Tools",
    "Buscar coche": "Find car",
    "Exportar biblioteca a CSV": "Export library to CSV",
    "Guardar cambios": "Save changes",
    "Edición": "Edit",
    "Filtros borrados": "Filters cleared",
    "Historial de coches recientes borrado": "Recent cars history cleared",
    "No hay ningún coche seleccionado": "No car selected",
    "Nombre copiado al portapapeles": "Name copied to clipboard",
    "Todavía no has abierto ningún coche": "You haven't opened any car yet",
    "No hay favoritos en la lista visible": "No favourites in the visible list",
    "Ruta copiada al portapapeles": "Path copied to clipboard",
    "Mostrar solo coches con carpeta data/ editable": "Show only cars with an editable data/ folder",
    "Exportar la biblioteca visible a una hoja de cálculo CSV (Ctrl+E)":
        "Export the visible library to a CSV spreadsheet (Ctrl+E)",
    "COLECCIÓN DE VEHÍCULOS": "CAR COLLECTION",
    "Exportar biblioteca": "Export library",
    "CSV (*.csv)": "CSV (*.csv)",
    "Editable": "Editable",
    "Nombre": "Name",
    "Identificador": "ID",
    "Marca": "Brand",
    "Clase": "Class",
    "Estado": "Status",
    "Carpeta": "Folder",
    "favoritos": "favourites",
    "editables": "editable",
    # ------------------------------------------------------------ pestanas
    "Resumen": "Overview",
    "Motor": "Engine",
    "Caja de cambios": "Gearbox",
    "Caja cambios": "Gearbox",
    "Chasis": "Chassis",
    "Diagnostico": "Diagnostics",
    "Diagnóstico": "Diagnostics",
    "ⓘ    Diagnostico": "ⓘ    Diagnostics",
    "Asistencias": "Driver aids",
    "Avanzado": "Advanced",
    "GARAGE": "GARAGE",
    "Resumen de rendimiento y estadisticas de la biblioteca":
        "Performance overview and library statistics",
    "Curvas de potencia y par, limitador y turbo":
        "Power and torque curves, limiter and turbo",
    "Editor de relaciones, diferencial y velocidades":
        "Gear ratios, differential and speed editor",
    "Suspension, geometria, frenos y neumaticos":
        "Suspension, geometry, brakes and tyres",
    "Ficha tecnica, estado de archivos y diagnostico":
        "Spec sheet, file status and diagnostics",
    "Compatibilidad y controles de ABS y traccion":
        "ABS and traction control compatibility and switches",
    "Editor experto de parametros numericos existentes en archivos locales":
        "Expert editor for numeric parameters already present in local files",
    "Estado de la colección y cálculos derivados de los archivos del coche.":
        "Collection status and figures derived from the car files.",
    "Estado de la colección y cálculos derivados de los archivos locales del coche.":
        "Collection status and figures derived from the car's local files.",
    "Lee power.lut y permite editar sus puntos, corte, turbo y entrega de par.":
        "Reads power.lut and lets you edit its points, cut-off, turbo and torque delivery.",
    "Ajusta relaciones y diferencial; las velocidades teóricas se muestran en una tabla.":
        "Adjusts ratios and differential; theoretical speeds are shown in a table.",
    "Suspensión, geometría, frenos, masa y presiones con análisis instantáneo.":
        "Suspension, geometry, brakes, mass and pressures with instant analysis.",
    "Ficha técnica, alertas de seguridad y estado de los archivos de física.":
        "Spec sheet, safety alerts and the status of the physics files.",
    "Inspecciona ABS y control de tracción cuando están declarados por el coche.":
        "Inspects ABS and traction control when the car declares them.",
    "Editor experto limitado a parámetros numéricos presentes en los INI abiertos.":
        "Expert editor limited to numeric parameters present in the open INI files.",
    # ------------------------------------------------------------ cabecera
    "TALLER DE COCHES · ASSETTO CORSA": "CAR WORKSHOP · ASSETTO CORSA",
    "Recargar": "Reload",
    "⌕  Buscar herramienta…  Ctrl+K": "⌕  Search tool…  Ctrl+K",
    "GARAJE  ›  RESUMEN": "GARAGE  ›  OVERVIEW",
    "Paleta de comandos: páginas y acciones (Ctrl+K)": "Command palette: pages and actions (Ctrl+K)",
    "GARAJE": "GARAGE",
    "INGENIERÍA": "ENGINEERING",
    "DIAGNÓSTICO": "DIAGNOSTICS",
    "HERRAMIENTAS": "TOOLS",
    "Stage tuning, RTO, ficha ui_car y copias de seguridad del coche seleccionado.":
        "Stage tuning, RTO, ui_car sheet and backups for the selected car.",
    "Vuelve a leer content/cars sin bloquear la interfaz":
        "Re-reads content/cars without blocking the interface",
    "Abrir data": "Open data",
    "Edita la carpeta data de un coche extraido": "Edit the data folder of an extracted car",
    "Ruta AC": "AC path",
    "Si el juego no esta en la ruta de Steam": "If the game is not in the Steam path",
    "Interfaz": "Interface",
    "Tema carbón y oro; ajusta el tamaño de la interfaz":
        "Carbon and gold theme; adjust the interface size",
    "Guía": "Guide",
    "Guía rápida, seguridad y atajos de teclado": "Quick guide, safety and keyboard shortcuts",
    "Créditos y licencia de Quick Mechanic": "Credits and licence of Quick Mechanic",
    # ------------------------------------------------------------ coche y pie
    "Selecciona un coche": "Select a car",
    "Marcar como favorito (Ctrl+D)": "Mark as favourite (Ctrl+D)",
    "Quitar de favoritos (Ctrl+D)": "Remove from favourites (Ctrl+D)",
    "Alternar favorito": "Toggle favourite",
    "Deshacer": "Undo",
    "Rehacer": "Redo",
    "Descartar cambios": "Discard changes",
    "Vuelve a leer los .ini del coche y tira los cambios en memoria (Ctrl+R)":
        "Re-reads the car .ini files and drops the in-memory changes (Ctrl+R)",
    "Deshacer ajuste (Ctrl+Z)": "Undo change (Ctrl+Z)",
    "Rehacer ajuste (Ctrl+Y)": "Redo change (Ctrl+Y)",
    "Perfiles": "Profiles",
    "Guardar, cargar o importar/exportar perfiles de setup":
        "Save, load or import/export setup profiles",
    "Swaps": "Swaps",
    "Intercambiar componentes entre coches con validación y copia de seguridad":
        "Swap components between cars with validation and a backup",
    "Guardar todo": "Save all",
    "Escribe solo las lineas cambiadas; antes crea un ZIP de seguridad y conserva el .bak original (Ctrl+S)":
        "Writes only the changed lines; first creates a safety ZIP and keeps the original .bak (Ctrl+S)",
    "Selecciona un coche con carpeta data/ para empezar a tunear.":
        "Select a car with a data/ folder to start tuning.",
    "   ·   respaldo completo y .bak conservados": "   ·   full backup and .bak kept",
    "Guardar": "Save",
    "Descartar": "Discard",
    "Cancelar": "Cancel",
    "Descartar cambios sin guardar": "Discard unsaved changes",
    "Cambios sin guardar": "Unsaved changes",
    "¿Quieres guardar los cambios de {0} antes de continuar?":
        "Do you want to save the changes to {0} before continuing?",
    # ------------------------------------------------------------ escaneo
    "La biblioteca ya se está escaneando…": "The library is already being scanned…",
    "Escaneando carpetas y fichas de coches…": "Scanning car folders and cards…",
    "Leyendo la biblioteca en segundo plano; la interfaz sigue disponible…":
        "Reading the library in the background; the interface stays available…",
    "Assetto Corsa no encontrado": "Assetto Corsa not found",
    "No se ha encontrado Assetto Corsa. Usa 'Ruta AC' para indicar la carpeta.":
        "Assetto Corsa was not found. Use 'AC path' to point to the folder.",
    "Biblioteca vacía": "Empty library",
    "No hay coches visibles para exportar.": "There are no visible cars to export.",
    "No se pudo exportar la biblioteca": "Could not export the library",
    "solo data.acd": "data.acd only",
    "no editable": "not editable",
    # ---------------------------------------------------------------- Discord
    "Novedades, ayuda y soporte de Quick Mechanic": "News, help and support for Quick Mechanic",
    "Discord ↗": "Discord ↗",
    "Abrir la invitación oficial de Discord en el navegador":
        "Open the official Discord invite in your browser",
    "Cerrar este aviso; volverá a aparecer al próximo inicio":
        "Close this notice; it will show again on the next start",
    "COMUNIDAD  /  Novedades, ayuda y guía rápida": "COMMUNITY  /  News, help and a quick guide",
    "Abrir la comunidad oficial para ayuda y avisos de versiones":
        "Open the official community for help and release news",
    "Abrir guía": "Open guide",
    "QM  /  COMUNIDAD": "QM  /  COMMUNITY",
    # ------------------------------------------------------------------ swaps
    "Crear copia de seguridad ahora…": "Create a backup now…",
    "Restaurar copia de seguridad…": "Restore a backup…",
    "Copia de seguridad creada": "Backup created",
    "Restaurar copia de seguridad": "Restore backup",
    "Respaldos Quick Mechanic (*.zip)": "Quick Mechanic backups (*.zip)",
    "Restauración completada": "Restore completed",
    "Confirmar restauración": "Confirm restore",
    "Se restaurarán únicamente data/ y data.acd incluidos en el respaldo. "
    "No se eliminarán otros archivos; antes se creará otro respaldo de seguridad. ¿Continuar?":
        "Only the data/ and data.acd included in the backup will be restored. "
        "No other files will be deleted; another safety backup is created first. Continue?",
    "Selecciona primero un coche para continuar.": "Select a car first to continue.",
    "Intercambiar motor…": "Swap engine…",
    "Intercambiar sonido…": "Swap sound…",
    "Copiar transmisión…": "Copy transmission…",
    "Copiar suspensión / fitment…": "Copy suspension / fitment…",
    "Elegir coche donante": "Choose donor car",
    "Intercambio aplicado": "Swap applied",
    "Destino no editable": "Target not editable",
    "Restaura primero una copia con data/ extraída antes de aplicar un swap de física.":
        "First restore a copy with data/ extracted before applying a physics swap.",
    "Sin donantes compatibles": "No compatible donors",
    "Hace falta otro coche con carpeta data/ extraída y editable.":
        "Another car with an extracted, editable data/ folder is required.",
    "Este swap requiere una carpeta data/ extraída y editable":
        "This swap needs an extracted, editable data/ folder",
    "No se pudo crear el respaldo": "Could not create the backup",
    "No se pudo restaurar el respaldo": "Could not restore the backup",
    "Intercambio no disponible": "Swap not available",
    "No se pudo aplicar el intercambio": "Could not apply the swap",
    # ---------------------------------------------------------- perfiles y drift
    "Guardar perfil actual…": "Save current profile…",
    "Aplicar preset Drift adaptable…": "Apply adaptable Drift preset…",
    "Cargar perfil": "Load profile",
    "Importar perfil JSON…": "Import JSON profile…",
    "Exportar perfil actual…": "Export current profile…",
    "Eliminar perfil guardado…": "Delete saved profile…",
    "Sin perfiles guardados": "No saved profiles",
    "Preset Drift adaptable": "Adaptable Drift preset",
    "Preset Drift": "Drift preset",
    "Preset Drift aplicado": "Drift preset applied",
    "Se ajustarán solo parámetros compatibles ya presentes en este coche; "
    "los cambios quedarán en memoria, sin guardar en disco. Es una base orientativa, "
    "no una puesta a punto universal. ¿Continuar?":
        "Only compatible parameters already present in this car will be adjusted; the changes "
        "stay in memory and are not written to disk. It is a starting point, not a universal "
        "tune-up. Continue?",
    "Guardar perfil": "Save profile",
    "Nombre del perfil:": "Profile name:",
    "Importar perfil": "Import profile",
    "Perfil Quick Mechanic (*.json)": "Quick Mechanic profile (*.json)",
    "Exportar perfil": "Export profile",
    "JSON (*.json)": "JSON (*.json)",
    "Eliminar perfil": "Delete profile",
    "Perfil:": "Profile:",
    "No se pudo guardar el perfil": "Could not save the profile",
    "Perfil no válido": "Invalid profile",
    "No se pudo exportar": "Could not export",
    "No se pudo guardar la preferencia": "Could not save the preference",
    "No se pudo guardar": "Could not save",
    # ------------------------------------------------------------- reparar datos
    "Revisar y reparar datos…": "Check and repair data…",
    "Busca errores en car.ini y aero.ini. Pide confirmacion y guarda una copia .bak antes de tocar nada.":
        "Looks for errors in car.ini and aero.ini. Asks for confirmation and saves a .bak copy before changing anything.",
    "Reparar datos del coche": "Repair car data",
    "No se pudo revisar el coche": "Could not check the car",
    "No se pudo reparar el coche": "Could not repair the car",
    "No se pudo recargar el coche": "Could not reload the car",
    "Datos correctos": "Data is correct",
    "No se ha encontrado ningún problema en los datos de este coche.":
        "No problems were found in this car's data.",
    "Reparación completada": "Repair completed",
    "ninguno": "none",
    # ------------------------------------------------------------- preferencias
    "Tamaño de la interfaz": "Interface size",
    "Compacta · 90%": "Compact · 90%",
    "Estándar · 100%": "Standard · 100%",
    "Cómoda · 110%": "Comfortable · 110%",
    "Grande · 120%": "Large · 120%",
    "Iniciar con Windows y abrir en segundo plano": "Start with Windows and open in the background",
    "Al cerrar, dejar Quick Mechanic en la bandeja": "On close, keep Quick Mechanic in the tray",
    "Mostrar animación de carga al iniciar": "Show the loading animation on start",
    "Mostrar guía al iniciar": "Show the guide on start",
    "Guía de bienvenida": "Welcome guide",
    "Animación de carga": "Loading animation",
    "Al cerrar, Quick Mechanic quedará en la bandeja": "On close, Quick Mechanic will stay in the tray",
    "Al cerrar, Quick Mechanic saldrá completamente": "On close, Quick Mechanic will quit completely",
    "Inicio con Windows": "Windows startup",
    "Quick Mechanic · Assetto Corsa": "Quick Mechanic · Assetto Corsa",
    "Abrir Quick Mechanic": "Open Quick Mechanic",
    "Salir completamente": "Quit completely",
    # -------------------------------------------------------------- ventanas
    "Información · Quick Mechanic": "About · Quick Mechanic",
    "Cerrar": "Close",
    "Elige la carpeta de Assetto Corsa (la que contiene content/cars)":
        "Choose the Assetto Corsa folder (the one that contains content/cars)",
    "Elige la carpeta data del coche": "Choose the car's data folder",
    "Carpeta incorrecta": "Wrong folder",
    "Esa carpeta no contiene content/cars. Elige la carpeta principal (la que tiene acs.exe).":
        "That folder does not contain content/cars. Choose the main folder (the one with acs.exe).",
    "No parece una carpeta data": "This does not look like a data folder",
    "Dentro no hay engine.ini. Elige la carpeta 'data' del coche.":
        "There is no engine.ini inside. Choose the car's 'data' folder.",
    "Editor de coches de Assetto Corsa": "Assetto Corsa car editor",
    "ruta de la instalacion de Assetto Corsa": "path to the Assetto Corsa installation",
    "inicia minimizada/en bandeja (uso del inicio de Windows)":
        "starts minimised/in the tray (used by the Windows startup entry)",
    "comprueba la instalacion y el ciclo de edicion sin abrir la ventana":
        "checks the installation and the editing cycle without opening the window",
    "escribe el informe del --selftest en un fichero": "writes the --selftest report to a file",
    # ---------------------------------------------------------------- previsualizacion
    "Ningun coche seleccionado": "No car selected",
    "Elige un coche de la lista para ver su foto": "Pick a car from the list to see its picture",
    "Sin previsualizacion": "No preview",
    "SIN PREVISUALIZACION": "NO PREVIEW",
    "Sin carpeta skins/ (el mod no trae skins)": "No skins/ folder (this mod ships without skins)",
    "sin imagen preview": "no preview image",
    "Ningun coche": "No car",
    "Doble clic para abrir la imagen original": "Double-click to open the original image",
    "Amplía la previsualización hasta el 200%": "Zoom the preview up to 200%",
    "Abrir imagen de previsualización a tamaño completo": "Open the preview image at full size",
    "Skins del coche (la imagen es la preview de cada una)":
        "Car skins (each image is that skin's preview)",
    "Quick Mechanic · Vehicle engineering": "Quick Mechanic · Vehicle engineering",
    "ZOOM": "ZOOM",
    "Skins": "Skins",
    # ------------------------------------------------------------- inicio (splash)
    "PREPARANDO BOX DIGITAL": "PREPARING DIGITAL PIT BOX",
    "INICIALIZANDO TALLER": "STARTING WORKSHOP",
    "ESCANEANDO BIBLIOTECA DE COCHES": "SCANNING CAR LIBRARY",
    "LEYENDO COCHES Y FICHAS": "READING CARS AND DATA CARDS",
    "BIBLIOTECA NO DISPONIBLE": "LIBRARY UNAVAILABLE",
    "VEHICLE ENGINEERING · ASSETTO CORSA": "VEHICLE ENGINEERING · ASSETTO CORSA",
    "SIM RACING VEHICLE ENGINEERING": "SIM RACING VEHICLE ENGINEERING",
    "activada": "enabled",
    "desactivada": "disabled",
    "TEMA FIJO · CARBÓN / GRAFITO / ORO": "FIXED THEME · CARBON / GRAPHITE / GOLD",
    "Data": "Data",
    "Turbo": "Turbo",
    "01  /  PERFORMANCE OVERVIEW": "01  /  PERFORMANCE OVERVIEW",
    # ------------------------------------------------------------------- guia
    "01  ·  TU GARAJE": "01  ·  YOUR GARAGE",
    "Busca un coche por nombre o marca y guárdalo en favoritos. "
    "La previsualización usa la imagen preview de la skin seleccionada; amplíala desde su tarjeta. "
    "Teclado: Ctrl+1 a 9 o Ctrl+Tab cambian de pestaña, Alt+Arriba/Abajo cambian de coche, "
    "Ctrl+L va a la lista y F1 abre esta guía.":
        "Search a car by name or brand and save it as a favourite. The preview uses the preview "
        "image of the selected skin; zoom it from its card. "
        "Keys: Ctrl+1 to 9 or Ctrl+Tab switch tab, Alt+Up/Down switch car, "
        "Ctrl+L goes to the list and F1 opens this guide.",
    "02  ·  AJUSTA CON CRITERIO": "02  ·  TUNE WITH CRITERIA",
    "Motor: consulta los valores leídos de power.lut y edita sus puntos en la tabla. "
    "Caja: ajusta marchas y grupo final. Chasis: prueba muelles, amortiguadores, geometría, "
    "frenos y presiones con sus unidades reales.":
        "Engine: check the values read from power.lut and edit its points in the table. "
        "Gearbox: adjust gears and final drive. Chassis: try springs, dampers, geometry, brakes "
        "and pressures in their real units.",
    "03  ·  PERFILES Y CAMBIOS": "03  ·  PROFILES AND CHANGES",
    "Guarda una configuración como perfil, compara resultados en el resumen y usa "
    "Ctrl+Z / Ctrl+Y para deshacer o rehacer. Nada se escribe en el juego hasta pulsar Guardar.":
        "Save a setup as a profile, compare results in the overview and use Ctrl+Z / Ctrl+Y to "
        "undo or redo. Nothing is written to the game until you press Save.",
    "04  ·  PROTEGE EL ORIGINAL": "04  ·  PROTECT THE ORIGINAL",
    "Antes de guardar crea una copia ZIP y conserva el .bak original y el formato. Los coches con data.acd "
    "requieren extraer data con Content Manager; Quick Mechanic no modifica data.acd.":
        "Before saving it creates a ZIP copy and keeps the original .bak and the file format. "
        "Cars with data.acd need data extracted with Content Manager; Quick Mechanic does not "
        "modify data.acd.",
    "05  ·  COMUNIDAD Y CONTENT MANAGER": "05  ·  COMMUNITY AND CONTENT MANAGER",
    "Abre Discord para encontrar ayuda y novedades. "
    "Content Manager instala o extrae contenido; pulsa Sincronizar coches para refrescar la biblioteca.":
        "Open Discord for help and news. Content Manager installs or extracts content; "
        "press Sync cars to refresh the library.",
    "QUICK START · EDICIÓN SEGURA": "QUICK START · SAFE EDITING",
    "Bienvenido al box": "Welcome to the pit box",
    "Tu centro de ingeniería para Assetto Corsa.": "Your engineering hub for Assetto Corsa.",
    "COMUNIDAD Y AYUDA · EL ENLACE ABRE DISCORD":
        "COMMUNITY AND HELP · THE LINK OPENS DISCORD",
    "Abrir Discord  ↗": "Open Discord  ↗",
    "Visita la comunidad de SuperIraitz para novedades y ayuda":
        "Visit the SuperIraitz community for news and help",
    "Anterior": "Back",
    "Siguiente": "Next",
    "Mostrar al iniciar": "Show on start",
    "Empezar a trabajar": "Start working",
    "Espera a que termine de preparar el coche actual…": "Wait for the current car to finish preparing…",
    "Espera: ya se está preparando otro coche…": "Wait: another car is already being prepared…",
    "Confirma la vinculación en el navegador…": "Confirm the link in your browser…",
    "Opcional: vincula tu cuenta si estás en el servidor SuperIraitz.":
        "Optional: link your account if you are in the SuperIraitz server.",
    "Vincular Discord": "Link Discord",
    "Desvincular": "Unlink",
    "Cancelaste la vinculación en Discord.": "You cancelled the link in Discord.",
    "Tu cuenta no está en el servidor SuperIraitz. Únete al Discord y vuelve a intentarlo.":
        "Your account is not in the SuperIraitz server. Join the Discord and try again.",
    "El servicio de vinculación todavía no está configurado.":
        "The link service is not configured yet.",
    "Se agotó el tiempo de espera. Vuelve a intentarlo.": "The wait timed out. Try again.",
    "Discord no devolvió la autorización.": "Discord did not return the authorization.",
    "Discord no aceptó la autorización. Vuelve a intentarlo.":
        "Discord did not accept the authorization. Try again.",
    "No se pudo contactar con el servicio de vinculación.":
        "Could not reach the link service.",
    # ----------------------------------------------------------- content manager
    "Elegir .exe": "Choose .exe",
    "Abrir CM": "Open CM",
    "Sincronizar coches": "Sync cars",
    "Vuelve a escanear content/cars tras instalar o extraer coches. "
    "No requiere ni simula una API de Content Manager.":
        "Re-scans content/cars after installing or extracting cars. It does not need or fake a "
        "Content Manager API.",
    "Seleccionar Assetto Corsa Content Manager": "Select Assetto Corsa Content Manager",
    "Content Manager (*.exe);;Ejecutables (*.exe)": "Content Manager (*.exe);;Executables (*.exe)",
    "●  DETECTADO": "●  DETECTED",
    "No encontrado · puedes elegir Content Manager.exe": "Not found · you can pick Content Manager.exe",
    "●  SIN CONFIGURAR": "●  NOT CONFIGURED",
    "●  ERROR AL ABRIR": "●  ERROR OPENING",
    # ---------------------------------------------------------------- resumen
    "Coches instalados": "Installed cars",
    "Con data/": "With data/",
    "Con data.acd": "With data.acd",
    "Skins detectadas en la biblioteca": "Skins found in the library",
    "Potencia calculada": "Computed power",
    "Estimación matemática derivada de power.lut, no telemetría de pista":
        "Mathematical estimate from power.lut, not on-track telemetry",
    "Par calculado": "Computed torque",
    "Masa": "Mass",
    "Rel. peso/potencia": "Weight/power ratio",
    "Resumen calculado del motor": "Computed engine summary",
    "Selecciona un coche editable.": "Select an editable car.",
    "Velocidad teórica por marcha": "Theoretical speed per gear",
    "Se calcula con relación, grupo final, radio de rueda y limitador.":
        "Computed from ratio, final drive, wheel radius and limiter.",
    "Comprobaciones del fichero": "File checks",
    "Selecciona un coche editable para ver comprobaciones locales.":
        "Select an editable car to see local checks.",
    "Selecciona un coche editable para revisar las cifras del archivo.":
        "Select an editable car to review the file figures.",
    "Las velocidades teóricas aparecerán aquí; no se muestran gráficas.":
        "Theoretical speeds will appear here; no charts are shown.",
    "No hay relaciones de cambio disponibles.": "No gear ratios available.",
    # ------------------------------------------------------------------- motor
    "MAX_BOOST: multiplicador de par con el turbo lleno (2.0 = par x3)":
        "MAX_BOOST: torque multiplier with the turbo spooled (2.0 = torque x3)",
    "WASTEGATE: nivel maximo antes de que la wastegate corte el boost":
        "WASTEGATE: maximum level before the wastegate cuts the boost",
    "Valor que muestran los displays del cockpit": "Value shown by the cockpit displays",
    "Rpm a las que el turbo alcanza el boost maximo a fondo":
        "Rpm at which the turbo reaches full boost",
    "LAG_UP: 0.99 sube lento, 0.999 sube casi instantaneo":
        "LAG_UP: 0.99 spools slowly, 0.999 spools almost instantly",
    "LAG_DN: lo mismo al soltar el gas": "LAG_DN: same when you lift off",
    "GAMMA: forma de la curva de subida del turbo": "GAMMA: shape of the turbo spool curve",
    "Boost maximo": "Max boost",
    "Wastegate": "Wastegate",
    "Boost del display": "Display boost",
    "Rpm de referencia": "Reference rpm",
    "Lag al subir": "Spool lag",
    "Lag al bajar": "Drop lag",
    "Gamma": "Gamma",
    "Par maximo": "Peak torque",
    "Pico de la curva de par": "Peak of the torque curve",
    "Potencia": "Power",
    "Potencia maxima de la curva": "Peak of the curve",
    "Potencia por tonelada": "Power per tonne",
    "Corte": "Cut-off",
    "LIMITER: vueltas a las que corta": "LIMITER: rpm at which it cuts",
    "LIMITER: revoluciones a las que corta la inyeccion":
        "LIMITER: rpm at which injection cuts",
    "MINIMUM: regimen de ralenti": "MINIMUM: idle rpm",
    "INERTIA: menos inercia = el motor sube de vueltas antes":
        "INERTIA: less inertia = the engine revs up sooner",
    "Limitador": "Limiter",
    "Ralenti": "Idle",
    "Inercia del motor": "Engine inertia",
    "Curva de potencia": "Power curve",
    "Multiplica la curva de par entera antes de guardar power.lut":
        "Multiplies the whole torque curve before saving power.lut",
    "Multiplicador de par": "Torque multiplier",
    "Arrastra para reescalar la curva entera: 100 = curva original (x1.00)":
        "Drag to rescale the whole curve: 100 = original curve (x1.00)",
    "Curva original": "Original curve",
    "Deja el multiplicador en 1.0 sin tocar el fichero":
        "Leaves the multiplier at 1.0 without touching the file",
    "Curva power.lut": "power.lut curve",
    "Los valores se leen directamente de power.lut. Editar el par de un punto cambia solo ese valor; "
    "no hay interpolación ni mediciones de pista.":
        "Values are read straight from power.lut. Editing the torque of a point changes only that "
        "value; there is no interpolation and no on-track measurement.",
    "Ajustable desde el cockpit": "Adjustable from the cockpit",
    "COCKPIT_ADJUSTABLE: permite mover el boost con un mando en pista":
        "COCKPIT_ADJUSTABLE: lets you move the boost with a cockpit control",
    "Quitar turbo (comenta la seccion)": "Remove turbo (comments the section)",
    "Anadir turbo": "Add turbo",
    "Quitar turbo": "Remove turbo",
    "Potencia calculada (CV)": "Computed power (hp)",
    "Coche atmosferico: engine.ini no tiene ninguna seccion [TURBO_n].":
        "Naturally aspirated car: engine.ini has no [TURBO_n] section.",
    "Anadir turbo ([TURBO_0] con valores de Kunos)": "Add turbo ([TURBO_0] with Kunos values)",
    "El turbo no cambia el .lut: multiplica el par en tiempo real por (1 + MAX_BOOST) cuando esta lleno.":
        "The turbo does not change the .lut: it multiplies torque in real time by (1 + MAX_BOOST) "
        "when spooled.",
    # ----------------------------------------------------------------- cambios
    "Marchas": "Gears",
    "COUNT de drivetrain.ini": "COUNT in drivetrain.ini",
    "Grupo final": "Final drive",
    "FINAL: multiplica todas las marchas": "FINAL: multiplies every gear",
    "Punta teorica": "Top speed",
    "Velocidad de la ultima marcha al corte": "Speed in the last gear at the limiter",
    "Traccion": "Drive",
    "TYPE de la seccion [TRACTION]": "TYPE in the [TRACTION] section",
    "COUNT: numero de marchas que usa AC (las claves de mas se ignoran)":
        "COUNT: number of gears AC uses (extra keys are ignored)",
    "COUNT: numero de marchas que usa AC": "COUNT: number of gears AC uses",
    "Numero de marchas": "Number of gears",
    "Marcha atras": "Reverse gear",
    "Diferencial": "Differential",
    "POWER: bloqueo del diferencial al acelerar (0 = abierto)":
        "POWER: differential lock under power (0 = open)",
    "COAST: bloqueo al levantar el pie (mas = mas estable al frenar)":
        "COAST: lock when you lift off (more = more stable under braking)",
    "PRELOAD: par de precarga en Nm": "PRELOAD: preload torque in Nm",
    "Bloqueo en aceleracion": "Lock under power",
    "Bloqueo al retener": "Lock under coast",
    "Precarga": "Preload",
    "Como se comporta": "How it behaves",
    "Relaciones mas cortas (numeros mas altos) = mas aceleracion y menos punta. "
    "El grupo final multiplica todas las marchas a la vez.":
        "Shorter ratios (higher numbers) = more acceleration and less top speed. "
        "The final drive multiplies every gear at once.",
    "Relaciones y punta teórica": "Ratios and theoretical top speed",
    "Velocidad calculada a partir del radio de rueda, relación, grupo final y limitador; "
    "no es una medición en pista.":
        "Speed computed from wheel radius, ratio, final drive and limiter; it is not an on-track "
        "measurement.",
    "El coche no define MAX_TORQUE de embrague.": "The car does not define the clutch MAX_TORQUE.",
    # ------------------------------------------------------------ traccion total
    "Tracción total (AWD)": "All-wheel drive (AWD)",
    "Reparto al eje delantero": "Front axle share",
    "FRONT_SHARE: porcentaje de par que va al eje delantero":
        "FRONT_SHARE: percentage of torque sent to the front axle",
    "Bloqueo del. al acelerar": "Front lock under power",
    "FRONT_DIFF_POWER: bloqueo del diferencial delantero al acelerar (1.0 = 100%)":
        "FRONT_DIFF_POWER: front differential lock under power (1.0 = 100%)",
    "Bloqueo del. al retener": "Front lock under coast",
    "FRONT_DIFF_COAST: bloqueo delantero al levantar el pie":
        "FRONT_DIFF_COAST: front lock when you lift off",
    "Precarga delantera": "Front preload",
    "FRONT_DIFF_PRELOAD: par de precarga del diferencial delantero":
        "FRONT_DIFF_PRELOAD: front differential preload torque",
    "Bloqueo central al acelerar": "Centre lock under power",
    "CENTRE_DIFF_POWER: bloqueo del diferencial central al acelerar":
        "CENTRE_DIFF_POWER: centre differential lock under power",
    "Bloqueo central al retener": "Centre lock under coast",
    "CENTRE_DIFF_COAST: bloqueo central al levantar el pie":
        "CENTRE_DIFF_COAST: centre lock when you lift off",
    "Precarga central": "Centre preload",
    "CENTRE_DIFF_PRELOAD: par de precarga del diferencial central":
        "CENTRE_DIFF_PRELOAD: centre differential preload torque",
    "Rampa del central": "Centre ramp",
    "CENTRE_RAMP_TORQUE: par a partir del cual el central empieza a bloquear (modelo [AWD2])":
        "CENTRE_RAMP_TORQUE: torque at which the centre diff starts locking ([AWD2] model)",
    "Par máximo del central": "Centre max torque",
    "CENTRE_MAX_TORQUE: par maximo que puede transmitir el central (modelo [AWD2])":
        "CENTRE_MAX_TORQUE: maximum torque the centre diff can transfer ([AWD2] model)",
    "Bloqueo tras. al acelerar": "Rear lock under power",
    "REAR_DIFF_POWER: bloqueo del diferencial trasero al acelerar":
        "REAR_DIFF_POWER: rear differential lock under power",
    "Bloqueo tras. al retener": "Rear lock under coast",
    "REAR_DIFF_COAST: bloqueo trasero al levantar el pie":
        "REAR_DIFF_COAST: rear lock when you lift off",
    "Precarga trasera": "Rear preload",
    "REAR_DIFF_PRELOAD: par de precarga del diferencial trasero":
        "REAR_DIFF_PRELOAD: rear differential preload torque",
    # ------------------------------------------------------------------ chasis
    "Peso": "Weight",
    "TOTALMASS de car.ini": "TOTALMASS in car.ini",
    "Frec. delantera": "Front freq.",
    "Frecuencia natural del eje delantero (1.2 Hz calle, 2.5-4 GT)":
        "Natural frequency of the front axle (1.2 Hz road, 2.5-4 GT)",
    "Frec. trasera": "Rear freq.",
    "Muelles y amortiguadores": "Springs and dampers",
    "Delantero": "Front",
    "Trasero": "Rear",
    "Delantera": "Front",
    "Trasera": "Rear",
    "Muelles": "Springs",
    "SPRING_RATE: rigidez del muelle medida en la rueda (AC lo guarda en N/m)":
        "SPRING_RATE: wheel rate (AC stores it in N/m)",
    "Amortiguador compresion": "Bump damper",
    "DAMP_BUMP: frenado de la suspension al comprimirse":
        "DAMP_BUMP: how the suspension is slowed when compressing",
    "Amortiguador extension": "Rebound damper",
    "DAMP_REBOUND: controla como vuelve la suspension":
        "DAMP_REBOUND: controls how the suspension returns",
    "Tope de compresion": "Bump stop",
    "Altura (rod length)": "Ride height (rod length)",
    "ROD_LENGTH: positivo sube el coche, negativo lo baja":
        "ROD_LENGTH: positive raises the car, negative lowers it",
    "Camber estatico": "Static camber",
    "grados": "degrees",
    "Barras estabilizadoras (ARB)": "Anti-roll bars (ARB)",
    "Rigidez": "Stiffness",
    "ARB: barra estabilizadora": "ARB: anti-roll bar",
    "Mas barra en un eje = ese eje pierde agarre antes. Delantera mas dura subvira, "
    "trasera mas dura sobrevira.":
        "More bar on an axle = that axle loses grip sooner. Stiffer front understeers, "
        "stiffer rear oversteers.",
    "Frenos": "Brakes",
    "Par maximo total": "Total max torque",
    "MAX_TORQUE de brakes.ini": "MAX_TORQUE in brakes.ini",
    "Reparto delantero": "Front share",
    "FRONT_SHARE: 0.75 en el fichero = 75% de la frenada delante":
        "FRONT_SHARE: 0.75 in the file = 75% of braking at the front",
    "Freno de mano": "Handbrake",
    "HANDBRAKE_TORQUE (solo lectura)": "HANDBRAKE_TORQUE (read only)",
    "El par total lo reparte el reparto delantero/trasero. Mucho par con poco peso = bloqueos faciles; "
    "el ABS del coche no lo puedes activar desde aqui.":
        "The total torque is split by the front/rear share. Lots of torque with little weight = "
        "easy lock-ups; the car ABS cannot be enabled from here.",
    "Peso, combustible y presiones": "Weight, fuel and pressures",
    "Presion en frio del compuesto delantero principal":
        "Cold pressure of the main front compound",
    "Presion en frio del compuesto trasero principal":
        "Cold pressure of the main rear compound",
    "Masa total": "Total mass",
    "TOTALMASS de car.ini (el coche + piloto)": "TOTALMASS in car.ini (car + driver)",
    "Deposito maximo": "Max fuel",
    "MAX_FUEL de car.ini": "MAX_FUEL in car.ini",
    "Presion delantera": "Front pressure",
    "PRESSURE_STATIC del compuesto delantero principal":
        "PRESSURE_STATIC of the main front compound",
    "Presion trasera": "Rear pressure",
    "PRESSURE_STATIC del compuesto trasero principal":
        "PRESSURE_STATIC of the main rear compound",
    "Analisis del reparto": "Balance analysis",
    "Muelles delanteros": "Front springs",
    "Muelles traseros": "Rear springs",
    "Amortiguador comp. del.": "Front bump damper",
    "Amortiguador comp. tras.": "Rear bump damper",
    "Amortiguador ext. del.": "Front rebound damper",
    "Amortiguador ext. tras.": "Rear rebound damper",
    "ARB delantera": "Front ARB",
    "ARB trasera": "Rear ARB",
    "Camber delantero": "Front camber",
    "Camber trasero": "Rear camber",
    "Reparto de frenada": "Brake bias",
    "El coche no declara rangos en setup.ini para estos valores; se usan los del editor.":
        "The car does not declare setup.ini ranges for these values; the editor ranges are used.",
    "El eje trasero esta mucho mas duro que el delantero: el coche tenderá a sobrevirar en apoyo.":
        "The rear axle is much stiffer than the front: the car will tend to oversteer mid-corner.",
    "Rangos del setup del coche: ": "Car setup ranges: ",
    "El eje delantero esta mas duro: subviraje en apoyo. En traccion delantera es habitual "
    "y ayuda a que el eje motriz trabaje.":
        "The front axle is stiffer: mid-corner understeer. On front-wheel drive that is normal and "
        "helps the driven axle work.",
    "Reparto equilibrado entre los dos ejes.": "Balanced split between both axles.",
    # ------------------------------------------------------------- diagnostico
    "Coche sin datos editables": "Car with no editable data",
    # ------------------------------------------------------------- asistencias
    "Control traccion": "Traction control",
    "Asistencias del vehiculo": "Vehicle aids",
    "Quick Mechanic solo cambia PRESENT y ACTIVE si ya existen en electronics.ini. "
    "No crea soporte de hardware ni modifica data.acd. Guarda los cambios para aplicarlos "
    "al coche en Assetto Corsa.":
        "Quick Mechanic only changes PRESENT and ACTIVE if they already exist in electronics.ini. "
        "It does not create hardware support and does not modify data.acd. Save the changes to "
        "apply them to the car in Assetto Corsa.",
    "ABS · antibloqueo de frenos": "ABS · anti-lock brakes",
    "Este coche lleva ABS": "This car has ABS",
    "ABS activo en pista": "ABS active on track",
    "TC · control de traccion": "TC · traction control",
    "Este coche lleva control de traccion": "This car has traction control",
    "Control de traccion activo en pista": "Traction control active on track",
    "Selecciona un coche con data/ extraida para inspeccionar las asistencias.":
        "Select a car with data/ extracted to inspect the aids.",
    "Compatible": "Compatible",
    "No declarado": "Not declared",
    "El coche no declara una seccion compatible; no se puede activar desde aquí.":
        "The car does not declare a compatible section; it cannot be enabled from here.",
    "Detectado": "Detected",
    "No disponible": "Not available",
    "Este coche no incluye electronics.ini abierto. No se han inventado parámetros; si sus datos "
    "están en data.acd, extráelos con Content Manager y vuelve a sincronizar.":
        "This car has no extracted electronics.ini. No parameters were invented; if the data is "
        "inside data.acd, extract it with Content Manager and sync again.",
    "electronics.ini está presente, pero no declara secciones ABS/TC compatibles con los "
    "interruptores PRESENT/ACTIVE. Se mantiene intacto.":
        "electronics.ini is present but does not declare ABS/TC sections compatible with the "
        "PRESENT/ACTIVE switches. It is left untouched.",
    "Los estados se leen de electronics.ini. El comportamiento final depende del modelo de coche "
    "y de las opciones que Assetto Corsa permita en pista.":
        "The states are read from electronics.ini. The final behaviour depends on the car model "
        "and on the options Assetto Corsa allows on track.",
    # ---------------------------------------------------------------- avanzado
    "Parámetros numéricos detectados": "Numeric parameters detected",
    "Editor para usuarios avanzados: muestra valores físicos escalares que ya existen en los INI "
    "abiertos del coche. No crea claves, no modifica data.acd y no aplica rangos genéricos porque "
    "las escalas varían entre mods. Revisa los cambios y prueba en pista.":
        "Editor for advanced users: shows scalar physics values that already exist in the car's "
        "open INI files. It does not create keys, does not modify data.acd and does not apply "
        "generic ranges because scales vary between mods. Review the changes and test on track.",
    "Filtrar por archivo, sección o clave…": "Filter by file, section or key…",
    "Archivo": "File",
    "Sección": "Section",
    "Parámetro": "Parameter",
    "Valor": "Value",
    # ----------------------------------------------------- idioma
    "Idioma": "Language",
    "Español / English · la app se reinicia al cambiar":
        "Español / English · the app restarts when you switch",
    "IDIOMA / LANGUAGE · se aplica al reiniciar": "LANGUAGE · applied on restart",
    "Idioma cambiado": "Language changed",
    "El idioma se aplica al reiniciar Quick Mechanic para reconstruir la interfaz. "
    "¿Quieres reiniciar ahora?":
        "The language is applied when Quick Mechanic restarts so the interface is rebuilt. "
        "Do you want to restart now?",
    "Idioma guardado · se aplicará al reiniciar la app":
        "Language saved · it will be applied when the app restarts",
    "Abrir instalador": "Open installer",
    "Reintentar descarga": "Retry download",
    "Descarga no disponible": "Download not available",
    "Vuelve a descargar el instalador.": "Download the installer again.",
    "La descarga llegó vacía.": "The download was empty.",
    "No se pudo descargar: ": "Could not download: ",
    "Volver a comprobar": "Check again",
    "Cerrar sesión": "Sign out",
    "Comprueba ahora mismo tu membresía en el servidor de Discord":
        "Check your membership in the Discord server right now",
    "◐ Discord no disponible · se volverá a comprobar":
        "◐ Discord unavailable · will check again",
    "○ Acceso no verificado": "○ Access not verified",
}

#: Mensajes con valores dentro. El numero de ``{}`` debe coincidir en ambos idiomas.
EN_TEMPLATES: dict[str, str] = {
    "Aplicado: {}": "Applied: {}",
    "Coche: {}": "Car: {}",
    "Stage actual: {}": "Current stage: {}",
    "Stage {} aplicado": "Stage {} applied",
    "¿Aplicar {}? Se modificarán los ficheros del coche.": "Apply {}? The car files will be modified.",
    "No se pudo leer el stage: {}": "Could not read the stage: {}",
    "No se pudo leer el RTO: {}": "Could not read the RTO: {}",
    "No se pudo guardar el RTO: {}": "Could not save the RTO: {}",
    "{} guardado": "{} saved",
    "¿Restaurar {} copia(s) .bak?": "Restore {} .bak copy(ies)?",
    "{} fichero(s) restaurados": "{} file(s) restored",
    "Error restaurando {}: {}": "Error restoring {}: {}",
    "Ajustado: {}": "Adjusted: {}",
    "Este coche no declara: {}.": "This car does not declare: {}.",
    "Vinculado como {}. Es opcional: la app funciona igual.":
        "Linked as {}. Optional: the app works the same.",
    "No se pudo iniciar la vinculación: {}": "Could not start the link: {}",
    "No se pudo completar la vinculación ({}).": "Could not complete the link ({}).",
    # ------------------------------------------------------- estado y biblioteca
    "Biblioteca lista · {} coches revisados": "Library ready · {} cars scanned",
    "Biblioteca sincronizada · {} coches revisados": "Library synced · {} cars scanned",
    "No se pudo leer la biblioteca: {}": "Could not read the library: {}",
    "Leyendo fichas de coches… {}/{}": "Reading car cards… {}/{}",
    "Exportados {} coches · {}": "Exported {} cars · {}",
    "{} de {} coches · {} editables · {} favoritos": "{} of {} cars · {} editable · {} favourites",
    "{} de {} coches · {} editables · {} favoritos · filtro: {}":
        "{} of {} cars · {} editable · {} favourites · filter: {}",
    "BOX LISTO · {} COCHES": "PIT BOX READY · {} CARS",
    "FICHAS DE COCHE · {}/{}": "CAR DATA CARDS · {}/{}",
    "{} marchas": "{} gears",
    "{} · sin cambios pendientes": "{} · no pending changes",
    "{} fichero con cambios sin guardar: {}": "{} file with unsaved changes: {}",
    "{} ficheros con cambios sin guardar: {}": "{} files with unsaved changes: {}",
    "Guardar ({})": "Save ({})",
    "Guardado a las {}: {}   ·   respaldo completo y .bak conservados":
        "Saved at {}: {}   ·   full backup and .bak kept",
    "Hay cambios sin guardar en {}: {}": "There are unsaved changes in {}: {}",
    "{} · recargado desde disco": "{} · reloaded from disk",
    "{} al iniciar: {}": "{} on start: {}",
    "Tamaño de interfaz aplicado: {}": "Interface size applied: {}",
    "Perfil guardado: {}": "Profile saved: {}",
    "Perfil eliminado: {}": "Profile deleted: {}",
    "Copiar nombre": "Copy name",
    "Copiar ruta": "Copy path",
    "Quitar de recientes": "Remove from recent",
    "Coche quitado de recientes": "Car removed from recent",
    "Este coche no está en recientes": "This car is not in recent",
    "Assetto Corsa no está configurado": "Assetto Corsa is not set up",
    "Todavía no hay ningún coche abierto en una sesión anterior": "No car opened in a previous session yet",
    "nombre": "name",
    "favoritos primero": "favourites first",
    "editables primero": "editable first",
    "recientes primero": "recent first",
    "Orden: nombre": "Order: name",
    "Orden: favoritos primero": "Order: favourites first",
    "Orden: editables primero": "Order: editable first",
    "Orden: recientes primero": "Order: recent first",
    # ---------------------------------------------------------------- swaps
    "Respaldo creado · {}": "Backup created · {}",
    "Se guardaron data/ y data.acd (si existía):\n{}":
        "data/ and data.acd (if present) were saved:\n{}",
    "Respaldo restaurado · respaldo de seguridad: {}":
        "Backup restored · safety backup: {}",
    "Se creó un respaldo previo para deshacer: {}":
        "A previous backup was created so you can undo this: {}",
    "Donante para {}:": "Donor for {}:",
    "Revisar intercambio · {}": "Review swap · {}",
    "Donante: {}\nDestino: {}\n\nSe reemplazarán: {}\n\n{}\n\nSe creará un ZIP de respaldo "
    "antes de aplicar. El coche donante no se modifica. ¿Continuar?":
        "Donor: {}\nTarget: {}\n\nFiles to replace: {}\n\n{}\n\nA backup ZIP is created "
        "before applying. The donor car is not modified. Continue?",
    "{} aplicado · respaldo: {}": "{} applied · backup: {}",
    "Se actualizó {}.\n\nRespaldo completo: {}\nRevisa el coche en Assetto Corsa antes de compartirlo.":
        "{} has been updated.\n\nFull backup: {}\nCheck the car in Assetto Corsa before sharing it.",
    "Cambios preparados ({}): {}.\n\n{}{}\n\nRevisa en pista y pulsa Guardar todo para escribirlos.":
        "Changes prepared ({}): {}.\n\n{}{}\n\nCheck them on track and press Save all to write them.",
    "\n\nNo aplicados: {}": "\n\nNot applied: {}",
    # ------------------------------------------------------------- turbo motor
    "Turbo ({})": "Turbo ({})",
    "Con el turbo lleno: ~{} Nm y ~{} CV a {} rpm (la curva de abajo es la del motor sin boost).":
        "With the turbo spooled: ~{} Nm and ~{} hp at {} rpm (the curve below is the engine without boost).",
    "Atencion: MAX_BOOST {} supera el umbral de dano del motor ({}). El turbo se rompera en pista.":
        "Warning: MAX_BOOST {} exceeds the engine damage threshold ({}). The turbo will break on track.",
    "No se ha encontrado {} en la carpeta data del coche.":
        "{} was not found in the car's data folder.",
    "{}: {} puntos, {}-{} rpm": "{}: {} points, {}-{} rpm",
    "{}: {} puntos, {}-{} rpm · curva escalada x{}":
        "{}: {} points, {}-{} rpm · scaled curve x{}",
    "  ·  curva escalada x{}": "  ·  scaled curve x{}",
    "Par maximo {} Nm a {} rpm  ·  potencia {} CV a {} rpm":
        "Peak torque {} Nm at {} rpm  ·  power {} hp at {} rpm",
    "{} CV por tonelada  ·  {} kg/CV ({} kg)": "{} hp per tonne  ·  {} kg/hp ({} kg)",
    "Pico de par leído: {} Nm a {} rpm\nPotencia calculada desde par y rpm: {} CV a {} rpm\n"
    "Limitador configurado: {} rpm · masa: {} kg\n\nSon cálculos a partir de los archivos "
    "del coche; no son datos medidos en pista.":
        "Peak torque read: {} Nm at {} rpm\nPower computed from torque and rpm: {} hp at {} rpm\n"
        "Configured limiter: {} rpm · mass: {} kg\n\nThese are calculations from the car's "
        "files; they are not data measured on track.",
    # --------------------------------------------------------------- cambios
    "Traccion {} · neumatico motriz de {} mm de radio":
        "Drive {} · driven tyre radius {} mm",
    "{}ª: {} km/h": "Gear {}: {} km/h",
    "{}a: {} km/h": "Gear {}: {} km/h",
    "Par maximo del embrague: {} Nm": "Clutch max torque: {} Nm",
    "ratios.rto: este coche trae un gearset con {} relaciones. El setup elige entre ellas; "
    "aqui se edita la relacion de serie.":
        "ratios.rto: this car ships a gearset with {} ratios. The setup picks between them; "
        "here you edit the stock ratio.",
    "A {} rpm · grupo final {} · relaciones {} {}":
        "At {} rpm · final drive {} · ratios {} {}",
    "A {} rpm · grupo final {} · relaciones {}": "At {} rpm · final drive {} · ratios {}",
    # --------------------------------------------------------------- chasis
    "Reparto de frenada: {}% delante ({} Nm totales)":
        "Brake bias: {}% front ({} Nm total)",
    # ------------------------------------------------------------ traccion total
    "{} · solo se editan los parametros que este coche ya trae en drivetrain.ini.":
        "{} · only the parameters this car already has in drivetrain.ini are edited.",
    "Este coche declara traccion total, pero drivetrain.ini no trae los parametros "
    "[AWD]/[AWD2]. Para no romper la fisica no se crean claves nuevas.":
        "This car declares all-wheel drive, but drivetrain.ini does not include the "
        "[AWD]/[AWD2] parameters. No new keys are created, to avoid breaking the physics.",
    "{}% al eje delantero": "{}% to the front axle",
    "rampa central {} Nm": "centre ramp {} Nm",
    "par máximo central {} Nm": "centre max torque {} Nm",
    # ----------------------------------------------------- idioma
    "Versión nueva {}. El aviso se queda aquí hasta que lo cierres.":
        "New version {}. The notice stays here until you close it.",
    "Descarga {} a tu carpeta de descargas; no lo ejecuta solo":
        "Downloads {} to your downloads folder; it is not run automatically",
    "Abre {} solo cuando pulses aquí": "Opens {} only when you press here",
    "Descargado en {}. Ciérralo desde este aviso cuando lo hayas usado.":
        "Downloaded to {}. Close it from this notice once you have used it.",
    "No se pudo descargar: {}": "Could not download: {}",
    "Tipo de archivo no permitido: {}": "File type not allowed: {}",
    "No se pudo crear la carpeta de descargas: {}":
        "Could not create the downloads folder: {}",
    "Descarga incompleta ({} de {} bytes).": "Incomplete download ({} of {} bytes).",
    "No se pudo guardar el archivo: {}": "Could not save the file: {}",
    "El ZIP trae demasiados archivos.": "The ZIP contains too many files.",
    "El ZIP es demasiado grande para extraerlo.": "The ZIP is too large to extract.",
    "No se pudo abrir el ZIP: {}": "Could not open the ZIP: {}",
    "Abrir carpeta de descargas": "Open downloads folder",
    "Abre la carpeta donde quedó {}": "Opens the folder where {} was saved",
    "Con {} kg y {} CV: {} CV/t · {} kg/CV":
        "With {} kg and {} hp: {} hp/t · {} kg/hp",
    "Masa {} kg · {} CV/t · presiones {}/{} PSI en frio":
        "Mass {} kg · {} hp/t · cold pressures {}/{} PSI",
    "Reparto de muelles: {}% delante / {}% detras":
        "Spring split: {}% front / {}% rear",
    "Frecuencia natural: {} Hz delante · {} Hz detras (un turismo de calle va sobre 1.2 Hz; "
    "un GT de carreras, 2.5-4)":
        "Natural frequency: {} Hz front · {} Hz rear (a road car sits near 1.2 Hz; "
        "a racing GT, 2.5-4)",
}
