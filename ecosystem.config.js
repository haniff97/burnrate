const path = require('path');

module.exports = {
  apps: [{
    name: 'burnrate',
    cwd: __dirname,
    script: path.join(__dirname, 'backend', '.venv', 'bin', 'python'),
    interpreter: 'none',
    args: ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '0.0.0.0', '--port', '4007'],
    exec_mode: 'fork',
    instances: 1,
    watch: false,
    autorestart: true,
    restart_delay: 3000,
    kill_timeout: 15000,
    time: true,
    env: { PYTHONUNBUFFERED: '1' },
  }],
};
