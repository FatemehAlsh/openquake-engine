# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
# 
# Copyright (C) 2024, GEM Foundation
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

import sys
import getpass
import subprocess
from openquake.baselib import general


def ssh_args(zworkers):
    """
    :yields: triples (hostIP, num_cores, [ssh remote python command])
    """
    user = getpass.getuser()
    if zworkers.host_cores.strip():
        for hostcores in zworkers.host_cores.split(','):
            host, cores = hostcores.split()
            if host == '127.0.0.1':  # localhost
                yield host, cores, [sys.executable]
            else:
                yield host, cores, [
                    'ssh', '-f', '-T', user + '@' + host, sys.executable]


def start_workers(zworkers):
    """
    Start multiple workerpools on remote servers via ssh and/or a single
    workerpool on localhost.
    """
    starting = []
    for host, cores, args in ssh_args(zworkers):
        if general.socket_ready((host, zworkers.ctrl_port)):
            print('%s:%s already running' % (host, zworkers.ctrl_port))
            continue
        args += ['-m', 'openquake.baselib.workerpool', cores]
        if host != '127.0.0.1':
            print('%s: if it hangs, check the ssh keys' % ' '.join(args))
        subprocess.Popen(args)
        starting.append(host)
    return 'starting %s' % starting


def kill_workers(zworkers):
    """
    Send a "killall" command to all worker pools to cleanup everything
    in case of hard out of memory situations
    """
    killed = []
    for host, cores, args in ssh_args(zworkers):
        args = args[:-1] + ['killall', '-r', 'oq-zworker|multiprocessing']
        print(' '.join(args))
        subprocess.run(args)
        killed.append(host)
    return 'killed %s' % killed
