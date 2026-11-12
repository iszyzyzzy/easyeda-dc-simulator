"""Dependency-free packaging matching official SDK IIFE/ZIP format for this small module.
No arbitrary source rewriting: only the two known, explicitly checked module forms.
"""
import pathlib,zipfile
p=pathlib.Path(__file__).resolve().parent
core=(p/'src/exporter.mjs').read_text();entry=(p/'src/index.mjs').read_text()
assert core.count('export const FORMAT=')==1 and core.count('export async function capture(')==1
assert entry.count("import {capture} from './exporter.mjs';")==1 and entry.count('export async function exportNetwork(')==1
core=core.replace('export const FORMAT=','const FORMAT=').replace('export async function capture(','async function capture(')
entry=entry.replace("import {capture} from './exporter.mjs';",'').replace('export async function exportNetwork(','async function exportNetwork(')
js='var edaEsbuildExportName = (() => {\n'+core+'\n'+entry+'\nreturn { exportNetwork };\n})();\n'
(p/'dist').mkdir(exist_ok=True);(p/'dist/index.js').write_text(js)
with zipfile.ZipFile(p/'pcb-dc-readonly-export.eext','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['extension.json','dist/index.js']:z.write(p/name,name)
print(p/'pcb-dc-readonly-export.eext')
