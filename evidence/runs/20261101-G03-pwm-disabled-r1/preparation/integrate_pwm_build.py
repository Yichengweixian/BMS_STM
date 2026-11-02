"""Append independent output-disabled Keil targets after the port is ready.

Run from this staging directory. Original target XML is retained byte-for-byte;
the script does not invoke Keil, a serial interface, or a programmer.
"""
from pathlib import Path
import copy
import hashlib
import json
import re
import xml.etree.ElementTree as ET

STAGE = Path(__file__).resolve().parent
WORKSPACE = STAGE / 'workspace'
PROJECT = WORKSPACE / 'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx'
TARGETS = (
    ('BMS_EX_Debug', 'BMS_PWM_Disabled_Debug'),
    ('BMS_EX_Release', 'BMS_PWM_Disabled_Release'),
)
REQUIRED_DEFINES = ('G03_PWM_DISABLED_BUILD=1', 'G3R_LIVE_PROFILE_VERIFIED=0')
SOURCES = ('pwm_oneshot.c', 'g03_pwm_port.c')


def required(parent, path):
    result = parent.find(path)
    if result is None:
        raise ValueError('Required project element missing: '+path)
    return result


def clone_target(original, name):
    target = copy.deepcopy(original)
    target.tail = None
    required(target, 'TargetName').text = name
    common = required(target, 'TargetOption/TargetCommonOption')
    required(common, 'OutputDirectory').text = name+'\\'
    required(common, 'OutputName').text = name
    required(common, 'ListingPath').text = name+'\\'
    for language in ('Cads', 'Aads'):
        defines = required(target, 'TargetOption/TargetArmAds/'+language+'/VariousControls/Define')
        tokens = [item.strip() for item in (defines.text or '').split(',') if item.strip()]
        for new_define in REQUIRED_DEFINES:
            macro = new_define.split('=', 1)[0]
            tokens = [item for item in tokens if item.split('=', 1)[0].strip() != macro]
            tokens.append(new_define)
        defines.text = ','.join(tokens)

    # The original linker emits a CMSE object into shared Secure_nsclib.
    # New targets keep that generated artifact inside their own output folders.
    miscellaneous = required(target, 'TargetOption/TargetArmAds/LDads/Misc')
    linker_text, replacements = re.subn(
        r'--import_cmse_lib_out=(?:"[^"]+"|\S+)',
        lambda _: '--import_cmse_lib_out='+name+'\\secure_nsclib.o',
        miscellaneous.text or '')
    if replacements != 1:
        raise ValueError('Expected one inherited CMSE output option')
    miscellaneous.text = linker_text

    groups = required(target, 'Groups')
    bsp = [group for group in groups.findall('Group') if group.findtext('GroupName') == 'BSP']
    if len(bsp) != 1:
        raise ValueError('Expected exactly one BSP group')
    files = required(bsp[0], 'Files')
    existing = {file.findtext('FileName') for file in files.findall('File')}
    for source in SOURCES:
        if source in existing:
            raise ValueError('New source unexpectedly already present: '+source)
        file = ET.SubElement(files, 'File')
        ET.SubElement(file, 'FileName').text = source
        ET.SubElement(file, 'FileType').text = '1'
        ET.SubElement(file, 'FilePath').text = '..\\..\\BSP\\'+source
    return target


def make_project(original):
    text = original.decode('utf-8')
    document = ET.fromstring(original)
    targets = required(document, 'Targets')
    by_name = {target.findtext('TargetName'): target for target in targets.findall('Target')}
    if len(by_name) != len(targets.findall('Target')):
        raise ValueError('Duplicate original target names')
    for source, destination in TARGETS:
        if source not in by_name:
            raise ValueError('Missing original target '+source)
        if destination in by_name:
            raise ValueError('Refusing to duplicate or overwrite existing target '+destination)

    newline = '\r\n' if b'\r\n' in original else '\n'
    new_blocks = []
    for source, destination in TARGETS:
        clone = clone_target(by_name[source], destination)
        ET.indent(clone, space='  ', level=2)
        new_blocks.append('    '+ET.tostring(clone,encoding='unicode',short_empty_elements=False).replace('\n',newline))
    closing = '  </Targets>'
    if text.count(closing) != 1:
        raise ValueError('Expected one unchanged Targets closing element')
    insert = newline.join(new_blocks)+newline
    updated = text.replace(closing, insert+closing, 1).encode('utf-8')

    # Re-parse and verify every old target remains semantically identical.
    # The replacement above also leaves every byte outside the insertion intact.
    result = ET.fromstring(updated)
    all_targets = {target.findtext('TargetName'):target for target in required(result,'Targets').findall('Target')}
    for name, old in by_name.items():
        # Adding the next sibling changes whitespace in the former last tail.
        # Compare each complete target body independently of that sibling tail.
        observed, expected = copy.deepcopy(all_targets[name]), copy.deepcopy(old)
        observed.tail = expected.tail = None
        assert ET.tostring(observed) == ET.tostring(expected), 'Original target changed: '+name
    for _, name in TARGETS:
        common = required(all_targets[name],'TargetOption/TargetCommonOption')
        assert common.findtext('OutputDirectory') == name+'\\'
        assert common.findtext('OutputName') == name
        new_defines = required(all_targets[name], 'TargetOption/TargetArmAds/Cads/VariousControls/Define').text
        assert all(value in new_defines.split(',') for value in REQUIRED_DEFINES)
        for source in SOURCES:
            assert sum(f.findtext('FileName') == source for f in all_targets[name].findall('Groups/Group/Files/File')) == 1
    assert len(all_targets) == len(by_name)+2
    return updated


def main():
    for source in SOURCES:
        if not (WORKSPACE/'BMS_EXv1.1/BMS_EX/BSP'/source).is_file():
            raise RuntimeError('Finish board port before integrating targets: '+source)
    out = STAGE/'build-integration'
    before = PROJECT.read_bytes()
    after = make_project(before)
    out.mkdir(exist_ok=False)
    (out/'BMS_EX_Appli.before.uvprojx').write_bytes(before)
    PROJECT.write_bytes(after)
    manifest = dict(project=str(PROJECT), preserved_targets=[x[0] for x in TARGETS],
                    new_targets=[x[1] for x in TARGETS], definitions=REQUIRED_DEFINES,
                    added_sources=SOURCES, cmse_outputs_isolated=True,
                    before_sha256=hashlib.sha256(before).hexdigest(),
                    after_sha256=hashlib.sha256(after).hexdigest(),
                    build_invoked=False,hardware_access=False,
                    outputs={name:str(PROJECT.parent/name/(name+'.hex')) for _,name in TARGETS})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    main()
