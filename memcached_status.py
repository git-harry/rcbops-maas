#!/usr/bin/env python

# Copyright 2014, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import argparse
import memcache
from ipaddr import IPv4Address

from maas_common import status_ok, status_err, metric, metric_bool


VERSION_RE = re.compile('STAT version (\d+\.\d+\.\d+)(?![-+0-9\\.])')
VERSIONS = ('1.4.13', '1.4.14 (Ubuntu)')
MEMCACHE_METRICS = ['total_items',
                    'get_hits',
                    'get_misses',
                    'total_connections']


def item_stats(host, port):
    """Check the stats for items and connection status."""

    stats = None
    try:
        mc = memcache.Client(['%s:%s' % (host, port)])
        stats = mc.get_stats()[0][1]
    except IndexError:
        raise
    finally:
        return stats


def main():
    parser = argparse.ArgumentParser(description='Check memcached status')
    parser.add_argument('ip', type=IPv4Address, help='memcached IP address.')
    parser.add_argument('--port', type=int,
                        default=11211, help='memcached port.')
    args = parser.parse_args()

    bind_ip = str(args.ip)
    port = args.port
    is_up = True

    try:
        stats = item_stats(bind_ip, port)
        current_version = stats['version']
    except TypeError, IndexError:
        is_up = False
    else:
        is_up = True
        if current_version not in VERSIONS:
            status_err('This plugin has only been tested with versions %s '
                       'of memcached, and you are using version \'%s\''
                       % (', '.join([repr(v) for v in VERSIONS]), current_version))

    status_ok()
    metric_bool('memcache_api_local_status', is_up)
    if is_up:
        for m in MEMCACHE_METRICS:
            metric('memcache_%s' % m, 'uint64', stats[m])


if __name__ == '__main__':
    main()
