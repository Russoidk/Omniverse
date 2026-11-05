const { app, BrowserWindow, shell, dialog } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const net = require('node:net');
const http = require('node:http');

const ROOT = path.resolve(__dirname);
const HOST = '127.0.0.1';
const PORT = 8000;
const BASE_URL = `http://${HOST}:${PORT}`;
const APP_PROTOCOL = 'omniverse';
let djangoProcess = null;
let mainWindow = null;
let startupWindow = null;
let ownsServer = false;
let pendingFocus = false;
let startupLogPath = null;

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) app.quit();

function focusMainWindow() {
  if (!mainWindow) {
    pendingFocus = true;
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  pendingFocus = false;
}

function logLine(text) {
  const line = `[${new Date().toISOString()}] ${String(text)}\r\n`;
  try {
    if (startupLogPath) fs.appendFileSync(startupLogPath, line, 'utf8');
  } catch (_) { /* el registro no debe impedir el arranque */ }
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    logLine(`Ejecutando: ${command} ${args.join(' ')}`);
    const child = spawn(command, args, {
      cwd: options.cwd || ROOT,
      env: options.env || process.env,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    });
    let output = '';
    const addOutput = (chunk) => {
      const value = chunk.toString();
      output = (output + value).slice(-30000);
      logLine(value.trimEnd());
    };
    child.stdout.on('data', addOutput);
    child.stderr.on('data', addOutput);
    child.once('error', (error) => reject(new Error(`${error.message}\n${output}`)));
    child.once('close', (code) => {
      if (code === 0) resolve(output);
      else reject(new Error(`El comando terminó con código ${code}.\n${output}`));
    });
  });
}

function findPythonLauncher() {
  // Se acepta Python 3.12 o posterior. Un Python antiguo no debe causar un fallo
  // tardío al instalar una versión de Django que ya no lo admite.
  const candidates = [
    { command: 'py.exe', prefix: ['-3'] },
    { command: 'py', prefix: ['-3'] },
    { command: 'python.exe', prefix: [] },
    { command: 'python', prefix: [] }
  ];
  for (const candidate of candidates) {
    const result = spawnSync(candidate.command, [...candidate.prefix, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
      encoding: 'utf8', windowsHide: true, timeout: 8000
    });
    if (!result.error && result.status === 0) {
      const versionText = (result.stdout || '').trim();
      const match = versionText.match(/^(\d+)\.(\d+)/);
      if (match && (Number(match[1]) === 3 && Number(match[2]) >= 12 && Number(match[2]) <= 14)) {
        logLine(`Python ${versionText} detectado con ${candidate.command}.`);
        return candidate;
      }
      logLine(`Se omite ${candidate.command}: Python ${versionText || 'de versión desconocida'} es anterior a 3.12.`);
    }
  }
  return null;
}

async function ensurePythonLauncher() {
  const installed = findPythonLauncher();
  if (installed) return installed;

  // El instalador oficial de Python se incluye dentro del instalador Omniverse.
  // Se instala silenciosamente y solo para este usuario, sin modificar el PATH global.
  const packagedInstaller = path.join(process.resourcesPath, 'python-installer.exe');
  const developmentInstaller = path.join(ROOT, 'build', 'python-3.14.10-amd64.exe');
  const installerPath = fs.existsSync(packagedInstaller) ? packagedInstaller : developmentInstaller;
  if (!fs.existsSync(installerPath)) {
    throw new Error('No se encontró Python 3.12 o posterior ni el instalador incluido. Vuelve a descargar el instalador completo de Omniverse.');
  }

  const pythonHome = path.join(app.getPath('userData'), 'python-runtime');
  const bundledPython = path.join(pythonHome, 'python.exe');
  if (!fs.existsSync(bundledPython)) {
    logLine('No hay Python adecuado instalado. Se instalará la versión privada incluida en Omniverse.');
    fs.mkdirSync(pythonHome, { recursive: true });
    try {
      await runCommand(installerPath, [
        '/quiet',
        'InstallAllUsers=0',
        `TargetDir=${pythonHome}`,
        'Include_pip=1',
        'Include_test=0',
        'PrependPath=0',
        'Include_launcher=0',
        'InstallLauncherAllUsers=0',
        'Shortcuts=0'
      ], { cwd: pythonHome });
    } catch (error) {
      throw new Error(`No se pudo instalar Python automáticamente.\n${error.message}`);
    }
  }
  if (!fs.existsSync(bundledPython)) {
    throw new Error('El instalador terminó, pero no se encontró python.exe en la carpeta local de Omniverse.');
  }
  return { command: bundledPython, prefix: [] };
}

