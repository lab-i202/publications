"""Command line interface: python -m pubgroup --help."""
import argparse
import getpass
import os
import sys
from . import __version__, BUILD
from .workflow import run

def main():
    parser = argparse.ArgumentParser(description='Collect research publications and build a LaTeX PDF and website.')
    parser.add_argument('--version', action='version', version=f'Publication Group {__version__} (build {BUILD})')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('run', 'report'):
        p = sub.add_parser(command, help='Fetch profiles and generate outputs' if command == 'run' else 'Rebuild outputs from saved collection')
        p.add_argument('--config', default='config.toml')
        p.add_argument('--period', help='current, all, range, or a year such as 2025')
        p.add_argument('--offline', action='store_true', help='Use cached sources only')
        p.add_argument('--refresh', action='store_true', help='Ignore fresh HTTP cache')
        p.add_argument('--no-pdf', action='store_true', help='Write LaTeX without compiling it')
        p.add_argument('--no-enrich', action='store_true', help='Skip DOI APIs')
        p.add_argument('--encrypt', action='store_true', help='Encrypt the web dataset and PDF; prompt for passphrase')
    p = sub.add_parser('serve', help='Serve the web listing on localhost; allow local refresh and report builds')
    p.add_argument('--config', default='config.toml'); p.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            from .server import serve
            serve(args.config, args.port)
        else:
            passphrase = None
            if args.encrypt:
                passphrase = os.environ.get('PUBGROUP_PASSPHRASE') or getpass.getpass('Web export passphrase: ')
                if len(passphrase) < 16:
                    raise ValueError('Use at least 16 characters for the encryption passphrase')
            run(args.config, period=args.period, offline=args.offline, refresh=args.refresh,
                no_pdf=args.no_pdf, no_enrich=args.no_enrich, passphrase=passphrase,
                report_only=args.command == 'report')
    except (ValueError, RuntimeError, OSError) as exc:
        print('Error: ' + str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
