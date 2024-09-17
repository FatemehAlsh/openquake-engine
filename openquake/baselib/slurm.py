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

import os
import stat
import time
import subprocess
from openquake.baselib import parallel, config
    
submit_cmd = list(config.distribution.submit_cmd.split())
SLURM_BATCH = '''\
#!/bin/bash
#SBATCH --job-name=oq{name}
#SBATCH --time={slurm_time}
#SBATCH --cpus-per-task={num_cores}
#SBATCH --nodes={nodes}
srun python -m openquake.baselib.workerpool {num_cores}
'''

def start_workers(job_ids, n):
    """
    Start n workerpools which will write on scratch_dir/hostcores)
    """
    calc_dir = parallel.scratch_dir(job_ids)
    slurm_sh = os.path.join(calc_dir, 'slurm.sh')
    print('Using %s' % slurm_sh)
    code = SLURM_BATCH.format(num_cores=config.distribution.num_cores,
                              slurm_time=config.distribution.slurm_time,
                              name=os.path.basename(calc_dir), nodes=n)
    with open(slurm_sh, 'w') as f:
        f.write(code)
    os.chmod(slurm_sh, os.stat(slurm_sh).st_mode | stat.S_IEXEC)

    assert submit_cmd[0] == 'sbatch', submit_cmd
    # submit_cmd can be ['sbatch', '-A', 'gem', '-p', 'rome', 'oq', 'run']
    subprocess.run(submit_cmd[:-2] + [slurm_sh])


def wait_workers(job_ids, n):
    """
    Wait until the hostcores file is filled with n names
    """
    calc_dir = parallel.scratch_dir(job_ids)
    fname = os.path.join(calc_dir, 'hostcores')
    while True:
        if not os.path.exists(fname):
            time.sleep(5)
            print(f'Waiting for {fname}')
            continue
        with open(fname) as f:
            hosts = f.readlines()
        print('%d/%d workerpools started' % (len(hosts), n))
        if len(hosts) == n:
            break
        else:
            time.sleep(5)
