# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2017-2023, GEM Foundation
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
import sys
import time
import shutil
import socket
import getpass
import tempfile
import functools
import subprocess
from datetime import datetime
import psutil
from openquake.baselib import (
    DotDict, zeromq as z, general, performance, parallel, config, sap)
try:
    from setproctitle import setproctitle
except ImportError:
    def setproctitle(title):
        "Do nothing"


def init_workers():
    """Used to initialize the process pool"""
    setproctitle('oq-zworker')


def get_zworkers(dirname):
    """
    :param dirname: location of the hostcores file
    :returns: DotDict str->str with keys ctrl_port and host_cores
    """
    try:
        with open(os.path.join(dirname, 'hostcores')) as f:
            hostcores = f.read()
    except FileNotFoundError:
        hostcores = ''
    return DotDict(ctrl_port=config.zworkers.ctrl_port,
                   host_cores=hostcores.replace('\n', ',').rstrip(','))

class WorkerMaster(object):
    """
    :param dirname:
        a string like "calc_42-42" specifying the workerpool directory
    """
    def __init__(self, dirname):
        self.zworkers = get_zworkers(dirname)
        self.ctrl_port = int(self.zworkers.ctrl_port)
        self.host_cores = (
            [hc.split() for hc in self.zworkers.host_cores.split(',')]
            if self.zworkers.host_cores else [])
        self.popens = []

    def stop(self):
        """
        Send a "stop" command to all worker pools
        """
        stopped = []
        for host, _ in self.host_cores:
            if not general.socket_ready((host, self.ctrl_port)):
                continue
            ctrl_url = 'tcp://%s:%s' % (host, self.ctrl_port)
            with z.Socket(ctrl_url, z.zmq.REQ, 'connect') as sock:
                sock.send('stop')
                stopped.append(host)
        for popen in self.popens:
            popen.terminate()
            # since we are not consuming any output from the spawned process
            # we must call wait() after terminate() to have Popen()
            # fully deallocate the process file descriptors, otherwise
            # zombies will arise
            popen.wait()
        self.popens = []
        return 'stopped %s' % stopped

    def status(self):
        """
        :returns: a list [(host, running, total), ...]
        """
        executing = []
        for host, _cores in self.host_cores:
            if not general.socket_ready((host, self.ctrl_port)):
                continue
            ctrl_url = 'tcp://%s:%s' % (host, self.ctrl_port)
            with z.Socket(ctrl_url, z.zmq.REQ, 'connect') as sock:
                running = len(sock.send('get_executing').split())
                total = sock.send('get_num_workers')
                executing.append((host, running, total))
        return executing

    def send_jobs(self):
        """
        Send an asynchronous "run_jobs" command to the first WorkerPool
        """
        host, _cores = self.host_cores[0]
        ctrl_url = 'tcp://%s:%s' % (host, self.ctrl_port)
        with z.Socket(ctrl_url, z.zmq.REQ, 'connect') as sock:
            return sock.send('run_jobs')

    def wait(self, seconds=120):
        """
        Wait until all workers are active
        """
        num_hosts = len(self.zworkers.host_cores.split(','))
        for _ in range(seconds):
            time.sleep(1)
            status = self.status()
            if len(status) == num_hosts and all(
                    total for host, running, total in status):
                break
        else:
            raise TimeoutError(status)
        return status

    def restart(self):
        """
        Stop and start again
        """
        for host, _ in self.host_cores:
            if not general.socket_ready((host, self.ctrl_port)):
                continue
            ctrl_url = 'tcp://%s:%s' % (host, self.ctrl_port)
            with z.Socket(ctrl_url, z.zmq.REQ, 'connect', timeout=120) as sock:
                sock.send('restart')
        return 'restarted'

    def debug(self):
        """
        Start the workers, run a debug job, print some info and stop
        """
        self.start()
        try:
            mon = performance.Monitor('zmq-debug')
            mon.inject = True
            rec_host = config.dbserver.receiver_host or '127.0.0.1'
            receiver = 'tcp://%s:%s' % (
                rec_host, config.dbserver.receiver_ports)
            ntasks = len(self.host_cores) * 2
            task_no = 0
            with z.Socket(receiver, z.zmq.PULL, 'bind') as pull:
                mon.backurl = 'tcp://%s:%s' % (rec_host, pull.port)
                for host, _ in self.host_cores:
                    url = 'tcp://%s:%d' % (host, self.ctrl_port)
                    print('Sending to', url)
                    with z.Socket(url, z.zmq.REQ, 'connect') as sock:
                        for i in range(2):
                            msg = 'executing task #%d' % task_no
                            sock.send((debug_task, (msg,), task_no, mon))
                            task_no += 1
                results = list(get_results(pull, ntasks))
                print(f'{results=}')
        finally:
            self.stop()
        return 'debugged'


def get_results(socket, n):
    for res in socket:
        if n == 0:
            return
        elif res.msg != 'TASK_ENDED':
            yield res.get()
            n -= 1


