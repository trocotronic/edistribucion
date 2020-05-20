#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 20 11:42:56 2020

@author: trocotronic
"""

import requests, pickle, json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
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


class Edistribucion():
    __session = None
    SESSION_FILE = 'edistribucion.session'
    ACCESS_FILE = 'edistribucion.access'
    __token = 'undefined'
    __credentials = {}
    __dashboard = 'https://zonaprivada.edistribucion.com/areaprivada/s/sfsites/aura?'
    __command_index = 0
    def __init__(self, user, password):
        self.__session = requests.Session()
        self.__credentials['user'] = user
        self.__credentials['password'] = password
        
        try:
            with open(Edistribucion.SESSION_FILE, 'rb') as f:
                self.__session.cookies.update(pickle.load(f))
        except FileNotFoundError:
            logging.warning('Session file not found')
        try:
            with open(Edistribucion.ACCESS_FILE, 'rb') as f:
                d = json.load(f)
                self.__token = d['token']
        except FileNotFoundError:
            logging.warning('Access file not found')
        
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
        logging.info('Response with code: %d', r.status_code)
        logging.debug('Headers: %s', r.headers)
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
    
    def __command(self, command, post=None, dashboard=None, accept='*/*', content_type=None, recurrent=False):
        if (not dashboard):
            dashboard = self.__dashboard
        if (self.__command_index):
            command = 'r='+self.__command_index+'&'
            self.__command_index += 1
        logging.info('Preparing command: %s', command)
        if (post):
            post['aura.context'] = '{"mode":"PROD","fwuid":"5EkiQjrG-amda9Z1-HgsDQ","app":"siteforce:communityApp","loaded":{"APPLICATION@markup://siteforce:communityApp":"ide1NyqwEFjB0hcXqolx2Q"},"dn":[],"globals":{},"uad":false}'
            post['aura.pageURI'] = '/areaprivada/s/wp-online-access'
            post['aura.token'] = self.__token
            logging.debug('POST data: %s', post)
        logging.debug('Dashboard: %s', dashboard)
        if (accept):
            logging.debug('Accept: %s', accept)
        if (content_type):
            logging.debug('Content-tpye: %s', content_type)
        try:
            if (not self.__check_tokens()):
                self.__force_login()
        except UrlError as e:
            raise EdisError('Aborting command {}: login failed ({})'.format(command,e.message))
        headers = {}
        if (content_type):
            headers['Content-Type'] = content_type
        if (accept):
            headers['Accept'] = accept
        r = self.__get_url(dashboard+command, post=post, headers=headers)
        if ('window.location.href' in r.text):
            if (not recurrent):
                logging.info('Redirection received. Fetching credentials again.')
                self.__force_login()
                self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recurrent=True)
            else:
                logging.warning('Redirection received twice. Aborting command.')
        if ('json' in r.headers['Content-Type']):
            jr = r.json()
            return jr
        return r
    
    def __check_tokens(self):
        logging.debug('Checking tokens')
        return self.__token != 'undefined'
        
    def __save_access(self):
        t = {}
        t['token'] = self.__token
        with open(Edistribucion.ACCESS_FILE, 'w') as f:
            json.dump(t, f)
        logging.info('Saving access to file')
        
    def login(self):
        logging.info('Logging')
        if (not self.__check_tokens()):
            return self.__force_login()
        return True
    
    def __force_login(self):
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
            upr = urlparse(r.url)
            r = self.__get_url(upr.scheme+'://'+upr.netloc+src)
        
        logging.info('Performing login routine')
        data = {
                'message':'{"actions":[{"id":"91;a","descriptor":"apex://LightningLoginFormController/ACTION$login","callingDescriptor":"markup://c:WP_LoginForm","params":{"username":"'+self.__credentials['user']+'","password":"'+self.__credentials['password']+'","startUrl":"/areaprivada/s/"}}]}',
                'aura.context':'{"mode":"PROD","fwuid":"5EkiQjrG-amda9Z1-HgsDQ","app":"siteforce:loginApp2","loaded":{"APPLICATION@markup://siteforce:loginApp2":"QIjIXSLGqcgAH-oBcEbh6g"},"dn":[],"globals":{},"uad":false}',
                'aura.pageURI':'/areaprivada/s/login/?language=es&startURL=%2Fareaprivada%2Fs%2F&ec=302',
                'aura.token':'undefined',
                }
        r = self.__get_url(self.__dashboard+'other.LightningLoginForm.login=1',post=data)
        jr = r.json()
        if ('events' not in jr):
            raise EdisError('Wrong login response. Cannot continue')
        logging.info('Accessing to frontdoor')
        r = self.__get_url(jr['events'][0]['attributes']['values']['url'])
        logging.info('Accessing to landing page')
        r = self.__get_url('https://zonaprivada.edistribucion.com/areaprivada/s/')
        ix = r.text.find('auraConfig')
        if (ix == -1):
            raise EdisError('auraConfig not found. Cannot continue')
        ix = r.text.find('{',ix)
        ed = r.text.find(';',ix)
        jr = json.loads(r.text[ix:ed])
        if ('token' not in jr):
            raise EdisError('token not found. Cannot continue')
        self.__token = jr['token']
        logging.info('Token received!')
        logging.debug(self.__token)
        with open(Edistribucion.SESSION_FILE, 'wb') as f:
            pickle.dump(self.__session.cookies, f)
        logging.debug('Saving session')
        self.__save_access()
            
    def get_login_info(self):
        data = {
            'message': '{"actions":[{"id":"215;a","descriptor":"apex://WP_Monitor_CTRL/ACTION$getLoginInfo","callingDescriptor":"markup://c:WP_Monitor","params":{"serviceNumber":"S011"}}]}',
            }
        r = self.__command('other.WP_Monitor_CTRL.getLoginInfo=1', post=data)
        return r
        
        