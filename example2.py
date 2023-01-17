"""
Created on Wed May 20 11:51:36 2020

@author: trocotronic
"""

'''
This example show how to call cycle and measurements panel.
'''

from EdistribucionAPI import Edistribucion

edis = Edistribucion()
edis.login()
cups = edis.get_list_cups()[-1]
print('Cups: ',cups['CUPS_Id'])
info = edis.get_cups_info(cups['CUPS_Id'])
print(info)
cycles = edis.get_list_cycles(cups['Id'])
meas = edis.get_meas(cups['Id'], cycles[0]) # Contains all measured points per hour for the first cycle
meas = edis.get_meas_interval(cups['Id'], '2022-12-01', '2022-12-31')