def debug_task(msg, mon):
    """
    Trivial task useful for debugging
    """
    print(socket.gethostname(), msg)
    # while True: pass
    return mon.task_no


def call(func, args, taskno, mon, executing):
    fname = os.path.join(executing, f'{mon.calc_id}-{taskno}')
    # NB: very hackish way of keeping track of the running tasks,
    # used in get_executing, could litter the file system
    open(fname, 'w').close()
    parallel.safely_call(func, args, taskno, mon)
    os.remove(fname)


def errback(job_id, task_no, exc):
    # NB: job_id can be None if the Starmap was invoked without h5
    from openquake.commonlib.logs import dbcmd
    dbcmd('log', job_id, datetime.utcnow(), 'ERROR',
          '%s/%s' % (job_id, task_no), str(exc))
    e = exc.__class__('in job %d, task %d' % (job_id, task_no))
    raise e.with_traceback(exc.__traceback__)


class WorkerPool(object):
    """
    A pool of workers accepting various commands.

    :param ctrl_url: zmq address of the control socket
    :param num_workers: the number of workers (or -1)
    """
    def __init__(self, num_workers=-1):
        self.ctrl_port = config.zworkers.ctrl_port
        if num_workers == -1:
            try:
                self.num_workers = len(psutil.Process().cpu_affinity())
            except AttributeError:  # missing cpu_affinity on macOS
                self.num_workers = psutil.cpu_count()
        else:
            self.num_workers = num_workers
        self.executing = tempfile.mkdtemp(dir=config.directory.custom_tmp)
        try:
            os.mkdir(self.executing)
        except FileExistsError:  # already created by another WorkerPool
            pass
        self.pid = os.getpid()

    def start(self):
        """
        Start worker processes and a control loop
        """
        self.hostname = socket.gethostname()
        if self.job_id:
            # save the hostname in calc_XXX/hostcores
            calc_dir = os.path.join(
                config.directory.custom_tmp, 'calc_%s' % self.job_id)
            try:
                os.mkdir(calc_dir)
            except FileExistsError:  # somebody else created it
                pass
            if parallel.oq_distribute() == 'slurm':
                fname = os.path.join(calc_dir, 'hostcores')
                line = f'{self.hostname} {self.num_workers}'
                print(f'Writing {line} on {fname}')
                with open(fname, 'a') as f:
                    f.write(line + '\n')

        print(f'Starting oq-zworkerpool on {self.hostname}', file=sys.stderr)
        setproctitle('oq-zworkerpool')
        self.pool = general.mp.Pool(self.num_workers, init_workers)
        pids = [proc.pid for proc in self.pool._pool]
        # start control loop accepting the commands stop
        try:
            ctrl_url = 'tcp://0.0.0.0:%s' % self.ctrl_port
            with z.Socket(ctrl_url, z.zmq.REP, 'bind') as ctrlsock:
                for cmd in ctrlsock:
                    if cmd == 'stop':
                        ctrlsock.send(self.stop())
                        break
                    elif cmd == 'restart':
                        self.stop()
                        self.pool = general.mp.Pool(self.num_workers)
                        ctrlsock.send('restarted')
                    elif cmd == 'getpid':
                        ctrlsock.send(self.proc.pid)
                    elif cmd == 'get_num_workers':
                        ctrlsock.send(self.num_workers)
                    elif cmd == 'get_executing':
                        executing = sorted(os.listdir(self.executing))
                        ctrlsock.send(' '.join(executing))
                    elif cmd == 'run_jobs':
                        pik = os.path.join(self.scratch, 'jobs.pik')
                        lst = ['python', '-m', 'openquake.engine.engine', pik]
                        subprocess.Popen(lst)
                        ctrlsock.send("started %s" % self.job_ids)
                    elif cmd == 'memory_gb':
                        ctrlsock.send(performance.memory_gb(pids))
                    elif isinstance(cmd, tuple):
                        _func, _args, taskno, mon = cmd
                        self.pool.apply_async(
                            call, cmd + (self.executing,),
                            error_callback=functools.partial(
                                errback, mon.calc_id, taskno))
                        ctrlsock.send('submitted')
                    else:
                        ctrlsock.send('unknown command')
        finally:
            shutil.rmtree(self.executing)

    def stop(self):
        """
        Terminate the pool
        """
        self.pool.close()
        self.pool.terminate()
        self.pool.join()
        return 'WorkerPool on %s stopped' % self.hostname


def workerpool(num_workers: int=-1, job_id: int=0):
    """
    Start a workerpool with the given number of workers.
    """
    # NB: unexpected errors will appear in the DbServer log
    wpool = WorkerPool(num_workers, job_id)
    try:
        wpool.start()
    finally:
        wpool.stop()

workerpool.num_workers = dict(help='number of cores to use')
workerpool.job_id = dict(help='associated job')


if __name__ == '__main__':
    sap.run(workerpool)
