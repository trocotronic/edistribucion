
"""
Created on Wed May 20 11:42:56 2020

@author: trocotronic
"""

__VERSION__ = '0.8.0'

import requests, pickle, json
from bs4 import BeautifulSoup
from urllib.parse import unquote
import logging
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import credentials
from pyjsparser import parse as jsparse

UTC = tzutc()

logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
logging.getLogger().setLevel(logging.DEBUG)

class EdisError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

class UrlError(EdisError):
    def __init__(self, status_code, message, request):
        self.status_code = status_code
        self.request = request
        super().__init__(message)
    pass

class EdistribucionMessageAction(object):
    def __init__(self, id_: int, descriptor, callingDescriptor, params: dict):
        self.id = id_
        self.descriptor = descriptor
        self.callingDescriptor = callingDescriptor
        self.params = params
        self._extras = {}

    def __str__(self):
        data = {
            "id": self.id,
            "descriptor": self.descriptor,
            "callingDescriptor": self.callingDescriptor,
            "params": self.params
        }
        if self._extras:
            data.update(self._extras)
        return json.dumps(data)

    def add_field(self, key, value):
        self._extras[key] = value

    @property
    def id(self):
        return f"{self._id};a"

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def command(self):
        return ".".join(self._descriptor.split("/ACTION$"))

    @property
    def descriptor(self):
        return f"apex://{self._descriptor}"

    @descriptor.setter
    def descriptor(self, value):
        self._descriptor = value

    @property
    def callingDescriptor(self):
        return f"markup://c:{self._callingDescriptor}"

    @callingDescriptor.setter
    def callingDescriptor(self, value):
        self._callingDescriptor = value

def serialize_date(dt):
    """
    Serialize a date/time value into an ISO8601 text representation
    adjusted (if needed) to UTC timezone.

    For instance:
    >>> serialize_date(datetime(2012, 4, 10, 22, 38, 20, 604391))
    '2012-04-10T22:38:20.604391Z'
    """
    if dt.tzinfo:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat()

