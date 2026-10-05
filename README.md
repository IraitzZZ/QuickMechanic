# Quick Mechanic — editor de coches para Assetto Corsa

Herramienta de escritorio para ajustar los coches de Assetto Corsa sin abrir un
editor de texto: motor y turbo, puntos editables de `power.lut`, caja de cambios,
chasis con unidades reales (N/mm, N·s/mm, Nm, PSI), editor experto y diagnostico.
La interfaz ya no muestra graficos: las cifras del resumen se identifican como
calculadas desde los archivos y no como telemetria de pista.

La interfaz esta disponible en **español e ingles** (boton **Idioma**): el idioma
se guarda en `%APPDATA%\QuickMechanic` y se aplica al reiniciar la app.

La interfaz usa una paleta premium fija de negro grafito, gris tecnico y oro
satinado, con navegacion lateral animada, splash de carga, guia de bienvenida y
ayuda contextual. El icono `icono.ico` de la raiz se integra en la ventana,
cabecera, splash y ejecutable; si falta, se dibuja un emblema QM vectorial. A la
izquierda hay busqueda, favoritos y **previsualizacion del coche** (la imagen `preview` de
cada skin); el area de trabajo agrupa resumen, motor, caja de cambios, chasis,
asistencias y diagnostico. Los coches con fisica dentro de `data.acd` tambien
enseñan su foto aunque no se puedan editar sus .ini.

La tarjeta de Content Manager detecta su ejecutable (incluida la ruta
`C:\\latest\\Content Manager.exe`), permite abrirlo o elegir otra ubicacion y
sincroniza la biblioteca local al volver a Quick Mechanic. Es una integracion
local de lanzamiento/escaneo: Content Manager no expone una API publica estable
para editar la fisica en directo.

## Capturas

En `docs/capturas.html` hay una galeria con las cuatro pestanas (las imagenes
van embebidas, asi que es un unico fichero que se abre en cualquier navegador).
Se regenera con:

```
python tools/capturas.py --car 350z_tea_hair
```

## Requisitos

- Windows
- Python 3.11 o superior (probado con 3.14)
- Assetto Corsa instalado (se detecta solo, tambien puedes indicar la carpeta a mano)

## Uso rapido

```
pip install -r requirements.txt
python -m quickmechanic
```

O doble clic en `run.bat`.

## Compilar el .exe y el instalador

Primero ejecuta `build_exe.bat`, que genera el ejecutable portable `dist\QuickMechanic.exe`.
Para obtener además el instalador separado `dist\Setup.exe`, instala **Inno Setup 6**
y ejecuta `build_installer.bat` (configurado en [QuickMechanic.iss](QuickMechanic.iss)).
El instalador es por usuario, reemplaza los archivos de aplicación al actualizar y no
instala ni elimina `%APPDATA%\QuickMechanic`, donde se guardan perfiles y preferencias.

Si `icono.ico` esta en la raiz, se usa como icono de Windows y se incluye dentro del
archivo ejecutable; si no, la aplicacion conserva su emblema QM de reserva. El .exe
tambien sabe autocomprobarse:

```
dist\QuickMechanic.exe --selftest --report informe.txt
```

## Que hace

| Pestana | Que se puede tocar |
|---|---|
| **Motor** | Limitador, ralenti, inercia, turbo completo (MAX_BOOST, wastegate, lag, gamma...), añadir/quitar turbo, multiplicador y edición de cada punto de par de `power.lut` |
| **Cambios** | Número de marchas, cada relación, marcha atrás, grupo final, diferencial (bloqueo y precarga); velocidades teóricas en tabla, sin gráficas |
| **Chasis** | Muelles (N/mm), amortiguadores (N·s/mm), topes, altura, camber, barras estabilizadoras (Nm), frenos (Nm y reparto %) y peso/deposito |
| **Asistencias** | Lee y permite cambiar ABS/TC solo cuando el coche declara `PRESENT` y `ACTIVE` en `electronics.ini`; nunca inventa soporte ni toca `data.acd` |
| **Diagnostico** | Ficha del coche, avisos (dano por boost, limite de rpm, ficheros que faltan...) y estado de los ficheros |
| **Avanzado** | Tabla filtrable de parámetros físicos numéricos ya existentes en los INI, para editar sin inventar claves |
| **Perfiles** | Incluye un preset orientativo de drift que adapta cambios a RWD/AWD y solo toca parámetros existentes; requiere revisión en pista |
| **Content Manager** | Detecta/abre el ejecutable configurado y permite resincronizar `content/cars` tras instalar o extraer contenido |
| **Swaps** | Previsualiza y transfiere motor (engine.ini + curvas enlazadas), sonido (sfx.ini + bancos/GUIDs declarados), transmisión compatible y geometría básica de suspensión. El sonido puede aplicarse a coches que solo tengan `data.acd`; el donante no se modifica. La caja bloquea tracciones distintas. |
| **Respaldos** | Antes de cada guardado, swap o restauración crea ZIP timestamped de `data/`, `data.acd` y, en swaps de audio, los sonidos del destino. Incluye botón de restauración. |
| **Tracción total (AWD)** | Cuando el coche declara `[AWD]`/`[AWD2]`, la pestaña Cambios muestra el reparto al eje delantero (`FRONT_SHARE`) y los diferenciales delantero, central y trasero (bloqueo al acelerar/retener y precarga); en el modelo `[AWD2]` también la rampa y el par máximo del central. Solo se editan claves que el coche ya trae. |

