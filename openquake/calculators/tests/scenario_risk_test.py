# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2025 GEM Foundation
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

import numpy
from openquake.baselib.general import gettemp
from openquake.hazardlib import InvalidFile
from openquake.hazardlib.gsim_lt import InvalidLogicTree
from openquake.calculators.tests import (
    CalculatorTestCase, ignore_gsd_fields, strip_calc_id)
from openquake.calculators.views import view, text_table
from openquake.calculators.export import export
from openquake.calculators.extract import extract
from openquake.qa_tests_data.scenario_risk import (
    case_1, case_2, case_2d, case_1g, case_1h, case_3, case_4, case_5,
    case_6a, case_7, case_8, case_9, case_10, case_11, case_12,
    occupants, case_master, case_shakemap, case_shapefile, reinsurance,
    conditioned)


aac = numpy.testing.assert_allclose


def tot_loss(dstore):
    return dstore.read_df('aggrisk').loss.sum() / 2


class ScenarioRiskTestCase(CalculatorTestCase):

    def test_case_1(self):
        out = self.run_calc(case_1.__file__, 'job_risk.ini', exports='csv')
        [fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agg.csv', fname)

        # check the exported GMFs
        [fname, sitefile] = export(('gmf_data', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/gmf-FromFile.csv', fname)
        self.assertEqualFiles('expected/sites.csv', sitefile)

        [fname] = export(('risk_by_event', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/risk_by_event.csv', fname)

    def test_case_2(self):
        out = self.run_calc(case_2.__file__, 'job_risk.ini', exports='csv')
        [fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agg.csv', fname)

    def test_case_2d(self):
        # time_event not specified in job_h.ini but specified in job_r.ini
        out = self.run_calc(case_2d.__file__, 'job_h.ini,job_r.ini',
                            exports='csv')
        # this is also a case with a single site but an exposure grid,
        # to test a corner case
        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles(
            'expected/losses_by_asset.csv', fname, delta=1E-5)

        # test agglosses
        tot = extract(self.calc.datastore, 'agg_losses/occupants')
        aac(tot.array, [0.033761], atol=2E-5)

        # test agglosses with *
        tbl = extract(self.calc.datastore, 'agg_losses/occupants?taxonomy=*')
        self.assertEqual(tbl.array.shape, (1, 1))  # 1 taxonomy, 1 rlz

    def test_case_3(self):
        # a4 has a missing cost
        out = self.run_calc(case_3.__file__, 'job.ini', exports='csv')

        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles('expected/asset-loss.csv', fname, delta=5E-6)

        [fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agg_loss.csv', fname, delta=5E-6)

    def test_case_4(self):
        # this test is sensitive to the ordering of the epsilons
        out = self.run_calc(case_4.__file__, 'job.ini', exports='csv')
        fname = gettemp(view('totlosses', self.calc.datastore))
        self.assertEqualFiles('expected/totlosses.txt', fname)

        [fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agglosses.csv', fname, delta=1E-5)

    def test_occupants(self):
        out = self.run_calc(occupants.__file__, 'job_haz.ini,job_risk.ini',
                            exports='csv')
        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles('expected/asset-loss.csv', fname)

        [fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agg_loss.csv', fname, delta=1E-5)

    def test_case_5(self):
        # case with site model and 11 sites filled out of 17
        out = self.run_calc(case_5.__file__, 'job.ini', exports='csv')
        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles('expected/losses_by_asset.csv', fname,
                              delta=2E-5)

        # TODO: check pandas
        # df = self.calc.datastore.read_df('avg_losses-rlzs', 'asset_id')
        # self.assertEqual(list(df.columns), ['rlz', 'loss_type', 'value'])

    def test_case_6a(self):
        # case with two gsims
        self.run_calc(case_6a.__file__, 'job_haz.ini,job_risk.ini',
                      exports='csv')
        [f] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/aggrisk.csv', f, delta=5E-5)

        # testing the totlosses view
        dstore = self.calc.datastore
        fname = gettemp(view('totlosses', dstore))
        self.assertEqualFiles('expected/totlosses.txt', fname, delta=5E-5)

        # testing portfolio_losses
        fname = gettemp(view('portfolio_losses', dstore))
        self.assertEqualFiles('expected/portfolio_losses.txt', fname,
                              delta=5E-5)

        # two equal gsims
        with self.assertRaises(InvalidLogicTree):
            self.run_calc(case_6a.__file__, 'job_haz.ini',
                          gsim_logic_tree_file='wrong_gmpe_logic_tree.xml')

    def test_case_1g(self):
        out = self.run_calc(case_1g.__file__, 'job_haz.ini,job_risk.ini',
                            exports='csv')
        [_tot, fname] = out['aggrisk', 'csv']
        self.assertEqualFiles('expected/agg-gsimltp_@.csv', fname)

    def test_case_1h(self):
        # this is a case with 2 assets spawning 2 tasks
        out = self.run_calc(case_1h.__file__, 'job.ini', exports='csv')
        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles('expected/losses_by_asset.csv', fname)

        # with a single task
        out = self.run_calc(case_1h.__file__, 'job.ini', exports='csv',
                            concurrent_tasks='0')
        [fname] = out['avg_losses-rlzs', 'csv']
        self.assertEqualFiles('expected/losses_by_asset.csv', fname)

    def test_case_master(self):
        # a case with two GSIMs
        self.run_calc(case_master.__file__, 'job.ini', exports='npz')

        # check realizations
        [fname] = export(('realizations', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/realizations.csv', fname)

        # check aggrisk
        [fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/aggrisk.csv', fname)
        
        # extract losses by taxonomy
        extract(self.calc.datastore, 'agg_losses/structural?'
                'taxonomy=*').array  # shape (T, R) = (3, 2)

        # extract agglosses with a * and a selection
        obj = extract(self.calc.datastore, 'agg_losses/structural?'
                      'state=*&cresta=0.11')
        self.assertEqual(obj.selected, [b'state=*', b'cresta=0.11'])
        self.assertEqual(obj.tags, [b'state=01'])
        # from avg_losses-stats with two quantiles
        aac(obj.array, [[2368.6128, 2280.863 , 2561.6628]], atol=.02)

        # check portfolio_loss
        fname = gettemp(view('portfolio_loss', self.calc.datastore))
        # sensitive to shapely version
        self.assertEqualFiles('expected/portfolio_loss.txt', fname, delta=1E-3)

        # losses_by_site
        df = extract(self.calc.datastore, 'losses_by_site')
        fname = gettemp(text_table(df, ext='org'))
        self.assertEqualFiles('expected/losses_by_site.org', fname, delta=1E-3)

    def test_collapse_gsim_logic_tree(self):
        self.run_calc(case_master.__file__, 'job.ini',
                      collapse_gsim_logic_tree='bs1')
        fname = gettemp(view('portfolio_loss', self.calc.datastore))
        self.assertEqualFiles(
            'expected/portfolio_loss2.txt', fname, delta=1E-5)

    def test_case_7(self):
        # check independence from concurrent_tasks
        self.run_calc(case_7.__file__, 'job.ini', concurrent_tasks='10')
        tot10 = tot_loss(self.calc.datastore)
        self.run_calc(case_7.__file__, 'job.ini', concurrent_tasks='20')
        tot20 = tot_loss(self.calc.datastore)
        aac(tot10, tot20, atol=.0001)  # must be around 230.0107

        # check aggregate_by site_id
        [_tot, fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/agglosses.csv', fname)

    def test_case_8(self):
        # a complex scenario_risk from GMFs where the hazard sites are
        # not in the asset locations
        self.run_calc(case_8.__file__, 'job.ini')

        # the gmf_data exported failed in the past, since this is a
        # tricky case with filtered sitecol and autogenerated custom_site_id
        export(('gmf_data', 'csv'), self.calc.datastore)
        
        [_tot, fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/agglosses.csv', fname)

        agglosses = extract(self.calc.datastore, 'agg_losses/structural')
        aac(agglosses.array, [1159325.6])

        # make sure the fullreport can be extracted
        view('fullreport', self.calc.datastore)

    def test_case_9(self):
        # scenario_risk from GMFs with intensity_measure_types
        self.run_calc(case_9.__file__, 'job.ini')
        [fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/aggrisk.csv', fname)
        [_, fname] = export(('exposure', 'zip'), self.calc.datastore)
        self.assertEqualFiles('expected/assetcol.csv', fname)

    def test_case_10(self):
        # missing occupants in the exposure
        with self.assertRaises(InvalidFile):
            self.run_calc(case_10.__file__, 'job.ini')

    def test_case_11(self):
        out = self.run_calc(
            case_11.__file__,  'job.ini', exports='csv')
        [fname] = out[('aggrisk', 'csv')]
        self.assertEqualFiles('expected/aggrisk-_443.csv', fname)
        [fname] = out[('avg_losses-rlzs', 'csv')]
        self.assertEqualFiles(
            'expected/avg_losses-rlz-000_443.csv', fname)
        [_, fname] = export(('exposure', 'zip'), self.calc.datastore)
        self.assertEqualFiles('expected/assetcol.csv', fname)

    def test_case_12(self):
        # testing affected, injured
        out = self.run_calc(case_12.__file__,  'job.ini', exports='csv')
        for fname in out[('aggrisk', 'csv')]:
            self.assertEqualFiles(
                'expected/%s' % strip_calc_id(fname), fname)
        [fname] = out[('avg_losses-rlzs', 'csv')]
        self.assertEqualFiles('expected/avg_losses.csv', fname)

    def test_case_shakemap(self):
        self.run_calc(case_shakemap.__file__, 'pre-job.ini')
        self.run_calc(case_shakemap.__file__, 'job.ini',
                      hazard_calculation_id=str(self.calc.datastore.calc_id))
        sitecol = self.calc.datastore['sitecol']
        self.assertEqual(len(sitecol), 9)
        gmfdict = dict(extract(self.calc.datastore, 'gmf_data'))
        gmfa = gmfdict['rlz-000']
        self.assertEqual(gmfa.shape, (9,))
        self.assertEqual(
            gmfa.dtype.names,
            ('custom_site_id', 'lon', 'lat', 'PGA', 'SA(0.3)', 'SA(1.0)'))
        [fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/agglosses.csv', fname)

        [fname] = export(('realizations', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/realizations.csv', fname)

    def test_case_shapefile(self):
        self.run_calc(case_shapefile.__file__, 'prepare_job.ini')
        pre_id = str(self.calc.datastore.calc_id)
        self.run_calc(case_shapefile.__file__, 'job.ini',
                      hazard_calculation_id=pre_id)
        sitecol = self.calc.datastore['sitecol']
        self.assertEqual(len(sitecol), 7)
        gmfdict = dict(extract(self.calc.datastore, 'gmf_data'))
        gmfa = gmfdict['rlz-000']
        self.assertEqual(gmfa.shape, (7,))
        self.assertEqual(gmfa.dtype.names,
                         ('custom_site_id', 'lon', 'lat', 'MMI'))
        [fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/agglosses.csv', fname)

        [fname] = export(('realizations', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/realizations.csv', fname)

        # also test case if shapefiles are together in a zip file
        self.run_calc(case_shapefile.__file__, 'job_zipped.ini',
                      hazard_calculation_id=pre_id)
        [fname] = export(('realizations', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/realizations.csv', fname)

    def test_reinsurance(self):
        self.run_calc(reinsurance.__file__, 'job.ini')
        [fname] = export(('reinsurance-avg_portfolio', 'csv'),
                         self.calc.datastore)
        self.assertEqualFiles('expected/reinsurance-avg_portfolio.csv',
                              fname, delta=1E-5)

    def test_conditioned_stations(self):
        self.run_calc(conditioned.__file__, 'job.ini')
        [fname] = export(('avg_gmf', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/avg_gmf.csv', fname,
                              ignore_gsd_fields, delta=1E-5)
        [fname] = export(('aggrisk', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/aggrisk.csv', fname, delta=1E-5)
