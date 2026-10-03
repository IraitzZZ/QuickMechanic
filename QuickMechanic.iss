#define AppName "Quick Mechanic"
#define AppVersion "0.2.0"
; IMPORTANTE: actualizar AppVersion a la vez que quickmechanic/**init**.py.
#define AppExeName "QuickMechanic.exe"
#define DiscordURL "https://discord.com/invite/pWE5yEKexW"

[Setup]
AppId={{E6902A03-45A4-4CF1-9A2B-2D6942B87218}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=SuperIraitz
DefaultDirName={userpf}\QuickMechanic
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Setup
SetupIconFile=icono.ico
Uninstallable=yes
UninstallDisplayIcon={app}\QuickMechanic.exe
AppMutex=QuickMechanic
CloseApplications=yes
CloseApplicationsFilter=QuickMechanic.exe
RestartApplications=no
UsePreviousAppDir=yes
DisableReadyPage=no
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Messages]
WelcomeLabel1=¡Bienvenido a {#AppName}!
WelcomeLabel2=La herramienta definitiva de ingeniería de vehículos y gestión de swaps para Assetto Corsa.%n%nHaga clic en Siguiente para revisar las condiciones de uso e instalar el programa.
FinishedHeadingLabel=¡Instalación completada!
FinishedLabel={#AppName} se ha instalado correctamente en tu sistema. ¡Prepárate para una experiencia increíble!

[Dirs]
Name: "{app}"; Flags: uninsalwaysuninstall
Name: "{userappdata}\QuickMechanic"; Flags: uninsneveruninstall

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\QuickMechanic.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Quick Mechanic"; Filename: "{app}\QuickMechanic.exe"
Name: "{userdesktop}\Quick Mechanic"; Filename: "{app}\QuickMechanic.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickMechanic.exe"; Description: "Abrir {#AppName}"; Flags: postinstall nowait skipifsilent
Filename: "{#DiscordURL}"; Description: "Unirse a la comunidad en Discord"; Flags: postinstall shellexec unchecked skipifsilent

[Code]
const
DISCORD_URL = 'https://discord.com/invite/pWE5yEKexW';

var
LicensePage: TOutputMsgMemoWizardPage;
DiscordPanel: TPanel;
ColorBg: TColor;
ColorPanel: TColor;
ColorGold: TColor;
ColorWhite: TColor;
ColorDiscord: TColor;

procedure InitColors();
begin
ColorBg := $FFFFFF;       // fondo blanco
ColorPanel := $FFFFFF;    // panel blanco
ColorGold := $000000;     // negro
ColorWhite := $000000;    // negro
ColorDiscord := $FFFFFF;  // blanco
end;

procedure ApplyTheme(Control: TControl);
var
I: Integer;
WinControl: TWinControl;
begin
if Control is TLabel then
begin
TLabel(Control).Transparent := True;
if fsBold in TLabel(Control).Font.Style then
TLabel(Control).Font.Color := ColorGold
else
TLabel(Control).Font.Color := ColorWhite;
end
else if Control is TNewCheckListBox then
begin
TNewCheckListBox(Control).Color := ColorPanel;
TNewCheckListBox(Control).Font.Color := ColorWhite;
end
else if Control is TNewMemo then
begin
TNewMemo(Control).Color := ColorPanel;
TNewMemo(Control).Font.Color := ColorWhite;
end
else if Control is TRichEditViewer then
begin
TRichEditViewer(Control).Color := ColorPanel;
TRichEditViewer(Control).Font.Color := ColorWhite;
end;

if Control is TWinControl then
begin
WinControl := TWinControl(Control);
for I := 0 to WinControl.ControlCount - 1 do
ApplyTheme(WinControl.Controls[I]);
end;
end;

procedure DiscordPanelClick(Sender: TObject);
var
ErrorCode: Integer;
begin
if not ShellExec('open', DISCORD_URL, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode) then
MsgBox('No se pudo abrir el navegador. Visita: ' + DISCORD_URL, mbError, MB_OK);
end;

procedure InitializeWizard();
var
LicenseText: String;
DiscordLabel: TLabel;
begin
InitColors();

LicenseText :=
'QUICK MECHANIC - CONDICIONES Y AVISO DE RESPONSABILIDAD' + #13#10 +
'------------------------------------------------------------------' + #13#10 + #13#10 +
'1. DESCRIPCIÓN DEL SOFTWARE:' + #13#10 +
'   Quick Mechanic es una herramienta de ingeniería de vehículos y' + #13#10 +
'   gestión de swaps para Assetto Corsa desarrollada por SuperIraitz.' + #13#10 + #13#10 +
'2. COPIAS DE SEGURIDAD AUTOMÁTICAS:' + #13#10 +
'   El software realiza copias de seguridad automáticas (.zip) de los' + #13#10 +
'   archivos modificados antes de aplicar cualquier cambio en tus mods.' + #13#10 + #13#10 +
'3. RESPONSABILIDAD DEL USUARIO:' + #13#10 +
'   Úsalo bajo tu propia responsabilidad. Verifica siempre la integridad' + #13#10 +
'   de los archivos de tus vehículos antes de utilizarlos en servidores.' + #13#10 + #13#10 +
'4. COMUNIDAD Y SOPORTE:' + #13#10 +
'   Únete a nuestra comunidad oficial en Discord para recibir soporte,' + #13#10 +
'   compartir mejoras y enterarte de las últimas novedades:' + #13#10 +
'   ' + DISCORD_URL + #13#10 + #13#10 +
'¡Gracias por confiar en Quick Mechanic!';

LicensePage := CreateOutputMsgMemoPage(
wpWelcome,
'Términos de Uso y Responsabilidad',
'Por favor, lee con atención las siguientes condiciones antes de continuar:',
'Aviso legal y de seguridad:',
LicenseText
);

WizardForm.MainPanel.Color := ColorBg;
WizardForm.InnerPage.Color := ColorBg;
WizardForm.Font.Color := ColorWhite;

// Botón de Discord: fondo blanco con texto negro
DiscordPanel := TPanel.Create(WizardForm);
DiscordPanel.Parent := WizardForm;
DiscordPanel.Left := ScaleX(20);
DiscordPanel.Top := WizardForm.CancelButton.Top;
DiscordPanel.Width := ScaleX(150);
DiscordPanel.Height := WizardForm.CancelButton.Height;
DiscordPanel.BevelOuter := bvNone;
DiscordPanel.Color := ColorDiscord;
DiscordPanel.Cursor := crHand;
DiscordPanel.OnClick := @DiscordPanelClick;

DiscordLabel := TLabel.Create(WizardForm);
DiscordLabel.Parent := DiscordPanel;
DiscordLabel.Caption := 'Comunidad Discord';
DiscordLabel.Font.Color := ColorWhite;
DiscordLabel.Font.Style := [fsBold];
DiscordLabel.Transparent := True;
DiscordLabel.Cursor := crHand;
DiscordLabel.OnClick := @DiscordPanelClick;
DiscordLabel.Left := ScaleX(10);
DiscordLabel.Top := (DiscordPanel.Height - DiscordLabel.Height) div 2;

ApplyTheme(WizardForm);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
ApplyTheme(WizardForm);
WizardForm.Font.Color := ColorWhite;
end;
