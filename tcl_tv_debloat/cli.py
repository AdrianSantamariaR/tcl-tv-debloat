"""Terminal operations call exactly the same engine as the browser."""
import argparse,json,sys
from pathlib import Path
from . import __version__
from .adb import Adb
from .app import Application
from .inventory import load_catalog
from .rea import Rea,check_prerequisites
from .store import Store

def make_app(data_dir=None):return Application(Adb(),Store(Path(data_dir or '~/.tcl-tv-debloat')),load_catalog(),Rea())

def read_json(path):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise ValueError('Expected a JSON object.')
    return value

def import_record(app,kind,path):
    r=read_json(path)
    try:existing=app.store.load(kind,r['id'])
    except FileNotFoundError:app.store.save(kind,r);return r
    if existing!=r and existing.get('status')=='preview':raise ValueError('Imported preview differs from the saved record.')
    return existing

def main(argv=None):
    parser=argparse.ArgumentParser(description='Local Google TV package review, preview and exact-state recovery')
    parser.add_argument('--version',action='version',version=__version__);parser.add_argument('--data-dir',help='Private local data directory')
    commands=parser.add_subparsers(dest='command')
    commands.add_parser('doctor',help='Check standard and optional deep-analysis dependencies')
    serve=commands.add_parser('serve',help='Open the local browser wizard');serve.add_argument('--no-browser',action='store_true');serve.add_argument('--port',type=int,default=0)
    scan=commands.add_parser('scan',help='Read-only package inventory');scan.add_argument('--serial',required=True);scan.add_argument('--deep',action='store_true');scan.add_argument('--out')
    analyze=commands.add_parser('analyze',help='Add optional REA evidence');analyze.add_argument('--inventory',required=True);analyze.add_argument('--out')
    preview=commands.add_parser('preview',help='Save a change preview');preview.add_argument('--inventory',required=True);preview.add_argument('--selection');preview.add_argument('--privacy',nargs='+',choices=['tcl_bi_reporting','tcl_diagnostics']);preview.add_argument('--out')
    apply=commands.add_parser('apply',help='Apply a saved preview');apply.add_argument('--plan',required=True);apply.add_argument('--yes',action='store_true');apply.add_argument('--out')
    restore=commands.add_parser('restore',help='Scan, preview and restore a saved apply journal');restore.add_argument('--journal',required=True);restore.add_argument('--yes',action='store_true');restore.add_argument('--out')
    args=parser.parse_args(argv)
    try:
        app=make_app(args.data_dir);command=args.command or 'serve'
        if command=='serve':
            from .server import serve as launch
            launch(app,open_browser=not getattr(args,'no_browser',False),port=getattr(args,'port',0));return 0
        if command=='doctor':result=check_prerequisites(app.adb,app.rea)
        elif command=='scan':result=app.run('scan',{'serial':args.serial,'deep':args.deep})
        elif command in ('analyze','preview'):
            inv=import_record(app,'sessions',args.inventory)
            result=app.run(command,{'inventory_id':inv['id'],**({'selection':read_json(args.selection) if args.selection else {},'privacy_selection':args.privacy or []} if command=='preview' else {})})
        else:
            if command=='restore':
                journal=import_record(app,'plans',args.journal)
                inv=app.run('scan',{'serial':journal['device']['serial'],'deep':False})
                plan=app.run('restore_preview',{'inventory_id':inv['id'],'source_plan_id':journal['id']})
            else:plan=import_record(app,'plans',args.plan)
            print(json.dumps(plan,indent=2))
            if not args.yes:
                try:confirmed=input('Apply this preview to Android user 0? Type yes: ').strip().lower()=='yes'
                except EOFError:confirmed=False
                if not confirmed:print('No changes made.');return 1
            result=app.run(command,{'plan_id':plan['id']})
        output=json.dumps(result,indent=2,ensure_ascii=False)
        if getattr(args,'out',None):Path(args.out).write_text(output+'\n',encoding='utf-8')
        else:print(output)
        return 1 if result.get('status') in ('failed','cancelled') else 0
    except (ValueError,RuntimeError,OSError,KeyError) as e:print('Error: '+str(e),file=sys.stderr);return 1
