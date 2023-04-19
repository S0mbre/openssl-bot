import subprocess as sp
import platform, os, traceback, logging, io, uuid
from pathlib import Path
from typing import Union

from config import CONFIG

# ============================================================ #

OSPLATFORM = platform.system()
SSLEXE = Path(CONFIG.openssl_root) / 'openssl'
TEMP = Path(CONFIG.temp_dir)
ENC = 'utf-8'
PEM_START = '-----BEGIN CERTIFICATE-----'
PEM_END = '-----END CERTIFICATE-----'
NL = '\n'

# ============================================================ #

def run_exe(args, external=False, capture_output=True, stdout=sp.PIPE, encoding=ENC,
            timeout=None, shell=False, **kwargs):    
    if external:
        if OSPLATFORM == 'Windows':
            creationflags=sp.CREATE_NO_WINDOW | sp.DETACHED_PROCESS
            return sp.Popen(args,
                creationflags=creationflags,
                stdout=stdout if capture_output else None,
                stderr=sp.STDOUT if capture_output else None,
                encoding=encoding, shell=shell, **kwargs)
        else:
            return sp.Popen('nohup ' + (args if isinstance(args, str) else ' '.join(args)),
                stdout=stdout if capture_output else None,
                stderr=sp.STDOUT if capture_output else None,
                encoding=encoding, shell=shell, preexec_fn=os.setpgrp,
                **kwargs)
    else:
        return sp.run(args, capture_output=capture_output, encoding=encoding,
                        timeout=timeout, shell=shell, **kwargs)
    
def generate_uid():
    return uuid.uuid4().hex

def check_ossl_path():
    return Path(CONFIG.openssl_root).exists()

def check_ossl():
    try:
        if not check_ossl_path():
            raise Exception('OpenSSL path not found or invalid')
        res = run_exe([SSLEXE, 'version'])
        res.check_returncode()
        return res.stdout
    except:
        logging.exception(traceback.format_exc())
        return None
    
def process_pem(pem: Union[str, io.BytesIO], filename: str) -> Path:
    if not isinstance(pem, str):
        pem = pem.getvalue().decode(ENC)
    lines_pem = [l for l in pem.splitlines() if l.strip()]
    if len(lines_pem) < 3 or lines_pem[0] != PEM_START or lines_pem[-1] != PEM_END:
        raise Exception(f'Wrong PEM format in file "{filename}"')
    if len(lines_pem) > 3:
        lines_pem = [lines_pem[0], ''.join(lines_pem[1:-1]), lines_pem[-1]]
    fpath = TEMP / filename
    if fpath.exists():
        os.remove(fpath)
    with open(fpath, 'w', encoding=ENC) as f:
        f.write(NL.join(lines_pem))
    return fpath
    
def make_pkcs12(cert: Union[str, io.BytesIO], key: Union[str, io.BytesIO], name: str = None, password: str = None) -> bytes:
    if not check_ossl():
        raise Exception('OpenSSL path not found or invalid')
    
    uid = generate_uid()

    cert_file = process_pem(cert, f'{uid}.crt')
    key_file = process_pem(key, f'{uid}.key')

    outfile = TEMP / f'{uid}.p12'
    if outfile.exists():
        os.remove(outfile)

    # openssl pkcs12 -export -in cert.crt -inkey cert.key -passout pass:123123 -out cert1.p12
    args = [SSLEXE, 'pkcs12', '-export', '-in', str(cert_file), '-inkey', str(key_file), '-passout', f'pass:{password or ""}', '-out', str(outfile)]
    if name: args += ['-name', name]

    if not outfile.exists():
        raise Exception(f'Error exporting PKCS key to "{str(outfile)}"')
    
    res = None
    with open(outfile, 'rb') as f:
        res = f.read()
    return res