async function isOmniverseRunningOnPort() {
  return new Promise((resolve) => {
    const req = http.get(`${BASE_URL}/iniciar-sesion/`, { timeout: 1500 }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { body += chunk; if (body.length > 50000) req.destroy(); });
      res.on('end', () => resolve(res.statusCode >= 200 && res.statusCode < 400 && /omniverse/i.test(body)));
    });
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.on('error', () => resolve(false));
  });
}

function portIsOpen() {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: HOST, port: PORT });
    socket.setTimeout(700);
    socket.once('connect', () => { socket.destroy(); resolve(true); });
    socket.once('timeout', () => { socket.destroy(); resolve(false); });
    socket.once('error', () => resolve(false));
  });
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function prepareDjango() {
  const userData = app.getPath('userData');
  const runtimeDir = path.join(userData, 'runtime');
  const venvDir = path.join(runtimeDir, 'venv');
  const venvPython = path.join(venvDir, 'Scripts', 'python.exe');
  const requirementsFile = path.join(ROOT, 'requirements.txt');
  const markerFile = path.join(runtimeDir, 'requirements.sha256');
  const dataDir = path.join(userData, 'data');
  startupLogPath = path.join(userData, 'omniverse-startup.log');
  fs.mkdirSync(runtimeDir, { recursive: true });
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(path.join(dataDir, 'media'), { recursive: true });
  logLine('Preparando la aplicación.');

  // En la edición para exposición se incluye un mundo de demostración listo para usar.
  // Solo se copia cuando todavía no existe una base de datos del usuario; nunca se
  // reemplaza una base existente durante una actualización.
  const legacyDatabase = path.join(ROOT, 'db.sqlite3');
  const demoDatabase = path.join(ROOT, 'demo-data', 'omniverse-demo.sqlite3');
  const targetDatabase = path.join(dataDir, 'db.sqlite3');
  if (!fs.existsSync(targetDatabase)) {
    if (fs.existsSync(demoDatabase)) {
      fs.copyFileSync(demoDatabase, targetDatabase);
      logLine('Se instaló la base de datos de demostración en una carpeta de datos nueva.');
    } else if (fs.existsSync(legacyDatabase)) {
      fs.copyFileSync(legacyDatabase, targetDatabase);
      logLine('Se copió la base de datos local de la versión anterior.');
    }
  }
  const legacyMedia = path.join(ROOT, 'media');
  const targetMedia = path.join(dataDir, 'media');
  if (fs.existsSync(legacyMedia)) {
    try {
      fs.cpSync(legacyMedia, targetMedia, { recursive: true, force: false, errorOnExist: false });
    } catch (error) {
      logLine(`No se pudo copiar parte de la carpeta media anterior: ${error.message}`);
    }
  }

  if (!fs.existsSync(requirementsFile)) {
    throw new Error('No se encontró requirements.txt. Reinstala Omniverse desde el instalador corregido.');
  }

  const expectedHash = crypto.createHash('sha256').update(fs.readFileSync(requirementsFile)).digest('hex');
  const env = { ...process.env, OMNIVERSE_DATA_DIR: dataDir, PYTHONUNBUFFERED: '1' };
  let pythonOk = false;
  if (fs.existsSync(venvPython)) {
    try {
      await runCommand(venvPython, ['-c', 'import django; import PIL; import reportlab'], { cwd: ROOT, env });
      pythonOk = true;
    } catch (error) {
      // Recuperación automática de los entornos incompletos o copiados desde otro PC.
      logLine(`El entorno de Python existente no es válido y se volverá a crear: ${error.message}`);
      fs.rmSync(venvDir, { recursive: true, force: true });
    }
  }

  if (!pythonOk) {
    const launcher = await ensurePythonLauncher();
    try {
      await runCommand(launcher.command, [...launcher.prefix, '-m', 'venv', venvDir], { cwd: ROOT, env });
    } catch (error) {
      throw new Error(`No se pudo crear el entorno de Python automáticamente.\n${error.message}`);
    }
    if (!fs.existsSync(venvPython)) {
      throw new Error('Python no creó el entorno virtual esperado. Consulta el registro de inicio para ver el detalle.');
    }
  }

  const installedHash = fs.existsSync(markerFile) ? fs.readFileSync(markerFile, 'utf8').trim() : '';
  if (installedHash !== expectedHash) {
    try {
      // La primera ejecución instala todas las bibliotecas en segundo plano; el usuario
      // ya no tiene que borrar carpetas ni ejecutar setup.bat manualmente.
      await runCommand(venvPython, ['-m', 'pip', 'install', '--disable-pip-version-check', '--retries', '2', '--timeout', '25', '-r', requirementsFile], { cwd: ROOT, env });
      fs.writeFileSync(markerFile, expectedHash, 'utf8');
    } catch (error) {
      throw new Error(`No se pudieron instalar automáticamente las dependencias de Omniverse. Comprueba la conexión a Internet y vuelve a abrir el programa.\n\nDetalle: ${error.message}`);
    }
  }

  try {
    await runCommand(venvPython, ['manage.py', 'migrate', '--noinput'], { cwd: ROOT, env });
  } catch (error) {
    throw new Error(`No se pudo preparar la base de datos local de Omniverse.\n${error.message}`);
  }
  return { python: venvPython, env };
}

