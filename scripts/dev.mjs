import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const pythonCommand = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
const nextBin = fileURLToPath(new URL('../node_modules/next/dist/bin/next', import.meta.url))

const python = spawn(pythonCommand, ['-B', 'scripts/serve_solve_api.py'], {
  cwd: root,
  stdio: 'inherit',
})
const next = spawn(process.execPath, [nextBin, 'dev', '-p', '3002'], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, MORTRA_LOCAL_SOLVE_URL: 'http://127.0.0.1:8766' },
})

function stop() {
  python.kill()
  next.kill()
}

process.on('SIGINT', stop)
process.on('SIGTERM', stop)

next.on('exit', code => {
  python.kill()
  process.exitCode = code ?? 0
})
python.on('exit', code => {
  if (code) {
    next.kill()
    process.exitCode = code
  }
})
