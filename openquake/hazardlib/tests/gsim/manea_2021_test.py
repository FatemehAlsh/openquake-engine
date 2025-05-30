# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2014-2025 GEM Foundation
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
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

# Test data have been generated from the Python implementation available from the authors


from openquake.hazardlib.gsim.manea_2021 import ManeaEtAl2021
from openquake.hazardlib.tests.gsim.utils import BaseGSIMTestCase

#test case
class ManeaEtAl2021TestCase(BaseGSIMTestCase):
    """
    Test the default model, the total standard deviation, the between- and the within-event
    standard deviation. 
    """

    GSIM_CLASS = ManeaEtAl2021

    def test_all(self):
        self.check('MANEA20/Manea_2020_mean.csv',
                   'MANEA20/Manea_2020_total.csv',
                   'MANEA20/Manea_2020_inter.csv',
                   'MANEA20/Manea_2020_intra.csv',
                   max_discrep_percentage=0.1)