Los rangos de los controles de chasis salen del propio `setup.ini` del coche
cuando los declara, asi que nunca se sale de lo que el setup del juego acepta.

Arriba de cada pestana estan los numeros que importan (par y potencia maximos,
relacion peso/potencia, corte, velocidades por marcha, frecuencias de la
suspension...), para ver el efecto de lo que tocas sin cambiar de pestana. Los
deslizadores de puesta a punto ofrecen control fino, y la foto admite zoom y
apertura ampliada; la skin elegida se recuerda por coche. La curva ahora se edita
por puntos en una tabla; sus cifras son cálculos desde archivos, no datos medidos
en pista. La escala de interfaz se ajusta desde el boton Interfaz.

En el primer arranque se abre una guia interactiva de cinco pasos sobre
biblioteca, ajustes, perfiles, copias de seguridad y Content Manager. Incluye un
acceso directo a la comunidad de Discord de SuperIraitz (`https://discord.gg/pWE5yEKexW`),
tambien disponible en la franja de bienvenida. Cada inicio normal muestra un aviso
no modal durante 9 segundos, cerrable con ×. El enlace abre la comunidad en el
navegador; Quick Mechanic no instala actualizaciones desde Discord. Se puede volver
a abrir la guia desde **Guia**. En **Interfaz** se cambian el tamaño,
la visibilidad de la guia y el splash al inicio; en Windows, cerrar la ventana
la deja en el area de notificacion (si esta disponible), desde donde se restaura
con un clic. **Salir completamente** cierra la aplicacion y conserva la
confirmacion de cambios sin guardar. Si no existe bandeja, cerrar sale de forma
normal. La lectura inicial de coches y fichas se ejecuta en segundo plano con
progreso, filtros por favoritos/editables y exportacion CSV de los coches
visibles (`Ctrl+E`). El botón **INFO** muestra los créditos y la licencia
CC BY-NC-SA 4.0 indicada por SuperIraitz. El tema permanece fijo para mantener
la identidad.

## Como trata los archivos

- Antes de guardar ediciones o aplicar swaps se crea `quickmechanic_backups/data_backup_*.zip`
  con `data/` y `data.acd` si existe; para intercambios de sonido también incluye
  bancos/GUIDs del destino. Restaurar acepta solo extensiones locales conocidas, no elimina
  archivos ajenos y crea otro ZIP de seguridad antes de restaurar.
- **Nunca reescribe el archivo entero** en una edición normal: cambia la línea
  correspondiente y conserva comentarios, orden y formato del `.ini` original.
- Cada fichero conserva además su `.bak` original (solo se crea la primera vez).
  Los swaps preparan los archivos nuevos en temporales antes del reemplazo atómico.
- Para restaurar respaldos, abre **Swaps → Restaurar copia de seguridad**.
- Los coches con física solo dentro de `data.acd` no se pueden editar ni usar como
  donantes de física: hay que extraer `data/` (Content Manager → botón derecho →
  Data → Unpack) o usar *Abrir data*. El archivo `data.acd` nunca se modifica, pero
  sí se conserva intacto en los respaldos.
- El swap de transmisión rechaza tipos de tracción distintos; el motor no cambia
  caja/masa/chasis y no puede garantizar compatibilidad mecánica; fitment solo toca
  geometría básica. El audio requiere `sfx.ini` y todos los bancos/GUIDs declarados;
  no combina bancos FMOD ni toca archivos globales. No se inyectan claves supuestas
  de launch control/DRS ni se empaqueta/desempaqueta `data.acd`.

## Estructura