class Edistribucion():
    __session = None
    SESSION_FILE = 'edistribucion.session'
    ACCESS_FILE = 'edistribucion.access'
    __token = 'undefined'
    __credentials = {}
    __dashboard = 'https://zonaprivada.edistribucion.com/areaprivada/s/sfsites/aura?'
    __command_index = 0
    __identities = {}
    __context = None
    __access_date = datetime.now()

    def __init__(self, login=None, password=None, debug_level=logging.INFO):
        self.__session = requests.Session()
        self.__credentials['user'] = login or credentials.username
        self.__credentials['password'] = password or credentials.password

        try:
            with open(Edistribucion.SESSION_FILE, 'rb') as f:
                self.__session.cookies.update(pickle.load(f))
        except FileNotFoundError:
            logging.warning('Session file not found')
        try:
            with open(Edistribucion.ACCESS_FILE, 'rb') as f:
                d = json.load(f)
                self.__token = d['token']
                self.__identities = d['identities']
                self.__context = d['context']
                self.__access_date = datetime.fromisoformat(d['date'])
        except FileNotFoundError:
            logging.warning('Access file not found')

        logging.getLogger().setLevel(debug_level)

        self.login()

    def __get_url(self, url,get=None,post=None,json=None,cookies=None,headers=None):
        __headers = {
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:77.0) Gecko/20100101 Firefox/77.0',
        }
        if (headers):
            __headers.update(headers)
        if (post == None and json == None):
            r = self.__session.get(url, params=get, headers=__headers, cookies=cookies)
        else:
            r = self.__session.post(url, data=post, json=json, params=get, headers=__headers, cookies=cookies)
        logging.info('Sending %s request to %s', r.request.method, r.url)
        logging.debug('Parameters: %s', r.request.url)
        logging.debug('Headers: %s', r.request.headers)
        logging.debug(f'Post data: {post}')
        logging.info('Response with code: %d', r.status_code)
        logging.debug('Headers: %s', r.headers)
        logging.debug(f'Cookies: {r.cookies.get_dict()}')
        logging.debug('History: %s', r.history)
        if r.status_code >= 400:
            try:
                e = r.json()
                msg = 'Error {}'.format(r.status_code)
                logging.debug('Response error in JSON format')
                if ('error' in e):
                    msg += ':'
                    if ('errorCode' in e['error']):
                        msg += ' [{}]'.format(e['error']['errorCode'])
                    if ('description' in e['error']):
                        msg += ' '+e['error']['description']
            except ValueError:
                logging.debug('Response error is not JSON format')
                msg = "Error: status code {}".format(r.status_code)
            raise UrlError(r.status_code, msg, r)
        return r

    def __command(self, command, post=None, dashboard=None, accept='*/*', content_type=None, recursive=False):
        if (not dashboard):
            dashboard = self.__dashboard
        if (self.__command_index >= 0):
            command = f'r={self.__command_index}&{command}'
            self.__command_index += 1
        logging.info('Preparing command: %s', command)
        if (post):
            post['aura.context'] = self.__context
            post['aura.pageURI'] = '/areaprivada/s/'
            post['aura.token'] = self.__token
            logging.debug('POST data: %s', post)
        logging.debug('Dashboard: %s', dashboard)
        if (accept):
            logging.debug('Accept: %s', accept)
        if (content_type):
            logging.debug('Content-type: %s', content_type)
            '''
        try:
            if (not self.__check_tokens()):
                self.__force_login()
        except UrlError as e:
            raise EdisError('Aborting command {}: login failed ({})'.format(command,e.message))
            '''
        headers = {}
        if (content_type):
            headers['Content-Type'] = content_type
        if (accept):
            headers['Accept'] = accept
        r = self.__get_url(dashboard+command, post=post, headers=headers)
        if ('window.location.href' in r.text or 'clientOutOfSync' in r.text):
            if (not recursive):
                logging.info('Redirection received. Fetching credentials again.')

                self.__session = requests.Session()
                self.__force_login()
                self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recursive=True)
            else:
                logging.warning('Redirection received twice. Aborting command.')
        if ('json' in r.headers['Content-Type']):
            if ('Invalid token' in r.text):
                if (not recursive):
                    self.__session = requests.Session()
                    #self.__force_login()
                    self.__token = self.__get_token()
                    self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recursive=True)
                else:
                    logging.warning('Token expired. Cannot refresh')
            jr = r.json()
            if (jr['actions'][0]['state'] != 'SUCCESS'):
                if (not recursive):
                    logging.info('Error received. Fetching credentials again.')

                    self.__session = requests.Session()
                    self.__force_login()
                    self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recursive=True)
                else:
                    logging.warning('Error received twice. Aborting command.')
                    raise EdisError('Error processing command: {}'.format(jr['actions'][0]['error'][0]['message']))
            return jr['actions'][0]['returnValue']
        return r

    def __check_tokens(self):
        logging.debug('Checking tokens')
        return self.__token != 'undefined' and self.__access_date+timedelta(minutes=10) > datetime.now()

    def __save_access(self):
        t = {}
        t['token'] = self.__token
        t['identities'] = self.__identities
        t['context'] = self.__context
        t['date'] = datetime.now()
        with open(Edistribucion.ACCESS_FILE, 'w') as f:
            json.dump(t, f, default=serialize_date)
        logging.info('Saving access to file')

    def login(self):
        logging.info('Loging')
        if (not self.__check_tokens()):
            self.__session = requests.Session()
            return self.__force_login()
        return True

    def __get_token(self):
        r = self.__get_url('https://zonaprivada.edistribucion.com/areaprivada/s/')
        soup = BeautifulSoup(r.text, 'html.parser')
        scripts = soup.find_all('script')
        logging.info('Loading token scripts')
        for s in scripts:
            if (s.string and 'auraConfig' in s.string):
                prsr = jsparse(s.string)
                for b in prsr['body']:
                    decls = b.get('expression', {}).get('callee', {}).get('body', {}).get('body', [])
                    for d in decls:
                        if (d.get('type', None) == 'VariableDeclaration'):
                            for dc in d.get('declarations', []):
                                if (dc.get('id', {}).get('name', None) == 'auraConfig'):
                                    for prop in dc.get('init', {}).get('properties', []):
                                        if (prop.get('key', {}).get('value', None) == 'eikoocnekot'):
                                            cookie_var = prop.get('value', {}).get('value', None)
                                            ret = self.__session.cookies.get_dict().get(cookie_var, None)
                                            del self.__session.cookies[cookie_var]
                                            return ret
        return None

    def __force_login(self, recursive=False):
        logging.warning('Forcing login')
        r = self.__get_url('https://zonaprivada.edistribucion.com/areaprivada/s/login?ec=302&startURL=%2Fareaprivada%2Fs%2F')
        ix = r.text.find('auraConfig')
        if (ix == -1):
            raise EdisError('auraConfig not found. Cannot continue')

        soup = BeautifulSoup(r.text, 'html.parser')
        scripts = soup.find_all('script')
        logging.info('Loading scripts')
        for s in scripts:
            src = s.get('src')
            if (not src):
                continue
            if ('resources.js' in src):
                unq = unquote(src)
                #self.__context = unq[unq.find('{'):unq.rindex('}')+1]
                self.__context = '{"mode":"PROD","fwuid":"LU1oNENmckdVUXNqVGtLeG5odmktZ2Rkdk8xRWxIam5GeGw0LU1mRHRYQ3cyNDYuMTUuMS0zLjAuNA","app":"siteforce:communityApp","loaded":{"APPLICATION@markup://siteforce:communityApp":"8srl03VqKMnukxbiM5O73w"},"dn":[],"globals":{},"uad":false}'
        logging.info('Performing login routine')

        params = {
            "username": self.__credentials['user'],
            "password": self.__credentials['password'],
            "startUrl": "/areaprivada/s/"
        }
        action = EdistribucionMessageAction(
            91,
            "LightningLoginFormController/ACTION$login",
            "WP_LoginForm",
            params
        )

        data = {
                'message': '{"actions":[' + str(action) + ']}',
                'aura.context':self.__context,
                'aura.pageURI':'/areaprivada/s/login/?language=es&startURL=%2Fareaprivada%2Fs%2F&ec=302',
                'aura.token':'undefined',
                }
        r = self.__get_url(self.__dashboard+'r=1&other.LightningLoginForm.login=1',post=data)
        #print(r.text)
        if ('/*ERROR*/' in r.text):
            if ('invalidSession' in r.text and not recursive):
                self.__session = requests.Session()
                self.__force_login(recursive=True)
            raise EdisError('Unexpected error in loginForm. Cannot continue')
        jr = r.json()
        if ('events' not in jr):
            raise EdisError('Wrong login response. Cannot continue')
        logging.info('Accessing to frontdoor')
        r = self.__get_url(jr['events'][0]['attributes']['values']['url'])
        logging.info('Accessing to landing page')
        self.__token = self.__get_token()
        if (not self.__token):
            raise EdisError('token not found. Cannot continue')
        logging.info('Token received!')
        logging.debug(self.__token)
        logging.info('Retreiving account info')
        r = self.get_login_info()
        self.__identities['account_id'] = r['visibility']['Id']
        self.__identities['name'] = r['Name']
        logging.info('Received name: %s (%s)',r['Name'],r['visibility']['Visible_Account__r']['Identity_number__c'])
        logging.debug('Account_id: %s', self.__identities['account_id'])
        with open(Edistribucion.SESSION_FILE, 'wb') as f:
            pickle.dump(self.__session.cookies, f)
        logging.debug('Saving session')
        self.__save_access()

    def __run_action_command(self, action, command=None):
        data = {'message': '{"actions":[' + str(action) + ']}'}
        if not command:
            command = action.command
        req = self.__command(f"other.{command}=1", post=data)
        return req

    def get_login_info(self):
        action = EdistribucionMessageAction(
            215,
            "WP_Monitor_CTRL/ACTION$getLoginInfo",
            "WP_Monitor",
            {"serviceNumber": "S011"}
        )
        return self.__run_action_command(action)

    def get_identities(self):
        ids = self.get_login_info()
        return ids.get('authList',[])

    def get_cups(self, vis=None):
        action = EdistribucionMessageAction(
            270,
            "WP_ContadorICP_F2_CTRL/ACTION$getCUPSReconectarICP",
            "WP_Reconnect_ICP",
            {"visSelected": vis or self.__identities['account_id']}
        )
        return self.__run_action_command(action)

    def get_cups_info(self, cups, vis=None):
        action = EdistribucionMessageAction(
            489,
            "WP_ContadorICP_F2_CTRL/ACTION$getCupsInfo",
            "WP_Reconnect_Detail_F2",
            {"cupsId": cups, "visSelected": vis or self.__identities['account_id']}
        )
        return self.__run_action_command(action)

    def get_meter(self, cups):
        action = EdistribucionMessageAction(
            522,
            "WP_ContadorICP_F2_CTRL/ACTION$consultarContador",
            "WP_Reconnect_Detail",
            {"cupsId": cups}
        )
        return self.__run_action_command(action)

    def get_all_cups(self, vis=None):
        action = EdistribucionMessageAction(
            294,
            "WP_ConsultaSuministros/ACTION$getAllCUPS",
            "WP_MySuppliesForm",
            {"visSelected": vis or self.__identities['account_id']}
        )
        return self.__run_action_command(action)

    def get_cups_detail(self, cups, vis=None):
        action = EdistribucionMessageAction(
            490,
            "WP_CUPSDetail_CTRL/ACTION$getCUPSDetail",
            "WP_cupsDetail",
            {"visSelected": vis or self.__identities['account_id'], "cupsId": cups}
        )
        return self.__run_action_command(action)

    def get_cups_status(self, cups):
        action = EdistribucionMessageAction(
            629,
            "WP_CUPSDetail_CTRL/ACTION$getStatus",
            "WP_cupsDetail",
            {"cupsId": cups}
        )
        return self.__run_action_command(action)

    def get_atr_detail(self, atr):
        action = EdistribucionMessageAction(
            62,
            "WP_ContractATRDetail_CTRL/ACTION$getATRDetail",
            "WP_SuppliesATRDetailForm",
            {"atrId": atr}
        )
        return self.__run_action_command(action)

    def get_solicitud_atr_detail(self, sol):
        action = EdistribucionMessageAction(
            56,
            "WP_SolicitudATRDetail_CTRL/ACTION$getSolicitudATRDetail",
            "WP_ATR_Requests_Detail_Form",
            {"solId": sol}
        )
        return self.__run_action_command(action)

    def reconnect_ICP(self, cups):
        action = EdistribucionMessageAction(
            261,
            "WP_ContadorICP_F2_CTRL/ACTION$reconectarICP",
            "WP_Reconnect_Detail_F2",
            {"cupsId": cups}
        )
        r = self.__run_action_command(action)
        # -----
        action = EdistribucionMessageAction(
            287,
            "WP_ContadorICP_F2_CTRL/ACTION$goToReconectarICP",
            "WP_Reconnect_Modal",
            {"cupsId": cups}
        )
        r = self.__run_action_command(action)

        return r

    def get_list_cups(self, vis=None):
        action = EdistribucionMessageAction(
            1086,
            "WP_Measure_v3_CTRL/ACTION$getListCups",
            "WP_Measure_List_v4",
            {"sIdentificador": vis or self.__identities['account_id']}
        )
        r = self.__run_action_command(action)

        conts = []
        for cont in r['data']['lstCups']:
            if (cont['Id'] in r['data']['lstIds']):
                c = {}
                c['CUPS'] = cont['CUPs__r']['Name']
                c['CUPS_Id'] = cont['CUPs__r']['Id']
                c['Id'] = cont['Id']
                c['Active'] = False if 'Version_end_date__c' in cont else True
                c['Power'] = cont['Requested_power_1__c']
                c['Rate'] = cont['rate']
                conts.append(c)
        return conts

    def get_list_cycles(self, cont):
        action = EdistribucionMessageAction(
            1190,
            "WP_Measure_v3_CTRL/ACTION$getInfo",
            "WP_Measure_Detail_v4",
            {"contId": cont}
        )
        action.add_field("longRunning", True)

        r = self.__run_action_command(action)
        return r['data']['lstCycles']

    def get_meas(self, cont, cycle):
        action = EdistribucionMessageAction(
            1295,
            "WP_Measure_v3_CTRL/ACTION$getChartPoints",
            "WP_Measure_Detail_v4",
            {"cupsId": cont, "dateRange": cycle['label'], "cfactura": cycle['value']}
        )
        action.add_field("longRunning", True)

        r = self.__run_action_command(action)
        return r['data']['lstData']

    def get_meas_interval(self, cont, startDate, endDate):
        action = EdistribucionMessageAction(
            1362,
            "WP_Measure_v3_CTRL/ACTION$getChartPointsByRange",
            "WP_Measure_Detail_Filter_Advanced_v3",
            {"contId": cont, "type": 4, "startDate": startDate, "endDate": endDate}
        )

        r = self.__run_action_command(action)
        return r['data']['lstData']
