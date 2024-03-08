#  ============LICENSE_START===============================================
#  Copyright (C) 2023 Rimedo Labs and Tietoevry. All rights reserved.
#  ========================================================================
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  ============LICENSE_END=================================================
#

import numpy as np
import requests
import random
import logging
import time
import json
import os
from operator import itemgetter
from enum import Enum

NCI_LENGTH = 36

CANDIDATE_CELL_IDS = [0,1]

def get_example_per_slice_policy(nci: int, mcc: str, mnc: str, qos: int, preference: str):
    ## hardcoded values used for SMaRT-5G demo
    return {
        "scope": {
            "sliceId": {
                "sst": 1,
                "sd": "456DEF",
                "plmnId": {
                    "mcc": mcc,
                    "mnc": mnc
                }
            },
            "qosId": {
                "5qI": qos
            }
        },
        "tspResources": [
            {
                "cellIdList": [
                    {
                        "plmnId": {
                            "mcc": mcc,
                            "mnc": mnc
                        },
                        "cId": {
                            "ncI": nci
                        }
                    }
                ],
                "preference": preference
            }
        ]
    }

log = logging.getLogger('main')

FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT)  # , stream=sys.stdout
log.setLevel(logging.INFO)
log.info(f'rApp START')

class States(Enum):
    ENABLED = 1
    DISABLED = 2
    DISABLING = 3

