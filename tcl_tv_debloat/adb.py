"""Small bounded ADB adapter. All Android shell arguments are conservative tokens."""
import ipaddress
import os
import re
import shutil
import subprocess
from pathlib import Path

TOKEN = re.compile(r'^[A-Za-z0-9_./:@=+\[\]-]+$')
PACKAGE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$')

def address(value):
    if not isinstance(value, str): raise ValueError('Use a numeric IP address and port.')
    match = re.fullmatch(r'(\[[0-9a-fA-F:]+\]|[0-9.]+):([0-9]+)', value)
    if not match: raise ValueError('Use a numeric IP address and port, for example 192.168.1.100:5555.')
    ipaddress.ip_address(match[1].strip('[]'))
    if not 1 <= int(match[2]) <= 65535: raise ValueError('Port must be between 1 and 65535.')
    return value

class Adb:
    def __init__(self, command=None, env=None, timeout=30):
        self.command = list(command) if command else [shutil.which('adb') or 'adb']
        self.env = {**os.environ, **(env or {})}
        self.timeout = timeout
    def _run(self, args, *, stdin=None):
        try:
            result = subprocess.run(self.command + list(args), input=stdin, text=True, capture_output=True, env=self.env, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError('ADB unavailable or timed out.') from e
        if result.returncode: raise RuntimeError((result.stderr or result.stdout or 'ADB command failed.').strip())
        return result.stdout.replace('\r\n', '\n').strip()
    def version(self): return self._run(['version'])
    def devices(self):
        out = []
        for line in self._run(['devices', '-l']).splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[1] in ('device', 'unauthorized', 'offline', 'recovery', 'sideload'):
                out.append({'serial': fields[0], 'state': fields[1], 'description': ' '.join(fields[2:])})
        return out
    def _target(self, serial):
        if not isinstance(serial, str) or not TOKEN.fullmatch(serial) or serial.startswith('-'): raise ValueError('Invalid device identifier.')
        if not any(d['serial'] == serial and d['state'] == 'device' for d in self.devices()): raise ValueError('Select a connected, authorized device.')
        return serial
    def connect(self, value):
        out = self._run(['connect', address(value)])
        if 'connected to' not in out: raise RuntimeError(out or 'Connection failed.')
        return out
    def pair(self, value, code):
        address(value)
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code): raise ValueError('Pairing code must have six digits.')
        try: out = self._run(['pair', value], stdin=code+'\n')
        except RuntimeError: raise RuntimeError('ADB pairing failed. Check the TV and pairing port.') from None
        if 'Successfully paired' not in out: raise RuntimeError('ADB pairing failed. Check the TV and pairing port.')
    def shell(self, serial, args):
        if not args or any(not isinstance(a, str) or not TOKEN.fullmatch(a) for a in args): raise ValueError('Invalid Android command argument.')
        return self._run(['-s', self._target(serial), 'shell', *args])
    def pull(self, serial, remote, local: Path):
        if not isinstance(remote, str) or not remote.startswith('/') or not TOKEN.fullmatch(remote): raise ValueError('Invalid APK path.')
        self._run(['-s', self._target(serial), 'pull', remote, str(local)])
