#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 20 11:51:36 2020

@author: trocotronic
"""

USER = 'you_login'
PASSWORD = 'your_pw'

from EdistribucionAPI import Edistribucion

edis = Edistribucion(USER,PASSWORD)
edis.login()
r = edis.get_cups()
cups = r['data']['lstCups'][0]['Id']
print(cups)