class Application:
    def __init__(self, sleep_time_sec: float, sleep_after_decision_sec: float, slots: int):
        self.sleep_time_sec = sleep_time_sec
        self.sleep_after_decision_sec = sleep_after_decision_sec
        self.slots = slots

        self.cells = {}
        self.cell_urls = {}
        self.policyVariables = {}
        self.ready_time = time.time() + sleep_after_decision_sec
        self.source_name = ""
        self.meas_entity_dist_name = ""

        self.prb_history = []
        self.switch_off = False
        self.index = 0
        self.load_predictor = 'http://' + os.environ['LOAD_PREDICTOR'] + ':' + os.environ['LOAD_PREDICTOR_PORT'] + '/' + os.environ['LOAD_PREDICTOR_API']

        self.a1_url = 'http://' + os.environ['A1T_ADDRESS'] + ':' + os.environ['A1T_PORT']
        self.ransim_data_path = os.environ['RANSIM_DATA_PATH']

        self.sdn_controller_address = os.environ['SDN_CONTROLLER_ADDRESS']
        self.sdn_controller_port = os.environ['SDN_CONTROLLER_PORT']
        self.sdn_controller_auth = (os.environ['SDN_CONTROLLER_USERNAME'], os.environ['SDN_CONTROLLER_PASSWORD'])

    def work(self):
        policies = self.get_policies()
        if policies is None:
            log.error('Unable to connect to A1.')
            return

        for policy in policies:
            # assumed that all policies with ID >= 1000 are from this rApp
            if int(policy) >= 1000:
                self.delete_policy(policy)

        self.init()
        if not self.cell_urls:
            log.error('Unable to fetch cell URLs')
            return

        while True:
            time.sleep(self.sleep_time_sec)

            data = self.read_data()
            if not data:
                continue

            self.update_local_data(data)

            if time.time() >= self.ready_time:
                self.ready_time = time.time() + self.sleep_after_decision_sec
                if self.cells:
                    self.make_decision()

    def read_data(self):
        data = None
        try:
            reports_list = os.listdir(self.ransim_data_path)
            reports_list_fullpath = ["{}/{}".format(self.ransim_data_path, report) for report in reports_list]
            oldest_report = min(reports_list_fullpath, key=os.path.getmtime)
            log.debug(f'Opening report file: {oldest_report}')
            with open(oldest_report) as file:
                data = json.load(file)
            os.remove(oldest_report)
        except Exception as ex:
            pass
        return data

    def update_local_data(self, data):
        report_type = data['event']['perf3gppFields']['measDataCollection']['measuredEntityDn']
        if "Cell" not in report_type:
            log.info('Received report is not a Cell report')
            return

        self.source_name = data['event']['commonEventHeader']['sourceName']
        self.meas_entity_dist_name = report_type

        cells = data['event']['perf3gppFields']['measDataCollection']['measInfoList']

        if not cells:
            log.warning("PM report is lacking measurements")
            return

        for cell in cells:
            cId = str(cell['measInfoId']['sMeasInfoId'])

            p = -1
            types_list = cell['measTypes']['sMeasTypesList']
            for index_types, pm_type in enumerate(types_list):
                if pm_type == 'RRU.PrbTotDl':
                    p = index_types
                    break

            if p == -1:
                log.error('PM type RRU.PrbTotDl not present')
                return

            if cId not in self.cells:
                self.cells[cId] = {
                    "id": cId,
                    "state": States.ENABLED,
                    "prb_usage": [],
                    "avg_prb_usage": np.nan,
                    "policy_list": []
                }

            store = self.cells[cId]
            store['prb_usage'] = []

            for measValue in cell['measValuesList']:
                sValue = measValue['measResults'][p]['sValue']
                store['prb_usage'].append(float(sValue))

            if store['prb_usage']:
                store['avg_prb_usage'] = np.mean(store['prb_usage'])

        status = "PRB usage: ["
        candidate_prbs = []
        for i, key in enumerate(self.cells.keys()):
            cell = self.cells[key]
            avg_prb_usage = cell["avg_prb_usage"]

            # c1_prbs = [1,2,3]
            # c2_prbs = [6,7,8]
            # candidate_prbs = [[1,2,3], [6,7,8]]
            # sum_of_candidate_prbs = [1+6, 2+7, 3+8]

            if i in CANDIDATE_CELL_IDS and not np.isnan(avg_prb_usage):
                candidate_prbs.append(cell['prb_usage'])

            status += f'{cell["id"]}: {avg_prb_usage:.3f}, '

        sum_of_candidate_prbs = [candidate_prbs[0][i] + candidate_prbs[1][i] for i in range(self.slots)]
        for prb in sum_of_candidate_prbs:
            self.prb_history.append(int(prb))

        status = status[:-2] + "] avg: "
        avg_prb = sum(self.cells[cell]["avg_prb_usage"] for cell in self.cells) / sum((self.cells[cell]['state'] != States.DISABLED) for cell in self.cells)
        status += f'{avg_prb:.3f}'

        status += f', [candidate_prbs]: {candidate_prbs}, [sum_of_candidate_prbs]: {sum_of_candidate_prbs}'

        energy_all = (300 + 4 * 150) / 1e3
        energy = (300 + (sum((self.cells[cell]['state'] != States.DISABLED) for cell in self.cells) - 1) * 150) / 1e3
        energy_per_day = 24 * energy
        energy_save = (energy_all - energy) * 24
        status += f', (energy consumption: {energy:.2f}/{energy_all:.2f} W; per day: {energy_per_day:.2f} Wh; per day savings: {energy_save:.2f} Wh)'
        log.info(status)

    def make_decision(self):
        if len(self.prb_history) < 10:
            log.error("Insufficient data to make a prediction")
            log.info(f'prb_history = {self.prb_history}')
            return

        data = []
        for i, key in enumerate(self.cells.keys()):
            record = [None] * 3
            record[0] = self.cells[key]['id']
            record[1] = self.cells[key]['avg_prb_usage']
            record[2] = self.cells[key]['state']
            data.append(record)

        if any(np.nan in record for record in data):
            return

        total_prb_usage = sum(record[1] for record in data)
        enabled_cells = sum((record[2] != States.DISABLED) for record in data)
        disabling_cell = sum((record[2] == States.DISABLING) for record in data)

        log.info(f'Checking if a cell should be switched off')
        for record in data:
            if record[1] == 0 and (record[2] == States.DISABLING):
                cell_id = record[0]
                self.toggle_cell_administrative_state(cell_id, locked=True)
                self.cells[cell_id]['state'] = States.DISABLED
                enabled_cells-=1
                # Because report arrives once per 60s, skip making decision
                # to avoid OFF->ON in the same time frame.
                return

        current_avg_prb_usage = total_prb_usage / enabled_cells

        log.info(f'Making decision...')
        log.info(f'Current average PRB usage: {current_avg_prb_usage}')
        if (max(record[1] for record in data) > 40) and (current_avg_prb_usage > 30):
            log.info('Max and average PRB usage above thresholds - trying to enable one cell.')
            self.enable_one_cell()
        elif (current_avg_prb_usage < 20) and (disabling_cell == 0):
            log.info('Average PRB usage below threshold - trying to disable one cell.')
            future_avg_prb_usage = total_prb_usage / (enabled_cells - 1)
            log.info(f'Expected PRB usage {future_avg_prb_usage}.')
            self.disable_one_cell()
        else:
            log.info('Make cell on/off decision - no action - balance achieved.')

    def toggle_cell_administrative_state(self, cell_id, locked):
        sOff='off' if locked else 'on'
        log.info(f'Switching {sOff} cell {cell_id}')
        path_base = '/O1/CM/'
        path_tail = self.cell_urls[cell_id]
        url = 'http://' + self.sdn_controller_address + ':' + self.sdn_controller_port + path_base + path_tail
        payload = { "attributes": {"administrativeState": "LOCKED" if locked else "UNLOCKED"} }
        response = requests.put(url, verify=False, auth=self.sdn_controller_auth, json=payload)
        log.info(f'Cell-{sOff} response status:{response.status_code}')

    def enable_one_cell(self):
        options = []
        for key in self.cells.keys():
            option = [None] * 3
            option[0] = self.cells[key]['id']
            option[1] = self.cells[key]['avg_prb_usage']
            option[2] = (self.cells[key]['state'] == States.DISABLED)
            options.append(option)

        options_filtered = [option for option in options if option[2] == True]
        if len(options_filtered) == 0:
            log.info('There are no cells that could be enabled...')
            return

        cell_id = random.choice(options_filtered)[0]
        self.cells[cell_id]['state'] = States.ENABLED
        self.toggle_cell_administrative_state(cell_id, locked=False)
        self.send_command_enable_cell(cell_id)

    def send_command_enable_cell(self, cell_id):
        log.info(f'Enabling cell {cell_id}')
        for policy in self.cells[cell_id]['policy_list']:
            self.delete_policy(str(policy))
        self.cells[cell_id]['policy_list'] = []

    def disable_one_cell(self):
        options = []
        for key in self.cells.keys():
            option = [None] * 3
            option[0] = self.cells[key]['id']
            option[1] = self.cells[key]['avg_prb_usage']
            option[2] = (self.cells[key]['state'] == States.ENABLED)
            options.append(option)

        options_filtered = [option for option in options if option[2] == True]
        if len(options_filtered) == 0:
            log.info('There are no cells that could be disabled...')
            return

        ind = sorted(options_filtered, key=itemgetter(1))[0]
        cell_id = ind[0]
        self.cells[cell_id]['state'] = States.DISABLING
        self.send_command_disable_cell(cell_id)

    def send_command_disable_cell(self, cell_id):
        cellLocalId = self.policyVariables[cell_id]['cellLocalId']
        mcc = self.policyVariables[cell_id]['mcc']
        mnc = self.policyVariables[cell_id]['mnc']
        nci = self.calculate_nci(self.policyVariables['gnbId'], NCI_LENGTH, self.policyVariables['gnbIdLength'], cellLocalId)
        log.info(f'Disabling cell {cell_id} [cellLocalId={cellLocalId}, nci={nci}, mcc={mcc}, mnc={mnc}]')
        current_policies = self.get_policies()

        index = 1000
        while str(index) in current_policies:
            index += 1

        # put new policy with FORBID based on scope
        response = requests.put(self.a1_url +
                                '/policytypes/ORAN_TrafficSteeringPreference_2.0.0/policies/'
                                + str(index), params=dict(notification_destination='test'),
                                json=get_example_per_slice_policy(nci, mcc, mnc, qos=1, preference='FORBID'))
        log.info(f'Sending policy (id={index}) for cell {cell_id} [nci={nci}, mcc={mcc}, mnc={mnc}] (FORBID): status_code: {response.status_code}')
        self.cells[cell_id]['policy_list'].append(index)

        # index += 1
        # while str(index) in current_policies:
        #     index += 1
        # response = requests.put(self.a1_url +
        #                         '/policytypes/ORAN_TrafficSteeringPreference_2.0.0/policies/'
        #                         + str(index), params=dict(notification_destination='test'),
        #                         json=get_example_per_slice_policy(nci, mcc, mnc, qos=2, preference='FORBID'))
        # log.info(f'Sending policy (id={index}) for cell {cell_id} [nci={nci}, mcc={mcc}, mnc={mnc}] (FORBID): status_code: {response.status_code}')
        # self.cells[cell_id]['policy_list'].append(index)

    def delete_policy(self, policy_id: str):
        log.info(f'Deleting policy with id: {policy_id}')
        try:
            requests.delete(self.a1_url +
                            '/policytypes/ORAN_TrafficSteeringPreference_2.0.0/policies/' + policy_id)
        except Exception as ex:
            log.error(ex)

    def get_policies(self):
        try:
            response = requests.get(self.a1_url +
                                    '/policytypes/ORAN_TrafficSteeringPreference_2.0.0/policies').json()
            return response
        except Exception as ex:
            log.error(ex)
            return None

    def _getIdOfManagedElement(self):
        path_base = '/O1/CM/ManagedElement'
        url = 'http://' + self.sdn_controller_address + ':' + self.sdn_controller_port + path_base
        try:
            response = requests.get(url, auth=self.sdn_controller_auth).json()
            id = response[0]["id"]
            log.info(f'GET O1/CM/ManagedElement -> id = {id}')
            return id
        except Exception as ex:
            log.error(ex)
            return None

    def calculate_nci(self, gnbId: str, nciLength: int, gnbIdLength: int, cellId: int):
        return (int(gnbId) << (nciLength - gnbIdLength)) | cellId

    def init(self):
        id = self._getIdOfManagedElement()
        path_base = f'/O1/CM/ManagedElement={id}'
        url = 'http://' + self.sdn_controller_address + ':' + self.sdn_controller_port + path_base
        try:
            response = requests.get(url, auth=self.sdn_controller_auth).json()
            gnb_du_function = response['GnbDuFunction']

            # Assumption - all below values are same across GnbDuFunctions
            self.policyVariables['gnbId'] = gnb_du_function[0]['attributes']['gnbId']
            self.policyVariables['gnbIdLength'] = gnb_du_function[0]['attributes']['gnbIdLength']

            for data in gnb_du_function:
                for cell_du in data['NrCellDu']:
                    cell_name = cell_du['viavi-attributes']['cellName']
                    url = cell_du['objectInstance']
                    self.cell_urls[cell_name] = url

                    self.policyVariables[cell_name] = {}
                    self.policyVariables[cell_name]['cellLocalId'] = cell_du['attributes']['cellLocalId']

                    # Assumption - plmnInfoList has only 1 element
                    self.policyVariables[cell_name]['mcc'] = cell_du['attributes']['plmnInfoList'][0]['plmnId']['mcc']
                    self.policyVariables[cell_name]['mnc'] = cell_du['attributes']['plmnInfoList'][0]['plmnId']['mnc']

            return response
        except Exception as ex:
            log.error(ex)
            return None


if __name__ == '__main__':
    app = Application(
        sleep_time_sec=1.0,
        sleep_after_decision_sec=10.0,

        # number of measurements in incoming report: 60 / Aggregation Granularity (O1 Interface Config)
        slots=5
    )
    app.work()
