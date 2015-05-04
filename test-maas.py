import argparse
import datetime
import errno
import json
import os
import pyrax
import re
import requests
import sys

requests.packages.urllib3.disable_warnings()

USERNAME = os.environ['OS_USERNAME']
API_KEY = os.environ['OS_PASSWORD']
REGION = os.environ['OS_REGION_NAME']

pyrax.set_setting('identity_type', 'rackspace')
pyrax.set_default_region(REGION)
pyrax.set_credentials(USERNAME, API_KEY)
#pyrax.set_http_debug(True)

CM = pyrax.cloud_monitoring

# Monkey patching to provide metric_list view support
cm_class = pyrax.cloudmonitoring
CM._metric_list_manager = cm_class._EntityFilteringManger(
    CM, uri_base='views/metric_list', resource_class=None, response_key='view',
    plural_response_key=None)


def _get_metric_list(self=CM, entity=None):
    # the API doesn't appear to filter based on entity
    # return self._metric_list_manager.list(entity=entity)
    return self._metric_list_manager.list()


CM.get_metric_list = _get_metric_list

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('playbook', help='MaaS playbook used to setup Maas.')
    parser.add_argument('branch', help='Playbook branch.')
    parser.add_argument('label_templates', nargs='*', default=[],
                        help='entity_label:template_mapping')
    parser.add_argument('--raw_output', action='store_true')
    parser.add_argument('--from_file')
    parser.add_argument('--base_dir', default='.')
    args = parser.parse_args()
    return args


def get_entities(labels):
    uniq_labels = set(labels)
    all_entities = CM.list_entities()
    matched_entities = []
    matched_labels = set()
    for entity in all_entities:
        if entity.label in uniq_labels:
            matched_entities.append(entity)
            matched_labels.add(entity.label)
    unmatched_labels = uniq_labels - matched_labels
    if unmatched_labels:
        raise Exception('The label(s), "%s", do not match any entities.' %
                        ', '.join(unmatched_labels))
    return tuple(matched_entities)


def get_metric_list(entity=None):
    all_metrics = CM.get_metric_list()['values']
    for en in all_metrics:
        if entity and en['entity_id'] == entity.id:
            metric_list = en
            break
    else:
        if entity:
            err_str = ('No match found for entity "{entity}" in metric list.'
                       ''.format(entity=entity))
            raise Exception(err_str)
        else:
            metric_list = all_metrics

    return metric_list


def get_overview(entity=None):
    return CM.get_overview(entity=entity)['values']


def get_api_data(labels):
    entities = get_entities(labels)
    if entities:
        metrics = []
        overview = []
        for entity in entities:
            metrics.append(get_metric_list(entity=entity))
            overview.extend(get_overview(entity=entity))
    else:
        metrics = get_metric_list()
        overview = get_overview()
    data = []
    for overview, metrics in zip(overview, metrics):
        e = {}
        e['entity'] = overview['entity']
        e['checks'] = overview['checks']
        for check in e['checks']:
            check['alarms'] = [alarm for alarm in overview['alarms'] if
                               alarm['check_id'] == check['id']]
            check['metrics'] = [
                metric['metrics'] for metric in metrics['checks'] if
                metric['id'] == check['id']]
        data.append(e)
    return data


def things_by(by_what, things):
    things_by = {}
    for thing in things:
        things_by[thing[by_what]] = thing
    return things_by


def remove_keys(dictionary):
    to_remove = {'created_at', 'updated_at', 'latest_alarm_states',
                 'check_id', 'entity_id', 'id', 'agent_id', 'label',
                 'notification_plan_id', 'uri'}
    for key in dictionary.keys():
        if key in to_remove:
            del dictionary[key]

if __name__ == '__main__':
    args = parse_args()
    directory = os.path.join(args.base_dir, args.branch)
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e
    template_mappings = {}
    for lt in args.label_templates:
        try:
            label, template = lt.split(':', 1)
        except ValueError:
            label = lt
            template = None
        template_mappings[label] = template
    labels = template_mappings.keys()

    if args.from_file:
        with open(args.from_file) as f:
            raw_data = json.loads(f.read())
    else:
        raw_data = get_api_data(labels)

    if args.raw_output:
        raw_filename = '{playbook}.maas_data.raw'.format(
            branch=args.branch, playbook=args.playbook)
        path = os.path.join(directory, raw_filename)
        with open(path, 'w') as f:
            f.write(json.dumps(raw_data, indent=4, separators=(',', ': '),
                               sort_keys=True))

    entities = {}
    for host, hostname in zip(raw_data, labels):
        for check in host['checks']:
            check['alarms'] = things_by('label', check['alarms'])
            check['metrics'] = things_by('name', check['metrics'][0])
        host['checks'] = things_by('label', host['checks'])
        host['entity']['checks'] = host['checks']
        template = template_mappings[hostname]
        host['entity']['original_label'] = host['entity']['label']
        entities[template] = host['entity']

    for entity in entities.viewvalues():
        remove_keys(entity)
        remove_keys(entity['checks'])
        for check in entity['checks'].viewvalues():
            remove_keys(check)
            remove_keys(check['alarms'])
            for alarm in check['alarms'].viewvalues():
                remove_keys(alarm)

    json_bits = ['{']
    for entity_label, entity in entities.viewitems():
        original_label = entity['original_label']
        del entity['original_label']

        json_bit = json.dumps(entity)

        json_bit = re.sub(original_label, entity_label, json_bit)

        if entity['ip_addresses']:
            for label, ip in host['entity']['ip_addresses'].viewitems():
                json_bit = re.sub('(?<![0-9]){ip}(?![0-9])'.format(ip=ip),
                                  label.upper(), json_bit)
        json_bits.extend(('"', entity_label, '":', json_bit, ','))
    json_bits[-1] = '}'
    json_blob = ''.join(json_bits)

    json_blob = re.sub(r'container-[0-9a-f]{8}', 'container-UID', json_blob)
    json_blob = re.sub(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',
                       'IP_ADDRESS', json_blob)

    filename = '{playbook}.maas_data'.format(playbook=args.playbook)
    path = os.path.join(directory, filename)
    with open(path, 'w') as f:
        f.write(json.dumps(json.loads(json_blob), indent=4,
                           separators=(',', ': '), sort_keys=True))
