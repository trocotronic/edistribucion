"""
Created on Wed May 20 11:51:36 2020

@author: trocotronic
"""

from EdistribucionAPI import Edistribucion

edis = Edistribucion()
edis.login()
r = edis.get_cups()
cups = edis.get_list_cups()[-1]
print('Cups: ',cups['Id'])
info = edis.get_cups_info(cups['CUPS_Id'])
print(info)
cycles = edis.get_list_cycles(cups)
meas = edis.get_meas(cups, cycles[0]) # Contains all measured points per hour for the first cycle