async function startDjango() {
  if (await isOmniverseRunningOnPort()) {
    // Si el usuario ya abrió la web local con run.bat, la app puede reutilizar ese servidor.
    return;
  }
  if (await portIsOpen()) {
    throw new Error('El puerto local 8000 está ocupado por otro programa. Cierra esa aplicación y vuelve a abrir Omniverse. No se usará un servidor ajeno por seguridad.');
  }

  const runtime = await prepareDjango();
  djangoProcess = spawn(runtime.python, ['manage.py', 'runserver', `${HOST}:${PORT}`, '--noreload'], {
    cwd: ROOT,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: runtime.env
  });
  ownsServer = true;
  let processExited = false;
  let processExitCode = null;
  djangoProcess.stdout.on('data', chunk => logLine(chunk.toString().trimEnd()));
  djangoProcess.stderr.on('data', chunk => logLine(chunk.toString().trimEnd()));
  djangoProcess.once('error', error => logLine(`Error de proceso Django: ${error.message}`));
  djangoProcess.once('exit', code => { processExited = true; processExitCode = code; });

  for (let i = 0; i < 180; i++) {
    if (await isOmniverseRunningOnPort()) return;
    if (processExited) break;
    await sleep(500);
  }
  throw new Error(`Omniverse no pudo iniciar el servidor local. Revisa que Python y las dependencias se hayan instalado correctamente y que el puerto 8000 esté libre.\n\nRegistro técnico: ${startupLogPath || 'no disponible'}\nCódigo de salida: ${processExitCode === null ? 'sin respuesta' : processExitCode}`);
}

function isWebsitePage(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (url.hostname !== HOST || url.port !== String(PORT)) return false;
    return ['/', '/crear-cuenta/', '/mi-cuenta/'].includes(url.pathname)
      || url.pathname.startsWith('/web/')
      || url.pathname.startsWith('/mi-cuenta/')
      || url.pathname.startsWith('/suscripcion/');
  } catch { return false; }
}

function showStartupWindow() {
  startupWindow = new BrowserWindow({
    width: 620,
    height: 500,
    minWidth: 620,
    minHeight: 500,
    resizable: false,
    minimizable: true,
    maximizable: false,
    backgroundColor: '#0b0b10',
    title: 'Iniciando Omniverse',
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
  });
  startupWindow.loadFile(path.join(ROOT, 'startup.html'));
}
async function createWindow() {
  if (startupWindow && !startupWindow.isDestroyed()) startupWindow.close();
  startupWindow = null;
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1024,
    minHeight: 680,
    backgroundColor: '#0b0b10',
    title: 'Omniverse',
    icon: path.join(ROOT, 'build', 'omniverse.ico'),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isWebsitePage(url)) shell.openExternal(url);
    else if (url.startsWith(BASE_URL)) mainWindow.loadURL(url);
    else shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (isWebsitePage(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  await mainWindow.loadURL(`${BASE_URL}/iniciar-sesion/`);
  mainWindow.on('closed', () => { mainWindow = null; });
  if (pendingFocus) focusMainWindow();
}

if (gotSingleInstanceLock) {
  app.on('second-instance', () => {
    // La instancia adicional solo enfoca la ventana existente; no vuelve a iniciar Django.
    focusMainWindow();
  });

  app.on('open-url', (event, url) => {
    event.preventDefault();
    if (url.toLowerCase().startsWith(`${APP_PROTOCOL}://`)) focusMainWindow();
  });

  app.whenReady().then(async () => {
    try {
      const userData = app.getPath('userData');
      fs.mkdirSync(userData, { recursive: true });
      startupLogPath = path.join(userData, 'omniverse-startup.log');
      showStartupWindow();
      if (process.defaultApp && process.argv.length >= 2) {
        app.setAsDefaultProtocolClient(APP_PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
      } else {
        app.setAsDefaultProtocolClient(APP_PROTOCOL);
      }
      await startDjango();
      await createWindow();
    } catch (error) {
      logLine(error.stack || error.message);
      if (startupWindow && !startupWindow.isDestroyed()) startupWindow.close();
      startupWindow = null;
      await dialog.showMessageBox({
        type: 'error',
        title: 'No se pudo iniciar Omniverse',
        message: error.message,
        detail: startupLogPath ? `Registro técnico: ${startupLogPath}` : undefined,
        buttons: ['Aceptar']
      });
      app.quit();
    }
  });

  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', () => {
    if (ownsServer && djangoProcess && djangoProcess.exitCode === null) djangoProcess.kill();
  });

}
