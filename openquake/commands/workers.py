#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2017-2023 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import sys
import getpass
from openquake.baselib import config, workerpool as w, parallel as p

CHOICES = 'start stop status restart wait kill debug'.split()


def last_pool():
    """
    :returns: the latest workerpool in the custom_tmp directory
    """
    calcs = []
    for name in os.listdir(config.directory.custom_tmp):
        mo = re.search('calc\_(\d+)-(\d+)', name)
        if mo:
            calcs.append((int(mo.group(1)), name))
    if not calcs:
        sys.exit('No workerpool ever started')
    last_id, last = sorted(calcs)[-1]
    return last
                        

def main(cmd, workerpool=''):
    """
    query or start/stop/kill the workers
    """
    if (cmd != 'status' and config.multi_user and
            getpass.getuser() not in 'openquake'):
        sys.exit('oq workers only works in single user mode')
    dist = p.oq_distribute()
    if dist in ('zmq', 'slurm'):
        master = w.WorkerMaster(workerpool or last_pool())
        print(getattr(master, cmd)())
    else:
        print('Nothing to do: oq_distribute=%s' % dist)


main.cmd = dict(help='command', choices=CHOICES)
main.workerpool = dict(help='workerpool string (example calc_123-124)')
