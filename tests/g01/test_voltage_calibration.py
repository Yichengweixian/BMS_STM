"""Synthetic vectors only; never hardware calibration evidence."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/g01'))
import voltage_calibration as v
from g01_capture import FIELDS, pec15


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root/'capture'
        (self.folder/'raw').mkdir(parents=True)
        (self.folder/'derived').mkdir()
        self.rows = []
        self.plan = dict(schema='g01-voltage-points-v1', calibration_id='SYNTHETIC-ONLY', points=[])
        for index, raw in enumerate((30000, 35000, 40000, 37500)):
            for j in range(3):
                value = raw+j-1
                data = value.to_bytes(2, 'little')+b'\xff'*4
                frame = data+pec15(data).to_bytes(2, 'big')
                row = dict(zip(FIELDS, ['M', str(index*3+j), 'cell1', str((index*3+j)*500),
                    str((index*3+j)*500+3), '0', str(value), '128', '1', str(value/10000),
                    str(value/10000), 'V', '', '0', '', 'uncalibrated-v1', frame.hex(), '']))
                row['wire_pec15'] = '%04X'%pec15(','.join(row[k] for k in FIELDS[:-1]).encode())
                row.update(boot_id='sim:0', host_rx_utc='2026-01-01T00:00:00+00:00')
                self.rows.append(row)
            self.plan['points'].append(dict(id='p'+str(index), capture='capture', boot_id='sim:0',
                channel='cell1', role='fit' if index < 3 else 'validation', seq_first=index*3,
                seq_last=index*3+2, reference_V=raw*0.000101+0.02, instrument_id='synthetic',
                mapping_evidence='synthetic channel mapping', reference_time_evidence='synthetic windows',
                reference_condition='independent-'+str(index), expanded_uncertainty_V=None))
        self.save()

    def save(self):
        with (self.folder/'derived/device.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['boot_id', 'host_rx_utc']+FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        (self.folder/'raw/serial.bin').write_bytes(b''.join(
            (','.join(r[k] for k in FIELDS)+'\r\n').encode() for r in self.rows))
        (self.folder/'raw/events.jsonl').write_text('', encoding='utf-8')
        manifest = dict(schema='g01-recorder-v1', rows=len(self.rows), simulated=True,
                        evidence_scope='simulation', firmware_sha256='a'*64,
                        sha256={name.replace('/', '\\'):v.sha(self.folder/name) for name in
                                ('raw/serial.bin', 'raw/events.jsonl', 'derived/device.csv')})
        (self.folder/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_affine_vector_and_simulation_never_passes(self):
        self.plan.update(tolerance_V=0.01, acceptance_basis='synthetic test only')
        for p in self.plan['points']:
            p.update(expanded_uncertainty_V=0.001, uncertainty_basis='synthetic only')
        result = v.fit_plan(self.plan, self.root)
        model = result['models']['cell1']
        self.assertAlmostEqual(model['gain_V_per_count'], 0.000101)
        self.assertAlmostEqual(model['offset_V'], 0.02)
        self.assertAlmostEqual(model['comparisons'][-1]['error_V'], 0)
        self.assertAlmostEqual(model['comparisons'][-1]['output_stddev_V'], 0.000101)
        self.assertIsNone(model['comparisons'][-1]['verdict'])
        self.assertFalse(result['calibration_verified'])

    def test_guardband(self):
        self.assertEqual(v.assess(0.001, 0.002, 0.005), 'pass')
        self.assertEqual(v.assess(-0.01, 0.002, 0.005), 'fail')
        self.assertEqual(v.assess(0.004, 0.002, 0.005), 'inconclusive')
        self.assertIsNone(v.assess(0, None, 0.005))

    def test_hash_tamper(self):
        with (self.folder/'derived/device.csv').open('ab') as f:
            f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            v.inspect_capture(self.folder)

    def test_overlap_and_reused_condition(self):
        plan = copy.deepcopy(self.plan)
        plan['points'][-1].update(seq_first=0, seq_last=2)
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            v.fit_plan(plan, self.root)
        self.plan['points'][-1]['reference_condition'] = 'independent-0'
        with self.assertRaisesRegex(ValueError, 'reuse'):
            v.fit_plan(self.plan, self.root)

    def test_insufficient_points_and_unknown_mapping(self):
        plan = copy.deepcopy(self.plan)
        plan['points'][1]['reference_V'] = plan['points'][0]['reference_V']
        with self.assertRaisesRegex(ValueError, 'distinct'):
            v.fit_plan(plan, self.root)
        self.plan['points'][0]['mapping_evidence'] = ''
        with self.assertRaisesRegex(ValueError, 'mapping_evidence'):
            v.fit_plan(self.plan, self.root)

    def test_stale_retained_in_statistics_but_rejected_for_fit(self):
        row = self.rows[1]
        row.update(age_ms='1001', status='144', raw_valid='0', sensor_V_nominal='', estimate='')
        row['wire_pec15'] = '%04X'%pec15(','.join(row[k] for k in FIELDS[:-1]).encode())
        self.save()
        self.assertEqual(v.inspect_capture(self.folder)['channels']['cell1']['invalid'], 1)
        with self.assertRaisesRegex(ValueError, 'invalid/stale'):
            v.fit_plan(self.plan, self.root)

    def test_missing_duplicate_and_time_discontinuity(self):
        self.rows.pop(1)
        self.save()
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            v.fit_plan(self.plan, self.root)
        self.rows.insert(1, copy.deepcopy(self.rows[0]))
        self.save()
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            v.fit_plan(self.plan, self.root)

    def test_extrapolation_not_accepted(self):
        # Put validation raw beyond fitted span while keeping valid wire data.
        for row in self.rows[-3:]:
            value = int(row['raw'])+5000
            data = value.to_bytes(2, 'little')+b'\xff'*4
            row.update(raw=str(value), sensor_V_nominal=str(value/10000), estimate=str(value/10000),
                       frame_hex=(data+pec15(data).to_bytes(2, 'big')).hex())
            row['wire_pec15'] = '%04X'%pec15(','.join(row[k] for k in FIELDS[:-1]).encode())
        self.save()
        report = v.fit_plan(self.plan, self.root)['models']['cell1']['comparisons'][-1]
        self.assertFalse(report['in_fitted_raw_range'])
        self.assertIsNone(report['verdict'])

    def test_no_current_or_temperature_coefficients(self):
        self.plan['points'][0]['channel'] = 'temperature_gpio2'
        with self.assertRaisesRegex(ValueError, 'only cell voltage'):
            v.fit_plan(self.plan, self.root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
