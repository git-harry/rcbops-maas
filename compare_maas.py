import argparse
import collections
import json
import os
import sys

def load_data(template, branch, templates_dir):
    path = os.path.join(templates_dir, branch, template)
    with open(path) as f:
        data = f.read()
    return json.loads(data)


def compare(reference, new, ignored_keys=None):
    missing_from_new = {}
    different = {}
    modified = {}
    ret = {}
    if ignored_keys is None:
        ignored_keys = set()
    for key1, value1 in reference.viewitems():
        if key1 in ignored_keys:
            try:
                del new[key1]
            except KeyError:
                pass
            continue
        else:
            try:
                value2 = new[key1]
            except KeyError:
                missing_from_new[key1] = value1
            else:
                try:
                    rec_comp = compare(value1, value2, ignored_keys=ignored_keys)
                    if rec_comp:
                        modified[key1] = rec_comp
                except AttributeError:
                    if value1 != value2:
                        different[key1] = {'reference': value1, 'new': value2}
                del new[key1]
    missing_from_reference = new
    for k, v in {'different': different,
                 'missing_from_reference': missing_from_reference,
                 'missing_from_new': missing_from_new,
                 'modified': modified}.viewitems():
        if v:
            ret[k] = v
    return ret


def load_playbooks(playbooks, templates_dir='templates', branch=None):
    for playbook in playbooks:
        checks_by_host_type = {}
        template = playbook.endswith('.yml') and playbook[:-4] or playbook
        path = os.path.join(templates_dir, branch, template)
        data = load_data(template, branch, templates_dir)
        for entity_label, entity in data.viewitems():
            if entity_label in checks_by_host_type:
                # combine entities, first pass only update checks.
                checks_by_host_type[entity_label]['checks'].update(entity['checks'])
            else:
                checks_by_host_type[entity_label] = entity

    return checks_by_host_type


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--playbooks', nargs='+', help='A list of the playbooks to test.')
    parser.add_argument('--branch')
    parser.add_argument('--templates_dir', default='.')
    parser.add_argument('--test_file')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    reference = load_playbooks(args.playbooks,
                               templates_dir=args.templates_dir,
                               branch=args.branch)
    new = load_data(args.test_file, args.branch, args.templates_dir)

    output = compare(reference, new)
    if output:
        sys.exit(json.dumps(output, indent=4, separators=(',', ': '), sort_keys=True))