```
quickmechanic/
  ac_scanner.py    encuentra Assetto Corsa y lista los coches
  ini_editor.py    lectura/escritura de .ini manteniendo el formato original
  lut.py           curvas .lut (power.lut...) y catalogos .rto (gearsets)
  skins.py         skins, imagen de previsualizacion y ficha (ui_car.json)
  car_data.py      capa de datos del coche con unidades reales
  content_manager.py deteccion y apertura local de Content Manager
  cm_panel.py      panel de estado, seleccion y sincronizacion de biblioteca
  units.py         conversiones y fisica (N/mm, CV, km/h, frecuencias...)
  theme.py         paleta y hoja de estilo (estetica racing)
  i18n.py          motor de traduccion (español base -> ingles) y cobertura
  locales.py       tabla de traducciones y lista de identificadores ignorados
  qt_i18n.py       widgets de Qt que traducen el texto que reciben
  updates.py       comprobacion de versiones en GitHub Releases y descarga
  widgets.py       piezas de interfaz compartidas (paneles, tiles, preview)
  tabs/            pestanas de la interfaz
  main.py          ventana principal
  startup.py       inicio opcional de Windows y bandeja
  license.py       créditos y licencia del diálogo INFO
  selftest.py      autotest (--selftest)
tests/             tests unitarios + tests contra la instalacion real
tools/capturas.py  genera docs/*.png y docs/capturas.html
launcher.py        punto de entrada para PyInstaller
```

## Idioma (Español / English)

El español es el idioma base: el texto del codigo es la clave de traduccion y
`quickmechanic/locales.py` guarda su version inglesa (frases completas, mensajes
con valores y los titulos en mayusculas de las tarjetas). `quickmechanic/qt_i18n.py`
entrega a Qt los widgets ya traducidos, asi que ninguna etiqueta se queda por
traducir por un despiste, y `quickmechanic/i18n.py` hace de motor.

- Boton **Idioma** en la cabecera: guarda la preferencia y ofrece reiniciar la app
  para reconstruir la interfaz con el idioma nuevo (no hay que reinstalar nada).
- Si falta una traduccion se muestra el texto en español: nunca aparecen claves.
- `python -m quickmechanic.i18n` lista lo que queda sin traducir y
  `tests/test_i18n.py` falla si aparece texto nuevo sin traducir en la interfaz.

## Actualizaciones

Al abrir la app (y tambien desde **Interfaz → Buscar actualizaciones ahora**) se
consulta la ultima release publicada de GitHub:

```
GET https://api.github.com/repos/IraitzZZ/QuickMechanic/releases/latest
```

- Si el `tag_name` es mas nuevo que la version instalada, aparece un aviso
  persistente arriba con **Descargar e instalar**, **Ver en GitHub** y una × para
  cerrarlo. El aviso no desaparece solo: se queda hasta que lo cierres.
- **Descargar** baja el `Setup.exe` (o el `.zip`) a
  `%APPDATA%\QuickMechanic\updates` en segundo plano. **Nunca se ejecuta nada
  solo**: el instalador se abre unicamente cuando pulsas **Abrir instalador**.
- Si la descarga falla, el aviso se queda con el error y un boton para reintentar.
- Sin internet, con 404 (repositorio privado o sin releases) o con un JSON raro
  la comprobacion no molesta: se ignora en silencio y la app funciona normal. Si
  la pediste a mano, el pie de la ventana te dice que no se pudo consultar.
- Se puede desactivar en **Interfaz → Comprobar actualizaciones al iniciar**. La
  version descartada se recuerda para no insistir con la misma release.

Nota: `https://github.com/IraitzZZ/QuickMechanic/releases/latest` debe existir y
ser publico para que el aviso llegue a los usuarios. Si publicas la version que
ya tienes instalada (por ejemplo `v0.2.0` con la app en `0.2.0`), no se ofrece
nada: se avisa cuando el tag sea superior (por ejemplo `v0.2.1`).

## Tests

```
python -m unittest discover -s tests -v
```

Los tests de `tests/test_real_install.py` y `tests/test_skins.py` solo leen tu
instalacion de AC; el unico que escribe lo hace sobre una copia temporal. Si no
hay AC instalado, se saltan solos. Los tests de interfaz se ejecutan en modo sin
pantalla (`QT_QPA_PLATFORM=offscreen`) y no tocan tu configuracion.

### Como trata las skins

AC guarda una carpeta por skin en `content/cars/<coche>/skins/<Skin>/` con una
imagen llamada `preview` dentro (casi siempre `preview.jpg`, algunos mods usan
`preview.png`). Quick Mechanic busca en este orden: `preview.jpg`, `preview.png`,
cualquier otro `preview*` que sea imagen (ignorando copias como
`preview_original.jpg`) y, si la skin no trae ninguna, la `preview` suelta de la
raiz del coche. Cuando no hay nada, pinta un marcador con el monograma del coche
en vez de dejar el hueco vacio. El nombre de la skin y el equipo/dorsal salen de
`ui_skin.json`; la marca, clase y especificaciones, de `ui/ui_car.json`.
